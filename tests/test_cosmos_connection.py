#!/usr/bin/env python3
"""
Test script to verify Cosmos DB connection is working.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_cosmos_connection():
    """Test Cosmos DB connection."""
    print("\n" + "="*70)
    print("COSMOS DB CONNECTION TEST")
    print("="*70)
    
    # Check environment variables
    print("\nChecking environment variables...")
    cosmos_conn = os.environ.get('COSMOS_CONNECTION_STRING')
    cosmos_db = os.environ.get('COSMOS_DB_NAME')
    cosmos_container = os.environ.get('COSMOS_CONTAINER_NAME')
    
    if not cosmos_conn:
        print("❌ COSMOS_CONNECTION_STRING not set")
        return False
    else:
        # Show masked connection string for security
        masked = cosmos_conn[:50] + "..." + cosmos_conn[-20:]
        print(f"✓ COSMOS_CONNECTION_STRING: {masked}")
    
    if not cosmos_db:
        print("❌ COSMOS_DB_NAME not set")
        return False
    else:
        print(f"✓ COSMOS_DB_NAME: {cosmos_db}")
    
    if not cosmos_container:
        print("❌ COSMOS_CONTAINER_NAME not set")
        return False
    else:
        print(f"✓ COSMOS_CONTAINER_NAME: {cosmos_container}")
    
    # Try to connect
    print("\nAttempting to connect to Cosmos DB...")
    try:
        from core.data_engine.cosmos_driver import get_mongo_client, get_collection
        
        client = get_mongo_client()
        print("✓ MongoDB client created successfully")
        
        # Get database and collection
        db = client[cosmos_db]
        print(f"✓ Database '{cosmos_db}' accessed")
        
        collection = db[cosmos_container]
        print(f"✓ Collection '{cosmos_container}' accessed")
        
        # Try to count cards
        card_count = collection.count_documents({})
        print(f"✓ Successfully queried Cosmos DB")
        print(f"  Total cards in collection: {card_count}")
        
        # Sample a card
        sample_card = collection.find_one({})
        if sample_card:
            print(f"\n✓ Sample card retrieved:")
            print(f"  Name: {sample_card.get('name', 'N/A')}")
            print(f"  Type: {sample_card.get('type_line', 'N/A')}")
            print(f"  CMC: {sample_card.get('cmc', 'N/A')}")
            print(f"  Color Identity: {sample_card.get('color_identity', [])}")
        
        client.close()
        print("\n✓ Connection closed successfully")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "="*70)
    print("✓ ALL TESTS PASSED")
    print("="*70 + "\n")
    return True


if __name__ == '__main__':
    try:
        success = test_cosmos_connection()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.exception(f"Test failed: {e}")
        sys.exit(1)
