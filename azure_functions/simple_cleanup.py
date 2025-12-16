#!/usr/bin/env python3
"""Simple direct duplicate cleanup for CosmosDB limitations"""

import os
import sys
from datetime import datetime
from pricing_pipeline import MTGPricingPipeline

def direct_duplicate_cleanup():
    """Direct deletion approach to handle CosmosDB limitations"""
    pipeline = MTGPricingPipeline()
    
    print("🔧 Starting direct duplicate cleanup...")
    
    # Get total count before
    original_total = pipeline.pricing_collection.count_documents({})
    print(f"Total records before cleanup: {original_total:,}")
    
    # Find duplicates using aggregation
    print("📊 Finding duplicates...")
    
    duplicate_pipeline = [
        {'$group': {
            '_id': {
                'scryfall_id': '$scryfall_id',
                'date': '$date', 
                'price_type': '$price_type',
                'finish': {'$ifNull': ['$finish', 'nonfoil']}
            },
            'count': {'$sum': 1},
            'docs': {'$push': '$_id'},
            'first_doc': {'$first': '$_id'}
        }},
        {'$match': {'count': {'$gt': 1}}},  # Only groups with duplicates
        {'$project': {
            'duplicates': {
                '$slice': ['$docs', 1, {'$subtract': [{'$size': '$docs'}, 1]}]  # All except first
            }
        }}
    ]
    
    duplicates_found = list(pipeline.pricing_collection.aggregate(duplicate_pipeline))
    total_duplicate_groups = len(duplicates_found)
    
    print(f"Found {total_duplicate_groups:,} groups with duplicates")
    
    # Delete duplicates in batches
    total_deleted = 0
    BATCH_SIZE = 100
    
    for i in range(0, total_duplicate_groups, BATCH_SIZE):
        batch = duplicates_found[i:i + BATCH_SIZE]
        
        # Collect all duplicate IDs to delete
        ids_to_delete = []
        for dup_group in batch:
            ids_to_delete.extend(dup_group['duplicates'])
        
        if ids_to_delete:
            # Delete this batch of duplicates
            result = pipeline.pricing_collection.delete_many({'_id': {'$in': ids_to_delete}})
            deleted_count = result.deleted_count
            total_deleted += deleted_count
            
            print(f"Batch {i//BATCH_SIZE + 1}: Deleted {deleted_count:,} duplicates")
    
    # Final count
    final_total = pipeline.pricing_collection.count_documents({})
    print(f"\n🎉 Cleanup complete!")
    print(f"Records before: {original_total:,}")
    print(f"Records after: {final_total:,}")
    print(f"Total deleted: {total_deleted:,}")
    
    return total_deleted

if __name__ == "__main__":
    direct_duplicate_cleanup()