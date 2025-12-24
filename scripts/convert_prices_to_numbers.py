#!/usr/bin/env python3
"""
Convert string prices to numeric doubles in MongoDB
This fixes the data type issue permanently so we don't need $toDouble workarounds
"""

import os
import sys
from typing import Dict, Any

# Add project paths
sys.path.append('/workspaces/mtgecorec')
sys.path.append('/workspaces/mtgecorec/core')

from core.data_engine.cosmos_driver import get_mongo_client, get_collection
from dotenv import load_dotenv

def convert_prices_to_numbers():
    """Convert string prices to numeric doubles in the cards collection"""
    
    print("🔧 Converting string prices to numeric doubles...")
    print("=" * 60)
    
    # Load environment
    load_dotenv()
    
    # Connect to database
    client = get_mongo_client()
    database_name = "mtgecorec"
    cards_collection = get_collection(client, database_name, "cards")
    
    print(f"✅ Connected to database: {database_name}")
    
    # Get initial stats
    total_cards = cards_collection.count_documents({})
    cards_with_prices = cards_collection.count_documents({"prices": {"$exists": True}})
    
    print(f"📊 Total cards: {total_cards:,}")
    print(f"📊 Cards with prices field: {cards_with_prices:,}")
    
    # Check current data types
    print("\n🔍 Checking current data types...")
    sample_card = cards_collection.find_one({"prices": {"$exists": True}})
    if sample_card and "prices" in sample_card:
        prices = sample_card["prices"]
        print("Sample prices structure:")
        for key, value in prices.items():
            if value is not None:
                print(f"  {key}: {value} (type: {type(value).__name__})")
    
    # MongoDB aggregation pipeline to convert string prices to doubles
    conversion_pipeline = [
        {
            "$set": {
                "prices.usd": {
                    "$cond": {
                        "if": {"$eq": [{"$type": "$prices.usd"}, "string"]},
                        "then": {"$toDouble": "$prices.usd"},
                        "else": "$prices.usd"
                    }
                },
                "prices.usd_foil": {
                    "$cond": {
                        "if": {"$eq": [{"$type": "$prices.usd_foil"}, "string"]},
                        "then": {"$toDouble": "$prices.usd_foil"},
                        "else": "$prices.usd_foil"
                    }
                },
                "prices.usd_etched": {
                    "$cond": {
                        "if": {"$eq": [{"$type": "$prices.usd_etched"}, "string"]},
                        "then": {"$toDouble": "$prices.usd_etched"},
                        "else": "$prices.usd_etched"
                    }
                },
                "prices.eur": {
                    "$cond": {
                        "if": {"$eq": [{"$type": "$prices.eur"}, "string"]},
                        "then": {"$toDouble": "$prices.eur"},
                        "else": "$prices.eur"
                    }
                },
                "prices.eur_foil": {
                    "$cond": {
                        "if": {"$eq": [{"$type": "$prices.eur_foil"}, "string"]},
                        "then": {"$toDouble": "$prices.eur_foil"},
                        "else": "$prices.eur_foil"
                    }
                },
                "prices.tix": {
                    "$cond": {
                        "if": {"$eq": [{"$type": "$prices.tix"}, "string"]},
                        "then": {"$toDouble": "$prices.tix"},
                        "else": "$prices.tix"
                    }
                }
            }
        }
    ]
    
    print(f"\n🚀 Running conversion on {cards_with_prices:,} cards...")
    print("This may take a few minutes for large collections...")
    
    try:
        # Run the conversion
        result = cards_collection.update_many(
            {"prices": {"$exists": True}},
            conversion_pipeline
        )
        
        print(f"✅ Conversion completed!")
        print(f"📊 Documents matched: {result.matched_count:,}")
        print(f"📊 Documents modified: {result.modified_count:,}")
        
        # Verify conversion worked
        print(f"\n🔍 Verifying conversion...")
        sample_card_after = cards_collection.find_one({"prices": {"$exists": True}})
        if sample_card_after and "prices" in sample_card_after:
            prices_after = sample_card_after["prices"]
            print("Sample prices after conversion:")
            for key, value in prices_after.items():
                if value is not None:
                    print(f"  {key}: {value} (type: {type(value).__name__})")
        
        # Test a numeric query to confirm it works
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
        print(f"✅ Numeric queries now work without $toDouble!")
        
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        raise
    
    finally:
        client.close()
        print(f"\n🔒 Database connection closed")
    
    print(f"\n" + "=" * 60)
    print("🎉 PRICE CONVERSION COMPLETE!")
    print("✅ All string prices converted to numeric doubles")
    print("✅ MongoDB queries can now use direct numeric comparisons")
    print("✅ No more need for $toDouble workarounds")

if __name__ == "__main__":
    convert_prices_to_numbers()