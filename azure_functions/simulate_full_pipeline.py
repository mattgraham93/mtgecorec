#!/usr/bin/env python3
"""
Local simulation of the full auto-chaining pipeline
Process all remaining cards in batches
"""

import os
import sys
import time
from datetime import datetime

# Load .env
with open('/workspaces/mtgecorec/.env', 'r') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

sys.path.insert(0, '/workspaces/mtgecorec/azure_functions')
from pricing_pipeline import run_pricing_pipeline_azure_function, MTGPricingPipeline

def simulate_full_pipeline(batch_size=20000, max_batches=10):
    """Simulate the full auto-chaining pipeline locally"""
    print("🚀 Starting Full Pipeline Simulation")
    print("=" * 50)
    
    target_date = datetime.now().date().isoformat()
    batch_count = 0
    total_cards_processed = 0
    total_records_created = 0
    start_time = time.time()
    
    while batch_count < max_batches:
        batch_count += 1
        batch_start = time.time()
        
        print(f"\n📦 Batch {batch_count} - Processing up to {batch_size:,} cards...")
        
        # Run pipeline for this batch
        result = run_pricing_pipeline_azure_function(
            target_date=target_date,
            max_cards=batch_size
        )
        
        # Extract results
        cards_processed = result.get('cards_processed', 0)
        records_created = result.get('records_created', 0)
        status = result.get('status', 'unknown')
        
        total_cards_processed += cards_processed
        total_records_created += records_created
        
        batch_time = time.time() - batch_start
        print(f"   Cards processed: {cards_processed:,}")
        print(f"   Records created: {records_created:,}")
        print(f"   Batch time: {batch_time:.1f}s")
        print(f"   Status: {status}")
        
        # Check if we should continue (same logic as Azure Functions)
        pipeline = MTGPricingPipeline()
        total_cards = pipeline.cards_collection.count_documents({})
        unique_cards_with_pricing = len(set(pipeline.pricing_collection.distinct('scryfall_id', {'date': target_date})))
        remaining = total_cards - unique_cards_with_pricing
        
        print(f"   Remaining cards: {remaining:,}")
        
        # Continue if more than 1000 cards remain and we processed a reasonable number
        if remaining <= 1000 or cards_processed < batch_size * 0.1:
            print(f"🎉 Pipeline complete! Processed {remaining:,} remaining cards or low batch yield.")
            break
        
        print(f"   ➡️  Continuing to next batch...")
        time.sleep(2)  # Brief pause between batches
    
    total_time = time.time() - start_time
    
    print(f"\n📊 Final Summary:")
    print(f"Batches processed: {batch_count}")
    print(f"Total cards processed: {total_cards_processed:,}")
    print(f"Total records created: {total_records_created:,}")
    print(f"Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    
    if total_cards_processed > 0:
        print(f"Average cards/second: {total_cards_processed/total_time:.1f}")
        print(f"Average records per card: {total_records_created/total_cards_processed:.1f}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-size', type=int, default=5000, help='Cards per batch (default: 5000 for local testing)')
    parser.add_argument('--max-batches', type=int, default=20, help='Maximum batches to process')
    args = parser.parse_args()
    
    print(f"Configuration: {args.batch_size:,} cards per batch, max {args.max_batches} batches")
    simulate_full_pipeline(batch_size=args.batch_size, max_batches=args.max_batches)