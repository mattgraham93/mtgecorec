#!/usr/bin/env python3
"""Targeted duplicate cleanup for 2025-12-16"""

import os
import sys
from collections import defaultdict

# Load environment
with open('/workspaces/mtgecorec/.env', 'r') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

sys.path.insert(0, '/workspaces/mtgecorec/azure_functions')
from pricing_pipeline import MTGPricingPipeline

def clean_duplicates_for_date(target_date='2025-12-16'):
    """Clean duplicates for a specific date using small batches"""
    pipeline = MTGPricingPipeline()
    
    print(f"🔧 Cleaning duplicates for {target_date}...")
    
    # Count before
    original_count = pipeline.pricing_collection.count_documents({'date': target_date})
    print(f"Original count: {original_count:,}")
    
    # Process in small scryfall_id batches to avoid memory issues
    BATCH_SIZE = 1000  # Process 1000 unique scryfall_ids at a time
    
    # Get all unique scryfall_ids for this date
    unique_ids = pipeline.pricing_collection.distinct('scryfall_id', {'date': target_date})
    total_ids = len(unique_ids)
    print(f"Found {total_ids:,} unique scryfall_ids to process")
    
    total_deleted = 0
    
    # Process in batches
    for i in range(0, total_ids, BATCH_SIZE):
        batch_ids = unique_ids[i:i + BATCH_SIZE]
        print(f"Processing batch {i//BATCH_SIZE + 1}, IDs {i+1}-{min(i+BATCH_SIZE, total_ids)}")
        
        # For each scryfall_id in this batch, keep only the newest record per price_type+finish
        for scryfall_id in batch_ids:
            
            # Get all records for this scryfall_id on this date
            records = list(pipeline.pricing_collection.find({
                'scryfall_id': scryfall_id,
                'date': target_date
            }).sort('_id', -1))  # Newest first
            
            if len(records) <= 5:  # Should have ~5 records (USD, USD foil, EUR, EUR foil, TIX)
                continue
                
            # Group by price_type + finish combination
            seen_combinations = set()
            records_to_keep = []
            records_to_delete = []
            
            for record in records:
                combo = (record.get('price_type'), record.get('finish', 'nonfoil'))
                
                if combo not in seen_combinations:
                    seen_combinations.add(combo)
                    records_to_keep.append(record['_id'])
                else:
                    records_to_delete.append(record['_id'])
            
            # Delete duplicates for this card
            if records_to_delete:
                result = pipeline.pricing_collection.delete_many({
                    '_id': {'$in': records_to_delete}
                })
                total_deleted += result.deleted_count
        
        print(f"  Processed {len(batch_ids)} cards, deleted {total_deleted} duplicates so far")
    
    # Final count
    final_count = pipeline.pricing_collection.count_documents({'date': target_date})
    print(f"\n✅ Cleanup complete for {target_date}!")
    print(f"Before: {original_count:,}")
    print(f"After: {final_count:,}")
    print(f"Deleted: {total_deleted:,}")
    print(f"Reduction: {((original_count - final_count) / original_count * 100):.1f}%")

if __name__ == "__main__":
    clean_duplicates_for_date('2025-12-16')