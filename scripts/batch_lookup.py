"""
batch_lookup.py - Batch lookup of cards from Cosmos DB and JustTCG

This script:
- Connects to Cosmos DB (using your cosmos_driver)
- Retrieves card names and tcgplayerId from the cards collection
- Batches them in groups of 20
- Calls the JustTCG batch card lookup endpoint
- Prints the results
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from dotenv import load_dotenv
from data_engine.cosmos_driver import get_mongo_client, get_collection
from data_engine.justtcg import JustTCGClient

load_dotenv()

BATCH_SIZE = 20

def get_cards_from_cosmos(limit=100):
    client = get_mongo_client()
    db_name = os.environ.get('COSMOS_DB_NAME', 'cards')
    container_name = os.environ.get('COSMOS_CONTAINER_NAME', 'mtgecorec')
    collection = get_collection(client, container_name, db_name)
    # Only get cards with a tcgplayer_id
    cursor = collection.find({'tcgplayer_id': {'$exists': True, '$ne': None}}, {'name': 1, 'tcgplayer_id': 1, '_id': 0}).limit(limit)
    return list(cursor)

def batch_lookup(cards, condition="Near Mint", printing=None):
    client = JustTCGClient()
    url = "https://api.justtcg.com/v1/cards"
    headers = client._get_headers()
    headers['Content-Type'] = 'application/json'
    results = []
    for i in range(0, len(cards), BATCH_SIZE):
        batch = cards[i:i+BATCH_SIZE]
        payload = []
        for card in batch:
            entry = {"tcgplayerId": str(card['tcgplayer_id'])}
            if condition:
                entry["condition"] = condition
            if printing:
                entry["printing"] = printing
            payload.append(entry)
        resp = client.session.post(url, headers=headers, data=json.dumps(payload))
        resp.raise_for_status()
        results.extend(resp.json().get('data', []))
    return results

def main():
    cards = get_cards_from_cosmos(limit=40)  # Example: get 40 cards
    print(f"Pulled {len(cards)} cards from Cosmos DB.")
    results = batch_lookup(cards)
    print(f"Batch lookup returned {len(results)} cards.")
    for card in results[:5]:
        print(json.dumps(card, indent=2))
    if len(results) > 5:
        print(f"...and {len(results)-5} more cards.")

if __name__ == "__main__":
    main()
