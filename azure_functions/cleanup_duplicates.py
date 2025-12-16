#!/usr/bin/env python3
"""
Cleanup duplicate pricing records in CosmosDB
"""
import sys, os
sys.path.insert(0, '/workspaces/mtgecorec/azure_functions')

# Load .env
with open('/workspaces/mtgecorec/.env', 'r') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

from pricing_pipeline import MTGPricingPipeline

def cleanup_duplicates_test():
    """Test cleanup on 2025-12-16 data only"""
    pipeline = MTGPricingPipeline()
    
    print("🧪 Testing duplicate cleanup...")
    
    # Check original count
    original_count = pipeline.pricing_collection.count_documents({'date': '2025-12-16'})
    print(f"Original count for 2025-12-16: {original_count:,}")
    
    # Get unique combinations (keeping newest based on ObjectId)
    print("📊 Finding unique records...")
    
    unique_records = []
    seen_combinations = set()
    
    # Get all records for 2025-12-16, sorted by _id (newest first)
    records = pipeline.pricing_collection.find(
        {'date': '2025-12-16'}
    ).sort('_id', -1)
    
    for record in records:
        combo_key = (record['scryfall_id'], record['date'], record['price_type'], record.get('finish', 'nonfoil'))
        
        if combo_key not in seen_combinations:
            seen_combinations.add(combo_key)
            unique_records.append(record)
    
    print(f"Unique records found: {len(unique_records):,}")
    print(f"Duplicates to remove: {original_count - len(unique_records):,}")
    
    return len(unique_records)

def cleanup_duplicates_full():
    """Full cleanup - removes all duplicates, keeps newest - batched approach"""
    pipeline = MTGPricingPipeline()
    
    print("🔧 Starting full duplicate cleanup...")
    
    # Get total count before
    original_total = pipeline.pricing_collection.count_documents({})
    print(f"Total records before cleanup: {original_total:,}")
    
    # Create a temporary collection for clean data
    clean_collection = pipeline.db['card_pricing_daily_clean']
    clean_collection.drop()  # Remove if exists
    
    # Process in small batches using direct deletion approach
    print("📊 Processing records in small batches...")
    
    BATCH_SIZE = 10000  # Process 10k records at a time
    
    try:
        # Count total for progress tracking
        total_records = pipeline.pricing_collection.count_documents({})
        processed = 0
        
        # Process collection in batches
        cursor = pipeline.pricing_collection.find({}).sort('_id', 1).limit(BATCH_SIZE)
        
        while True:
            batch = list(cursor)
            if not batch:
                break
                
            print(f"Processing batch {processed//BATCH_SIZE + 1}, records {processed+1}-{processed+len(batch)}")
            
            # Group by unique key and keep only the first (oldest by _id)
            unique_docs = {}
            duplicates_to_remove = []
            
            for doc in batch:
                key = (
                    doc.get('scryfall_id'),
                    doc.get('date'), 
                    doc.get('price_type'),
                    doc.get('finish', 'nonfoil')
                )
                
                if key not in unique_docs:
                    unique_docs[key] = doc
                    # Add to clean collection
                    try:
                        clean_collection.insert_one(doc)
                    except Exception:
                        pass  # Skip if already exists (shouldn't happen but safety)
                else:
                    # This is a duplicate, mark for removal
                    duplicates_to_remove.append(doc['_id'])
            
            # Remove duplicates from original collection
            if duplicates_to_remove:
                pipeline.pricing_collection.delete_many({'_id': {'$in': duplicates_to_remove}})
                print(f"  Removed {len(duplicates_to_remove)} duplicates, kept {len(unique_docs)} unique")
            
            processed += len(batch)
            
            # Get next batch
            if batch:
                last_id = batch[-1]['_id']
                cursor = pipeline.pricing_collection.find({'_id': {'$gt': last_id}}).sort('_id', 1).limit(BATCH_SIZE)
            else:
                break
        
        # Check final results
        clean_count = clean_collection.count_documents({})
        print(f"\n🎉 Cleanup complete!")
        print(f"Clean records created: {clean_count:,}")
        print(f"Duplicates removed: {original_total - clean_count:,}")
        
        return clean_count
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        return 0

def create_unique_index():
    """Create unique index to prevent future duplicates"""
    pipeline = MTGPricingPipeline()
    
    print("📋 Creating unique index...")
    try:
        result = pipeline.pricing_collection.create_index(
            [
                ('scryfall_id', 1),
                ('date', 1), 
                ('price_type', 1),
                ('finish', 1)
            ],
            unique=True
        )
        print(f"✅ Unique index created: {result}")
        return True
    except Exception as e:
        print(f"❌ Index creation failed: {e}")
        return False

def swap_collections():
    """Backup original and replace with clean version"""
    pipeline = MTGPricingPipeline()
    
    print("🔄 Swapping collections...")
    
    # Rename original to backup
    try:
        pipeline.db['card_pricing_daily'].rename('card_pricing_daily_backup')
        print("✅ Original collection backed up")
        
        # Rename clean to original
        pipeline.db['card_pricing_daily_clean'].rename('card_pricing_daily')
        print("✅ Clean collection is now active")
        
        return True
    except Exception as e:
        print(f"❌ Collection swap failed: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Cleanup duplicate pricing records')
    parser.add_argument('action', choices=['test', 'cleanup', 'index', 'swap'], 
                        help='Action to perform')
    
    args = parser.parse_args()
    
    if args.action == 'test':
        cleanup_duplicates_test()
    elif args.action == 'cleanup':
        cleanup_duplicates_full()
    elif args.action == 'index':
        create_unique_index()
    elif args.action == 'swap':
        swap_collections()