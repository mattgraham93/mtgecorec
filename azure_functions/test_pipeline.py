#!/usr/bin/env python3
"""
Test script for the Azure Functions pricing pipeline
Run this to test the pipeline locally before deployment
"""

import os
import sys
import json
from datetime import date

# Add the functions directory to Python path
sys.path.insert(0, '/workspaces/mtgecorec/azure_functions')

def test_pipeline():
    """Test the pricing pipeline locally"""
    
    print("🧪 Testing MTG Pricing Pipeline")
    print("=" * 50)
    
    # Check if COSMOS_CONNECTION_STRING is available (same as existing codebase)
    if not os.getenv('COSMOS_CONNECTION_STRING'):
        print("❌ COSMOS_CONNECTION_STRING environment variable not set")
        print("Please load your .env file: export $(cat .env | xargs)")
        return False
    
    # Test database connection using the existing method
    try:
        sys.path.insert(0, '/workspaces/mtgecorec')
        from core.data_engine.cosmos_driver import get_mongo_client, get_collection
        
        # Test connection
        print("🔌 Testing database connection...")
        client = get_mongo_client()
        cards_collection = get_collection(client, "mtgecorec", "cards")
        total_cards = cards_collection.count_documents({})
        print(f"✅ Database connection successful! Found {total_cards:,} cards")
        print("✅ Using existing database connection for test")
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("Make sure you're in the dev container with database access")
        return False
    
    try:
        # Import and test the pipeline with a modified approach
        from pricing_pipeline import ScryfallBulkCollector, MTGPricingPipeline
        
        print("✅ Successfully imported pricing pipeline components")
        
        # Test the collector directly first
        print("\n🔬 Testing Scryfall collector with 5 cards...")
        
        collector = ScryfallBulkCollector()
        
        # Get 5 sample cards from the database
        sample_cards = list(cards_collection.find({'set': 'blb'}).limit(5))
        print(f"📦 Got {len(sample_cards)} sample cards from BLB set")
        
        if sample_cards:
            # Test pricing collection
            test_pricing = collector.collect_pricing_for_cards(sample_cards, date.today().isoformat())
            
            result = {
                'status': 'complete' if test_pricing else 'no_pricing',
                'cards_tested': len(sample_cards),
                'records_created': len(test_pricing),
                'sample_cards': [card.get('name', 'Unknown') for card in sample_cards[:3]]
            }
            
            if test_pricing:
                result['sample_pricing'] = {
                    'card_name': test_pricing[0].get('card_name'),
                    'price_value': test_pricing[0].get('price_value'),
                    'price_type': test_pricing[0].get('price_type')
                }
        else:
            result = {
                'status': 'error',
                'error': 'No sample cards found in database'
            }
        
        print("\n📊 Test Results:")
        print("=" * 30)
        print(json.dumps(result, indent=2))
        
        if result.get('status') == 'complete':
            print("\n✅ Pipeline test successful!")
            print(f"📈 Collected pricing for {result.get('cards_tested')} cards")
            print(f"💾 Created {result.get('records_created')} pricing records")
            return True
        else:
            print(f"\n❌ Pipeline test failed: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = test_pipeline()
    sys.exit(0 if success else 1)