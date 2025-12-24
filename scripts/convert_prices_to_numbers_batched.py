#!/usr/bin/env python3
"""
Convert string prices to numeric doubles in MongoDB - BATCHED VERSION
Processes records in small batches to avoid timeouts
"""

import os
import sys
import time
from typing import Dict, Any

# Add project paths
sys.path.append('/workspaces/mtgecorec')
sys.path.append('/workspaces/mtgecorec/core')

from core.data_engine.cosmos_driver import get_mongo_client, get_collection
from dotenv import load_dotenv

def convert_prices_to_numbers_batched():
    """Convert string prices to numeric doubles in batches"""
    
    print("🔧 Converting string prices to numeric doubles (BATCHED)...")
    print("=" * 60)
    
    # Load environment
    load_dotenv()
    
    # Connect to database
    client = get_mongo_client()
    database_name = "mtgecorec"
    cards_collection = get_collection(client, database_name, "cards")
    
    print(f"✅ Connected to database: {database_name}")
    
    # Get stats
    total_cards = cards_collection.count_documents({})
    cards_with_prices = cards_collection.count_documents({"prices": {"$exists": True}})
    
    print(f"📊 Total cards: {total_cards:,}")
    print(f"📊 Cards with prices field: {cards_with_prices:,}")
    
    # Check sample for string prices
    string_price_sample = cards_collection.find_one({
        "$or": [
            {"prices.usd": {"$type": "string"}},
            {"prices.usd_foil": {"$type": "string"}},
            {"prices.eur": {"$type": "string"}},
            {"prices.eur_foil": {"$type": "string"}}
        ]
    })
    
    if not string_price_sample:
        print("✅ No string prices found - conversion already complete!")
        client.close()
        return
    
    print("🔍 Found string prices to convert:")
    if "prices" in string_price_sample:
        for key, value in string_price_sample["prices"].items():
            if value and isinstance(value, str):
                print(f"  {key}: '{value}' (string) -> {float(value)} (number)")
    
    # Process in batches
    batch_size = 1000
    total_processed = 0
    total_modified = 0
    
    print(f"\n🚀 Processing in batches of {batch_size} documents...")
    
    try:
        # Find all documents with string prices and process in batches
        cursor = cards_collection.find(
            {
                "$or": [
                    {"prices.usd": {"$type": "string"}},
                    {"prices.usd_foil": {"$type": "string"}},
                    {"prices.usd_etched": {"$type": "string"}},
                    {"prices.eur": {"$type": "string"}},
                    {"prices.eur_foil": {"$type": "string"}},
                    {"prices.tix": {"$type": "string"}}
                ]
            },
            {"_id": 1, "prices": 1}
        ).batch_size(batch_size)
        
        batch_count = 0
        for batch_docs in batch_cursor(cursor, batch_size):
            batch_count += 1
            
            # Process this batch
            batch_updates = []
            for doc in batch_docs:
                doc_id = doc["_id"]
                prices = doc.get("prices", {})
                
                # Build update for this document
                update_doc = {}
                
                for price_field in ["usd", "usd_foil", "usd_etched", "eur", "eur_foil", "tix"]:
                    if price_field in prices and isinstance(prices[price_field], str):
                        try:
                            numeric_value = float(prices[price_field])
                            update_doc[f"prices.{price_field}"] = numeric_value
                        except (ValueError, TypeError):
                            # Skip invalid values
                            pass
                
                if update_doc:
                    batch_updates.append({
                        "filter": {"_id": doc_id},
                        "update": {"$set": update_doc}
                    })
            
            if batch_updates:
                # Execute batch update using UpdateOne operations
                from pymongo import UpdateOne
                
                operations = []
                for update_op in batch_updates:
                    operations.append(
                        UpdateOne(
                            update_op["filter"],
                            update_op["update"]
                        )
                    )
                
                if operations:
                    result = cards_collection.bulk_write(operations, ordered=False)
                    total_modified += result.modified_count
                    
            total_processed += len(batch_docs)
            
            print(f"📈 Batch {batch_count}: Processed {len(batch_docs)} docs, "
                  f"Total processed: {total_processed:,}, Modified: {total_modified:,}")
            
            # Small delay to avoid overwhelming the database
            time.sleep(0.1)
        
        print(f"\n✅ Conversion completed!")
        print(f"📊 Total documents processed: {total_processed:,}")
        print(f"📊 Total documents modified: {total_modified:,}")
        
        # Verify conversion
        print(f"\n🧪 Testing numeric queries...")
        high_value_count = cards_collection.count_documents({
            "$or": [
                {"prices.usd": {"$gte": 1.0}},
                {"prices.usd_foil": {"$gte": 1.0}},
                {"prices.eur": {"$gte": 0.9}},
                {"prices.eur_foil": {"$gte": 0.9}}
            ]
        })
        
        print(f"🎯 Cards with value ≥$1: {high_value_count:,}")
        
        # Check if any string prices remain
        remaining_strings = cards_collection.count_documents({
            "$or": [
                {"prices.usd": {"$type": "string"}},
                {"prices.usd_foil": {"$type": "string"}},
                {"prices.eur": {"$type": "string"}},
                {"prices.eur_foil": {"$type": "string"}}
            ]
        })
        
        print(f"📊 Remaining string prices: {remaining_strings:,}")
        
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        raise
    
    finally:
        client.close()
        print(f"\n🔒 Database connection closed")
    
    print(f"\n" + "=" * 60)
    print("🎉 BATCHED PRICE CONVERSION COMPLETE!")
    if remaining_strings == 0:
        print("✅ All string prices converted to numeric doubles")
        print("✅ MongoDB queries can now use direct numeric comparisons")
    else:
        print(f"⚠️ {remaining_strings} string prices still remain")

def batch_cursor(cursor, batch_size):
    """Yield batches of documents from cursor"""
    batch = []
    for doc in cursor:
        batch.append(doc)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

if __name__ == "__main__":
    convert_prices_to_numbers_batched()