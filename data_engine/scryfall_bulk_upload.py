# default data from: https://scryfall.com/docs/api/bulk-data

import decimal
import json
import ijson
import datetime
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
from cosmos_driver import get_mongo_client, get_collection, upsert_card

from dotenv import load_dotenv
load_dotenv()

BULK_FILE = 'data_engine/scryfall-default-cards.json'  # Path to your downloaded Scryfall bulk file
BATCH_SIZE = 500
DATABASE_NAME = 'cards'
CONTAINER_NAME = 'mtgecorec'

def convert_decimals(obj):
    """Recursively convert Decimal values to float in dicts/lists."""
    if isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    else:
        return obj


def stream_and_upload_cards(json_path, batch_size=500):
    client = get_mongo_client()
    collection = get_collection(client, CONTAINER_NAME, DATABASE_NAME)
    today = datetime.date.today().isoformat()
    with open(json_path, 'rb') as f:
        # Scryfall bulk file is a JSON array of card objects
        cards = ijson.items(f, 'item')
        batch = []
        count = 0
        for card in cards:
            card = convert_decimals(card)
            card['day_uploaded'] = today
            batch.append(card)
            if len(batch) >= batch_size:
                for c in batch:
                    upsert_card(collection, c)
                count += len(batch)
                print(f"Upserted {count} cards...")
                batch = []
        # Insert any remaining cards
        if batch:
            for c in batch:
                upsert_card(collection, c)
            count += len(batch)
            print(f"Upserted {count} cards (final batch). Done!")

if __name__ == "__main__":
    stream_and_upload_cards(BULK_FILE, BATCH_SIZE)
