"""
Validate MongoDB Connection and Data Structure
Shows sample unpivoted pricing data before transformation
"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime, timedelta

# Load environment
load_dotenv('/workspaces/mtgecorec/.env')

def validate_mongodb_connection():
    """Test MongoDB connection and show sample data"""
    
    print("=" * 60)
    print("MongoDB → Databricks Validation")
    print("=" * 60)
    
    # Connect to MongoDB
    COSMOS_CONNECTION_STRING = os.getenv('COSMOS_CONNECTION_STRING')
    if not COSMOS_CONNECTION_STRING:
        print("❌ COSMOS_CONNECTION_STRING not found in .env")
        return False
    
    try:
        client = MongoClient(COSMOS_CONNECTION_STRING, serverSelectionTimeoutMS=5000)
        db = client['mtgecorec']
        collection = db['card_pricing_daily']
        
        # Test connection
        db.command('ping')
        print("✅ Connected to MongoDB (Cosmos DB)")
        
        # Minimal stats (avoid expensive queries that hit Cosmos DB rate limits)
        print(f"\n📊 Collection Validation:")
        print(f"   ✅ Can connect to card_pricing_daily collection")
        
        # Show sample unpivoted records (minimal to avoid rate limiting)
        print(f"\n📋 Sample Unpivoted Records:")
        print("-" * 60)
        
        sample_docs = list(collection.find().limit(3))
        if sample_docs:
            print(f"✅ Successfully retrieved {len(sample_docs)} sample documents\n")
            
            for i, doc in enumerate(sample_docs, 1):
                card_name = doc.get('card_name', 'Unknown')
                price_type = doc.get('price_type', 'Unknown')
                price_value = doc.get('price_value', 0)
                date = doc.get('date', 'Unknown')
                print(f"  {i}. {card_name[:25]:25s} | {date} | {price_type:12s} | ${price_value}")
            
            print("\n🔄 Data Format:")
            print(f"   Unpivoted: Each card has 6 rows (usd, usd_foil, usd_etched, eur, eur_foil, tix)")
            print(f"   Sync will pivot to: 1 row per card per day")
        
        print("\n✅ MongoDB validation complete!")
        print("   Ready to run sync script: python scripts/sync_mongo_to_databricks_staging.py")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = validate_mongodb_connection()
    exit(0 if success else 1)
