#!/usr/bin/env python3
"""
Local development and testing for Azure Functions
Run this instead of deploying to Azure for faster development
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_local_settings():
    """Load .env file, local.settings.json, or use existing environment variables"""
    
    # First, try to load .env file from root directory
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        print("✅ Loading .env file from root directory")
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
    
    # Then try local.settings.json
    try:
        with open('local.settings.json', 'r') as f:
            settings = json.load(f)
            # Set environment variables
            for key, value in settings.get('Values', {}).items():
                if not value.startswith('REPLACE_WITH_YOUR'):  # Skip placeholder values
                    os.environ[key] = value
            print("✅ Loaded local.settings.json")
    except FileNotFoundError:
        print("⚠️  No local.settings.json found - using .env and existing environment variables")
    
    # Check if we have the required connection string
    if os.environ.get('COSMOS_CONNECTION_STRING'):
        print("✅ COSMOS_CONNECTION_STRING found")
    else:
        print("❌ COSMOS_CONNECTION_STRING not found - please check your .env file")

def test_collect_pricing(max_cards=100, target_date=None):
    """Test the collect_pricing function locally"""
    print(f"\n🧪 Testing collect_pricing with max_cards={max_cards}")
    
    try:
        # Load local settings
        load_local_settings()
        
        # Import the function
        from pricing_pipeline import run_pricing_pipeline_azure_function
        
        # Use today if no date specified
        if not target_date:
            target_date = datetime.now().date().isoformat()
        
        # Run the pipeline
        print(f"🚀 Starting pipeline for {target_date}...")
        result = run_pricing_pipeline_azure_function(
            target_date=target_date,
            max_cards=max_cards
        )
        
        # Display results
        print("\n📊 Results:")
        print(json.dumps(result, indent=2))
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_concurrency_protection():
    """Test the concurrency protection logic"""
    print("\n🔒 Testing concurrency protection...")
    
    # This would normally be done via HTTP requests in production
    # For local testing, we can simulate the logic
    print("✅ Concurrency logic can be tested via multiple local runs")

def test_batch_chaining():
    """Test the auto-chaining logic"""
    print("\n🔗 Testing batch chaining logic...")
    
    try:
        load_local_settings()
        from pricing_pipeline import MTGPricingPipeline
        
        pipeline = MTGPricingPipeline()
        target_date = datetime.now().date().isoformat()
        
        # Get cards that DON'T have pricing for this specific date (same logic as production)
        total_cards = pipeline.cards_collection.count_documents({})
        
        # Count unique cards with pricing for this date (more efficient)
        pipeline_result = pipeline.pricing_collection.aggregate([
            {'$match': {'date': target_date}},
            {'$group': {'_id': '$scryfall_id'}},
            {'$count': 'unique_cards'}
        ])
        
        cards_with_pricing = 0
        for result in pipeline_result:
            cards_with_pricing = result['unique_cards']
            break
        
        # Also get total pricing records for verification
        total_pricing_records = pipeline.pricing_collection.count_documents({'date': target_date})
        remaining = total_cards - cards_with_pricing
        
        print(f"📈 Total cards: {total_cards:,}")
        print(f"📈 Cards with pricing for {target_date}: {cards_with_pricing:,}")
        print(f"📈 Total pricing records for {target_date}: {total_pricing_records:,}")
        print(f"📈 Remaining: {remaining:,}")
        
        # Calculate batches needed
        batch_size = 20000
        batches_needed = (remaining + batch_size - 1) // batch_size  # Ceiling division
        
        print(f"📦 Batches needed (20K each): {batches_needed}")
        print(f"⏱️  Estimated total time: {batches_needed * 9:.1f} minutes")
        
        return remaining
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_production_simulation(target_date=None):
    """Simulate full production pipeline with batching"""
    print("\n🏭 Production Pipeline Simulation")
    print("=" * 50)
    
    if not target_date:
        target_date = datetime.now().date().isoformat()
    
    try:
        load_local_settings()
        from pricing_pipeline import run_pricing_pipeline_azure_function
        
        batch_size = 20000
        batch_count = 0
        total_cards_processed = 0
        total_records_created = 0
        
        print(f"🎯 Target date: {target_date}")
        print(f"📦 Batch size: {batch_size:,} cards")
        print()
        
        while True:
            batch_count += 1
            print(f"🚀 Starting Batch {batch_count} (Production Mode)")
            print("-" * 30)
            
            start_time = datetime.now()
            
            # Run the actual production function
            result = run_pricing_pipeline_azure_function(
                target_date=target_date,
                max_cards=batch_size
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            cards_processed = result.get('cards_processed', 0)
            records_created = result.get('records_created', 0)
            
            total_cards_processed += cards_processed
            total_records_created += records_created
            
            print(f"✅ Batch {batch_count} Complete:")
            print(f"   📊 Cards processed: {cards_processed:,}")
            print(f"   💾 Records created: {records_created:,}")
            print(f"   ⏱️  Duration: {duration:.1f} seconds")
            print(f"   🚄 Speed: {cards_processed/duration:.1f} cards/sec")
            print()
            
            # Check if we should continue (same logic as production)
            if cards_processed < batch_size:
                print(f"🏁 Pipeline Complete! Processed {cards_processed} cards (less than batch size)")
                break
                
            # Check remaining cards with efficient aggregation
            from pricing_pipeline import MTGPricingPipeline
            pipeline = MTGPricingPipeline()
            
            total_cards = pipeline.cards_collection.count_documents({})
            
            # Use aggregation to count unique cards (more efficient and accurate)
            pipeline_result = pipeline.pricing_collection.aggregate([
                {'$match': {'date': target_date}},
                {'$group': {'_id': '$scryfall_id'}},
                {'$count': 'unique_cards'}
            ])
            
            cards_with_pricing = 0
            for result in pipeline_result:
                cards_with_pricing = result['unique_cards']
                break
            
            # Count total records for debugging
            total_records = pipeline.pricing_collection.count_documents({'date': target_date})
            remaining_cards = total_cards - cards_with_pricing
            
            print(f"📊 Progress Check:")
            print(f"   Total cards: {total_cards:,}")
            print(f"   Cards with pricing: {cards_with_pricing:,}")
            print(f"   Total pricing records: {total_records:,}")
            print(f"   Remaining: {remaining_cards:,}")
            
            if remaining_cards <= 1000:  # Production threshold
                print(f"🎉 Collection Complete! Only {remaining_cards} cards remaining (below 1000 threshold)")
                break
            
            print(f"➡️  Next batch will process {min(remaining_cards, batch_size):,} cards")
            print(f"⏳ Simulating 3-second delay between batches...")
            import time
            time.sleep(3)  # Simulate production delay
            print()
        
        print("🎊 PRODUCTION SIMULATION COMPLETE!")
        print("=" * 50)
        print(f"📦 Total batches: {batch_count}")
        print(f"📊 Total cards processed: {total_cards_processed:,}")
        print(f"💾 Total records created: {total_records_created:,}")
        print(f"⏱️  Average per batch: {total_cards_processed/batch_count:.0f} cards")
        print()
        
        return result
        
    except Exception as e:
        print(f"❌ Production simulation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🔧 Azure Functions Local Development Tool")
    print("=" * 50)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Local Azure Functions testing')
    parser.add_argument('--test', choices=['pricing', 'concurrency', 'chaining', 'production'], 
                        default='pricing', help='Test to run')
    parser.add_argument('--max-cards', type=int, default=100, 
                        help='Maximum cards to process (for pricing test)')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD)')
    parser.add_argument('--production', action='store_true',
                        help='Run full production simulation (20K card batches)')
    
    args = parser.parse_args()
    
    if args.test == 'pricing' and not args.production:
        test_collect_pricing(max_cards=args.max_cards, target_date=args.date)
    elif args.test == 'production' or args.production:
        test_production_simulation(target_date=args.date)
    elif args.test == 'concurrency':
        test_concurrency_protection()
    elif args.test == 'chaining':
        test_batch_chaining()
    
    print("\n✨ Local testing complete!")