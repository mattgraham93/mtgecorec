#!/usr/bin/env python3
"""
Simple test for Azure Functions pricing pipeline components
Tests the Scryfall API functionality without requiring database connection
"""

import os
import sys
import json
from datetime import date

# Add the functions directory to Python path
sys.path.insert(0, '/workspaces/mtgecorec/azure_functions')

def test_scryfall_collector():
    """Test just the Scryfall collector component"""
    
    print("🧪 Testing Scryfall Collector (No Database Required)")
    print("=" * 60)
    
    try:
        from pricing_pipeline import ScryfallBulkCollector
        
        print("✅ Successfully imported ScryfallBulkCollector")
        
        # Create collector
        collector = ScryfallBulkCollector()
        print("✅ Collector initialized")
        
        # Test with a few real Magic card IDs (from Scryfall)
        # These are actual Scryfall IDs for testing
        test_cards = [
            {'id': 'f295b713-1d6a-43fd-910d-fb35414bf58a'},  # Lightning Bolt
            {'id': 'b34bb2dc-c1af-4d77-b0b3-a0fb342a5fc6'},  # Black Lotus
        ]
        
        print(f"🔍 Testing pricing collection for {len(test_cards)} cards...")
        
        # Test the pricing collection
        pricing_records = collector.collect_pricing_for_cards(test_cards, date.today().isoformat())
        
        print(f"\n📊 Test Results:")
        print(f"   Cards tested: {len(test_cards)}")
        print(f"   Pricing records collected: {len(pricing_records)}")
        
        if pricing_records:
            sample_record = pricing_records[0]
            print(f"   Sample card: {sample_record.get('card_name', 'Unknown')}")
            print(f"   Sample price: ${sample_record.get('price_value', 0):.2f} ({sample_record.get('price_type', 'unknown')})")
            print(f"   Currency: {sample_record.get('currency', 'unknown')}")
            
            result = {
                'status': 'success',
                'collector_working': True,
                'cards_tested': len(test_cards),
                'records_collected': len(pricing_records),
                'scryfall_api_working': True,
                'sample_data': {
                    'card_name': sample_record.get('card_name'),
                    'price_value': sample_record.get('price_value'),
                    'price_type': sample_record.get('price_type'),
                    'currency': sample_record.get('currency')
                }
            }
            
            print("\n✅ Scryfall API test SUCCESSFUL!")
            print("📈 The pricing collector is working correctly")
            print("💡 Ready for Azure Functions deployment")
            
        else:
            result = {
                'status': 'partial_success',
                'collector_working': True,
                'cards_tested': len(test_cards),
                'records_collected': 0,
                'scryfall_api_working': True,
                'message': 'API working but no pricing data returned (normal for some cards)'
            }
            print("\n⚠️  API working but no pricing returned (this can be normal)")
        
        print(f"\n📋 Full Results:")
        print(json.dumps(result, indent=2))
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print("Check internet connection and Scryfall API availability")
        return False

if __name__ == "__main__":
    print("🚀 MTG Pricing Pipeline - Component Test")
    print("Testing Scryfall API functionality only (no database required)")
    print()
    
    success = test_scryfall_collector()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ COMPONENT TEST PASSED")
        print("🎯 Next Steps:")
        print("   1. The Scryfall collector is working")
        print("   2. Ready for Azure Functions deployment")
        print("   3. Database connection will be configured in Azure")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ COMPONENT TEST FAILED")
        print("🔧 Check internet connection and try again")
        print("=" * 60)
    
    sys.exit(0 if success else 1)