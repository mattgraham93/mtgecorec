#!/usr/bin/env python3
"""Simple cleanup for test dates and duplicates"""

import os
import sys

# Load environment
with open('/workspaces/mtgecorec/.env', 'r') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

sys.path.insert(0, '/workspaces/mtgecorec/azure_functions')
from pricing_pipeline import MTGPricingPipeline

def delete_test_dates():
    """Delete test dates we created"""
    pipeline = MTGPricingPipeline()
    
    test_dates = ['2025-12-17', '2025-12-18', '2025-12-19', '2025-12-20']
    
    for date in test_dates:
        print(f"🗑️  Deleting records for {date}...")
        count_before = pipeline.pricing_collection.count_documents({'date': date})
        
        if count_before > 0:
            # Delete in small batches to avoid timeouts
            deleted_total = 0
            while True:
                # Find a small batch
                records = list(pipeline.pricing_collection.find({'date': date}).limit(100))
                if not records:
                    break
                    
                # Delete these records
                ids_to_delete = [r['_id'] for r in records]
                result = pipeline.pricing_collection.delete_many({'_id': {'$in': ids_to_delete}})
                deleted_total += result.deleted_count
                
                print(f"  Deleted {result.deleted_count} records...")
                
                if result.deleted_count == 0:
                    break
                    
            print(f"✅ Deleted {deleted_total} records for {date}")
        else:
            print(f"✅ No records found for {date}")

def check_current_status():
    """Check what dates we have now"""
    pipeline = MTGPricingPipeline()
    
    print("\n📊 Current database status:")
    
    # Get date counts
    date_counts = list(pipeline.pricing_collection.aggregate([
        {'$group': {'_id': '$date', 'count': {'$sum': 1}}},
        {'$sort': {'_id': -1}}
    ]))
    
    for date_info in date_counts[:10]:  # Show top 10 dates
        print(f"  {date_info['_id']}: {date_info['count']:,} records")
    
    total_records = pipeline.pricing_collection.count_documents({})
    print(f"\nTotal records: {total_records:,}")

if __name__ == "__main__":
    print("🧹 Quick cleanup starting...")
    
    # Step 1: Check current status
    check_current_status()
    
    # Step 2: Delete test dates
    print("\n" + "="*50)
    delete_test_dates()
    
    # Step 3: Check status after cleanup
    print("\n" + "="*50)
    check_current_status()
    
    print("\n🎉 Quick cleanup complete!")