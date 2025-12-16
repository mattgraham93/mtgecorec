#!/usr/bin/env python3
"""
Clean up duplicate records and remove test dates
"""
import os
import sys
from datetime import datetime

# Load environment
sys.path.insert(0, '/workspaces/mtgecorec/azure_functions')
with open('/workspaces/mtgecorec/.env', 'r') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

from pricing_pipeline import MTGPricingPipeline

def delete_test_dates():
    """Remove test dates we created (2025-12-17, 18, 19, 20)"""
    pipeline = MTGPricingPipeline()
    
    test_dates = ['2025-12-17', '2025-12-18', '2025-12-19', '2025-12-20']
    
    print("🗑️  Removing test dates...")
    total_deleted = 0
    
    for date in test_dates:
        # Get records for this date
        records = list(pipeline.pricing_collection.find({'date': date}, {'_id': 1}))
        if records:
            print(f"  🔄 Deleting {len(records)} records from {date}...")
            deleted_count = 0
            
            # Delete in small batches to avoid CosmosDB limits
            BATCH_SIZE = 100
            for i in range(0, len(records), BATCH_SIZE):
                batch = records[i:i + BATCH_SIZE]
                ids_to_delete = [doc['_id'] for doc in batch]
                
                # Delete individually to avoid retryable write issues
                for doc_id in ids_to_delete:
                    try:
                        pipeline.pricing_collection.delete_one({'_id': doc_id})
                        deleted_count += 1
                    except Exception as e:
                        print(f"    ⚠️  Failed to delete {doc_id}: {e}")
            
            print(f"  ✅ Deleted {deleted_count:,} records from {date}")
            total_deleted += deleted_count
        else:
            print(f"  ➖ No records found for {date}")
    
    print(f"🎯 Total test records deleted: {total_deleted:,}")
    return total_deleted

def clean_current_duplicates():
    """Clean duplicates from 2025-12-16 using direct deletion"""
    pipeline = MTGPricingPipeline()
    
    target_date = '2025-12-16'
    
    print(f"🔧 Cleaning duplicates for {target_date}...")
    
    # Get original count
    original_count = pipeline.pricing_collection.count_documents({'date': target_date})
    print(f"Original records for {target_date}: {original_count:,}")
    
    if original_count == 0:
        print("No records to clean!")
        return 0
    
    # Find duplicate groups using aggregation in smaller chunks
    print("📊 Finding duplicate groups...")
    
    duplicate_pipeline = [
        {'$match': {'date': target_date}},
        {'$group': {
            '_id': {
                'scryfall_id': '$scryfall_id',
                'date': '$date', 
                'price_type': '$price_type',
                'finish': {'$ifNull': ['$finish', 'nonfoil']}
            },
            'count': {'$sum': 1},
            'docs': {'$push': '$_id'},
        }},
        {'$match': {'count': {'$gt': 1}}},  # Only groups with duplicates
        {'$project': {
            'duplicates_to_delete': {
                '$slice': ['$docs', 1, {'$subtract': [{'$size': '$docs'}, 1]}]  # All except first
            }
        }},
        {'$limit': 10000}  # Process in chunks of 10K duplicate groups
    ]
    
    total_deleted = 0
    batch_num = 0
    
    while True:
        batch_num += 1
        print(f"Processing duplicate batch {batch_num}...")
        
        # Get a batch of duplicate groups
        duplicate_groups = list(pipeline.pricing_collection.aggregate(duplicate_pipeline + [{'$skip': (batch_num-1) * 10000}]))
        
        if not duplicate_groups:
            print("No more duplicate groups found")
            break
        
        # Collect all IDs to delete from this batch
        ids_to_delete = []
        for group in duplicate_groups:
            ids_to_delete.extend(group['duplicates_to_delete'])
        
        if ids_to_delete:
            # Delete duplicates individually to avoid CosmosDB retryable write issues
            deleted_in_batch = 0
            for doc_id in ids_to_delete:
                try:
                    result = pipeline.pricing_collection.delete_one({'_id': doc_id})
                    if result.deleted_count > 0:
                        deleted_in_batch += 1
                except Exception:
                    pass  # Skip if already deleted or other error
            
            total_deleted += deleted_in_batch
            print(f"  Batch {batch_num}: Deleted {deleted_in_batch:,} duplicates")
        
        # If we got less than 10K groups, we're done
        if len(duplicate_groups) < 10000:
            break
    
    # Final count
    final_count = pipeline.pricing_collection.count_documents({'date': target_date})
    
    print(f"\n🎉 Duplicate cleanup complete!")
    print(f"Records before: {original_count:,}")
    print(f"Records after: {final_count:,}")
    print(f"Duplicates deleted: {total_deleted:,}")
    print(f"Compression ratio: {original_count / final_count:.1f}:1")
    
    return total_deleted

def main():
    print("🧹 Starting comprehensive cleanup...")
    print("=" * 50)
    
    # Step 1: Remove test dates
    test_deleted = delete_test_dates()
    
    print("\n" + "=" * 50)
    
    # Step 2: Clean current duplicates
    duplicate_deleted = clean_current_duplicates()
    
    print("\n" + "=" * 50)
    print(f"🏆 CLEANUP COMPLETE!")
    print(f"Test records deleted: {test_deleted:,}")
    print(f"Duplicate records deleted: {duplicate_deleted:,}")
    print(f"Total space saved: {test_deleted + duplicate_deleted:,} records")

if __name__ == "__main__":
    main()