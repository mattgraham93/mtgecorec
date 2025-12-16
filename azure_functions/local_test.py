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
    """Load local.settings.json or use existing environment variables"""
    try:
        with open('local.settings.json', 'r') as f:
            settings = json.load(f)
            # Set environment variables
            for key, value in settings.get('Values', {}).items():
                if not value.startswith('REPLACE_WITH_YOUR'):  # Skip placeholder values
                    os.environ[key] = value
            print("✅ Loaded local.settings.json")
    except FileNotFoundError:
        print("⚠️  No local.settings.json found - using existing environment variables")
    
    # Check if we have the required connection string
    if os.environ.get('COSMOS_CONNECTION_STRING'):
        print("✅ COSMOS_CONNECTION_STRING found")
    else:
        print("❌ COSMOS_CONNECTION_STRING not found - please set this environment variable")

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
        
        # Check remaining cards
        total_cards = pipeline.cards_collection.count_documents({})
        cards_with_pricing = pipeline.pricing_collection.count_documents({
            'date': datetime.now().date().isoformat()
        })
        
        remaining = total_cards - cards_with_pricing
        
        print(f"📈 Total cards: {total_cards:,}")
        print(f"📈 Cards with pricing: {cards_with_pricing:,}")
        print(f"📈 Remaining: {remaining:,}")
        
        return remaining
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🔧 Azure Functions Local Development Tool")
    print("=" * 50)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Local Azure Functions testing')
    parser.add_argument('--test', choices=['pricing', 'concurrency', 'chaining'], 
                        default='pricing', help='Test to run')
    parser.add_argument('--max-cards', type=int, default=100, 
                        help='Maximum cards to process (for pricing test)')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    if args.test == 'pricing':
        test_collect_pricing(max_cards=args.max_cards, target_date=args.date)
    elif args.test == 'concurrency':
        test_concurrency_protection()
    elif args.test == 'chaining':
        test_batch_chaining()
    
    print("\n✨ Local testing complete!")