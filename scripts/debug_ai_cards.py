#!/usr/bin/env python3
"""
Debug script to check which AI suggested cards are in our database
"""

import os
import sys
from data_engine.cosmos_driver import get_mongo_client, get_collection

# Set up environment for testing
os.environ['COSMOS_CONNECTION_STRING'] = os.environ.get('COSMOS_CONNECTION_STRING', '')
os.environ['COSMOS_DB_NAME'] = 'cards'
os.environ['COSMOS_CONTAINER_NAME'] = 'mtgecorec'

def check_ai_cards():
    try:
        client = get_mongo_client()
        collection = get_collection(client, 'mtgecorec', 'cards')
        
        # The cards mentioned by AI in your description
        ai_suggested = [
            "Skullclamp", "Smothering Tithe", "Sol Ring", "Esper Sentinel", 
            "Bident of Thassa", "Anointed Procession", "Coat of Arms", 
            "Lightning Greaves", "Enchanted Evening", "Kindred Discovery",
            "Sai, Master Thopterist", "Aetherflux Reservoir", "Mirage Mirror",
            "Favorable Winds", "Magus of the Moat", "Baleful Strix"
        ]
        
        print("Checking AI suggested cards in database:")
        print("=" * 60)
        
        found_cards = []
        missing_cards = []
        
        for card_name in ai_suggested:
            results = list(collection.find({"name": card_name}))
            
            if results:
                legality = results[0].get('legalities', {}).get('commander', 'unknown')
                colors = results[0].get('colors', [])
                type_line = results[0].get('type_line', '')
                
                print(f"✓ {card_name}")
                print(f"   Versions: {len(results)}")
                print(f"   Commander Legal: {legality}")
                print(f"   Colors: {colors}")
                print(f"   Type: {type_line}")
                print()
                
                if legality == 'legal':
                    found_cards.append(card_name)
            else:
                print(f"✗ {card_name} - NOT FOUND")
                missing_cards.append(card_name)
        
        print("=" * 60)
        print(f"Summary:")
        print(f"   Found in DB: {len(found_cards)}/{len(ai_suggested)}")
        print(f"   Missing: {len(missing_cards)}")
        
        if missing_cards:
            print(f"   Missing cards: {', '.join(missing_cards)}")
            
        return found_cards, missing_cards
        
    except Exception as e:
        print(f"Error: {e}")
        return [], []

if __name__ == "__main__":
    check_ai_cards()