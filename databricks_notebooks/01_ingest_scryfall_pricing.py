# Databricks notebook source
# MAGIC %md
# MAGIC # Scryfall Pricing Ingestion
# MAGIC 
# MAGIC **Purpose**: Collect daily pricing from Scryfall API and write to MongoDB
# MAGIC 
# MAGIC **Replaces**: Azure Functions `pricing_pipeline.py`
# MAGIC 
# MAGIC **Flow**:
# MAGIC 1. Fetch bulk pricing data from Scryfall API (75 cards per request)
# MAGIC 2. Parse and transform to unpivoted format
# MAGIC 3. Write to MongoDB `card_pricing_daily` collection
# MAGIC 4. Clean up old data (keep 7 days only)
# MAGIC 
# MAGIC **Schedule**: Daily at 1:00 AM UTC
# MAGIC 
# MAGIC **Runtime**: ~3-5 minutes for 78k cards

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

import requests
import time
from datetime import datetime, timedelta
from pymongo import MongoClient, UpdateOne
from pyspark.sql.functions import col, explode, lit, current_timestamp

# Configuration
SCRYFALL_BULK_API = "https://api.scryfall.com/bulk-data"
SCRYFALL_COLLECTION_API = "https://api.scryfall.com/cards/collection"
BATCH_SIZE = 75  # Scryfall allows 75 identifiers per request
RATE_LIMIT_DELAY = 0.1  # 100ms between requests (Scryfall rate limit)
MONGO_RETENTION_DAYS = 7  # Keep only 7 days in MongoDB

# Get MongoDB connection from secrets
mongo_uri = dbutils.secrets.get(scope="mtgecorec", key="cosmos-connection-string")
mongo_client = MongoClient(mongo_uri)
db = mongo_client["mtgecorec"]
pricing_collection = db["card_pricing_daily"]

print(f"✅ Connected to MongoDB database: {db.name}")
print(f"✅ Target collection: {pricing_collection.name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Get Card List from MongoDB

# COMMAND ----------

# Get all cards that need pricing updates
# (Only cards that are legal in some format and have pricing available)
cards_df = (spark.read
  .format("mongo")
  .option("uri", mongo_uri)
  .option("database", "mtgecorec")
  .option("collection", "cards")
  .load()
  .select("id", "name")
  .filter(col("id").isNotNull())
)

total_cards = cards_df.count()
card_ids = [row.id for row in cards_df.collect()]

print(f"✅ Found {total_cards:,} cards to update pricing for")
print(f"📦 Will process in batches of {BATCH_SIZE}")
print(f"⏱️ Estimated time: {(total_cards / BATCH_SIZE * RATE_LIMIT_DELAY / 60):.1f} minutes")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Fetch Pricing from Scryfall API

# COMMAND ----------

def fetch_pricing_batch(card_identifiers):
    """
    Fetch pricing for a batch of cards from Scryfall Collection API
    
    Args:
        card_identifiers: List of Scryfall IDs (max 75)
    
    Returns:
        List of card objects with pricing data
    """
    url = SCRYFALL_COLLECTION_API
    payload = {
        "identifiers": [{"id": card_id} for card_id in card_identifiers]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "data" in data:
            return data["data"]
        else:
            print(f"⚠️ Unexpected response format: {data}")
            return []
            
    except requests.exceptions.RequestException as e:
        print(f"❌ API request failed: {e}")
        return []

def extract_pricing_records(card, collection_date):
    """
    Extract pricing records from Scryfall card object
    
    Converts from:
      {prices: {usd: "2.50", usd_foil: "5.00", ...}}
    
    To (unpivoted):
      [
        {scryfall_id: "abc", date: "2026-02-03", price_type: "usd", price_value: 2.50},
        {scryfall_id: "abc", date: "2026-02-03", price_type: "usd_foil", price_value: 5.00},
        ...
      ]
    """
    records = []
    prices = card.get("prices", {})
    
    # Map price types to currency and finish
    price_mappings = {
        "usd": {"currency": "usd", "finish": "nonfoil"},
        "usd_foil": {"currency": "usd", "finish": "foil"},
        "usd_etched": {"currency": "usd", "finish": "etched"},
        "eur": {"currency": "eur", "finish": "nonfoil"},
        "eur_foil": {"currency": "eur", "finish": "foil"},
        "tix": {"currency": "tix", "finish": "nonfoil"},
    }
    
    for price_type, price_value in prices.items():
        if price_value is not None and price_type in price_mappings:
            try:
                price_float = float(price_value)
                if price_float > 0:
                    mapping = price_mappings[price_type]
                    records.append({
                        "scryfall_id": card["id"],
                        "card_name": card["name"],
                        "date": collection_date,
                        "price_type": price_type,
                        "price_value": price_float,
                        "currency": mapping["currency"],
                        "finish": mapping["finish"],
                        "tcgplayer_id": card.get("tcgplayer_id"),
                        "cardmarket_id": card.get("cardmarket_id"),
                        "collected_at": datetime.utcnow().isoformat(),
                        "source": "scryfall_api"
                    })
            except (ValueError, TypeError):
                continue
    
    return records

# COMMAND ----------

# Collect all pricing records
all_pricing_records = []
collection_date = datetime.utcnow().strftime("%Y-%m-%d")
total_batches = (len(card_ids) + BATCH_SIZE - 1) // BATCH_SIZE

print(f"🚀 Starting pricing collection for {collection_date}")
print(f"📊 Processing {total_batches:,} batches...")

for i in range(0, len(card_ids), BATCH_SIZE):
    batch_num = i // BATCH_SIZE + 1
    batch_ids = card_ids[i:i + BATCH_SIZE]
    
    # Fetch pricing for this batch
    cards_data = fetch_pricing_batch(batch_ids)
    
    # Extract pricing records
    for card in cards_data:
        records = extract_pricing_records(card, collection_date)
        all_pricing_records.extend(records)
    
    # Progress update
    if batch_num % 100 == 0 or batch_num == total_batches:
        print(f"  ✓ Processed {batch_num:,} / {total_batches:,} batches ({len(all_pricing_records):,} records)")
    
    # Rate limiting
    if i + BATCH_SIZE < len(card_ids):
        time.sleep(RATE_LIMIT_DELAY)

print(f"✅ Collection complete: {len(all_pricing_records):,} pricing records")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Write to MongoDB

# COMMAND ----------

if len(all_pricing_records) > 0:
    # Bulk write to MongoDB (much faster than individual inserts)
    print(f"💾 Writing {len(all_pricing_records):,} records to MongoDB...")
    
    start_time = time.time()
    
    # Use bulk insert (faster than upserts for daily batch)
    result = pricing_collection.insert_many(all_pricing_records, ordered=False)
    
    elapsed = time.time() - start_time
    
    print(f"✅ Inserted {len(result.inserted_ids):,} records in {elapsed:.1f} seconds")
    print(f"📈 Throughput: {len(result.inserted_ids) / elapsed:.0f} records/second")
else:
    print("⚠️ No pricing records to insert")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Cleanup Old Data (Keep 7 Days)

# COMMAND ----------

# Delete pricing data older than retention period
retention_cutoff = (datetime.utcnow() - timedelta(days=MONGO_RETENTION_DAYS)).strftime("%Y-%m-%d")

print(f"🗑️ Deleting pricing data older than {retention_cutoff}...")

delete_result = pricing_collection.delete_many({
    "date": {"$lt": retention_cutoff}
})

print(f"✅ Deleted {delete_result.deleted_count:,} old records")
print(f"📊 MongoDB now contains last {MONGO_RETENTION_DAYS} days only")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Summary Statistics

# COMMAND ----------

# Get collection statistics
pipeline = [
    {
        "$group": {
            "_id": "$date",
            "record_count": {"$sum": 1},
            "unique_cards": {"$addToSet": "$scryfall_id"}
        }
    },
    {
        "$project": {
            "date": "$_id",
            "record_count": 1,
            "unique_cards": {"$size": "$unique_cards"}
        }
    },
    {"$sort": {"date": -1}},
    {"$limit": 7}
]

summary = list(pricing_collection.aggregate(pipeline))

print("\n📊 Pricing Data Summary (Last 7 Days)")
print("=" * 60)
print(f"{'Date':<12} {'Cards':<10} {'Records':<12} {'Avg Records/Card':<15}")
print("-" * 60)

for row in summary:
    date = row.get("date", "N/A")
    cards = row.get("unique_cards", 0)
    records = row.get("record_count", 0)
    avg_per_card = records / cards if cards > 0 else 0
    print(f"{date:<12} {cards:<10,} {records:<12,} {avg_per_card:<15.1f}")

print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: Trigger dbt Transformation (Optional)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Option A: Run dbt from Databricks
# MAGIC 
# MAGIC ```python
# MAGIC # Uncomment to run dbt transformation immediately after ingestion
# MAGIC # 
# MAGIC # import subprocess
# MAGIC # 
# MAGIC # print("🔄 Triggering dbt transformation...")
# MAGIC # result = subprocess.run(
# MAGIC #     ["dbt", "run", "--project-dir", "/Workspace/mtgecorec/dbt_pricing"],
# MAGIC #     capture_output=True,
# MAGIC #     text=True
# MAGIC # )
# MAGIC # 
# MAGIC # if result.returncode == 0:
# MAGIC #     print("✅ dbt transformation completed")
# MAGIC #     print(result.stdout)
# MAGIC # else:
# MAGIC #     print("❌ dbt transformation failed")
# MAGIC #     print(result.stderr)
# MAGIC ```
# MAGIC 
# MAGIC ### Option B: Schedule as Separate Job
# MAGIC 
# MAGIC **Recommended**: Create two Databricks jobs:
# MAGIC 1. **Job 1** (1:00 AM): Run this notebook (ingest from Scryfall)
# MAGIC 2. **Job 2** (1:30 AM): Run dbt transformation (MongoDB → Delta Lake)
# MAGIC 
# MAGIC This allows independent monitoring and retry logic.

# COMMAND ----------

# Cleanup
mongo_client.close()
print("\n✅ Pipeline complete!")
print(f"⏭️ Next step: Run dbt transformation to load into Delta Lake")
