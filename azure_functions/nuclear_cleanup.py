#!/usr/bin/env python3
"""Nuclear option - delete problem dates and rebuild clean"""

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

def nuclear_cleanup():
    """Delete all duplicated dates - we'll rebuild them clean"""
    pipeline = MTGPricingPipeline()
    
    print("☢️  NUCLEAR CLEANUP - Deleting problem dates...")
    
    # Check current status
    print("\n📊 Before cleanup:")
    total_before = pipeline.pricing_collection.count_documents({})
    print(f"Total records: {total_before:,}")
    
    # Delete the problem dates with massive duplicates
    problem_dates = ['2025-12-16']
    
    for date in problem_dates:
        count = pipeline.pricing_collection.count_documents({'date': date})
        print(f"  {date}: {count:,} records")
        
        if count > 100000:  # Only delete if it's clearly duplicated
            print(f"  🗑️  Deleting {date} (duplicated)...")
            
            # Delete in chunks to avoid timeouts
            deleted_total = 0
            chunk_size = 10000
            
            while True:
                # Find a chunk to delete
                records_to_delete = list(
                    pipeline.pricing_collection.find({'date': date}, {'_id': 1})
                    .limit(chunk_size)
                )
                
                if not records_to_delete:
                    break
                    
                # Delete this chunk
                ids = [r['_id'] for r in records_to_delete]
                result = pipeline.pricing_collection.delete_many({'_id': {'$in': ids}})
                
                deleted_total += result.deleted_count
                print(f"    Deleted {deleted_total:,} records...")
                
                if len(records_to_delete) < chunk_size:
                    break
            
            print(f"  ✅ Deleted {deleted_total:,} records for {date}")
        else:
            print(f"  ✅ Keeping {date} (normal size)")
    
    # Final status
    print("\n📊 After cleanup:")
    total_after = pipeline.pricing_collection.count_documents({})
    print(f"Total records: {total_after:,}")
    print(f"Freed up: {total_before - total_after:,} records")
    
    # Show remaining dates
    remaining_dates = list(pipeline.pricing_collection.aggregate([
        {'$group': {'_id': '$date', 'count': {'$sum': 1}}},
        {'$sort': {'_id': -1}},
        {'$limit': 5}
    ]))
    
    print(f"\nRemaining dates:")
    for date_info in remaining_dates:
        print(f"  {date_info['_id']}: {date_info['count']:,} records")
    
    print(f"\n🎉 Cleanup complete! Database is now clean and ready for fresh data.")

if __name__ == "__main__":
    nuclear_cleanup()