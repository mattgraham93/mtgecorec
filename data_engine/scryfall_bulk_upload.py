import json
import ijson
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
from cosmos_driver import get_mongo_client, get_collection

BULK_FILE = 'scryfall-default-cards.json'  # Path to your downloaded Scryfall bulk file
BATCH_SIZE = 500
DATABASE_NAME = 'cards'
CONTAINER_NAME = 'mtgecorec'


def stream_and_upload_cards(json_path, batch_size=500):
    client = get_mongo_client()
    collection = get_collection(client, CONTAINER_NAME, DATABASE_NAME)
    
    with open(json_path, 'rb') as f:
        # Scryfall bulk file is a JSON array of card objects
        cards = ijson.items(f, 'item')
        batch = []
        count = 0
        for card in cards:
            batch.append(card)
            if len(batch) >= batch_size:
                try:
                    collection.insert_many(batch, ordered=False)
                except BulkWriteError as bwe:
                    print(f"Bulk write error: {bwe.details}")
                count += len(batch)
                print(f"Inserted {count} cards...")
                batch = []
        # Insert any remaining cards
        if batch:
            try:
                collection.insert_many(batch, ordered=False)
            except BulkWriteError as bwe:
                print(f"Bulk write error: {bwe.details}")
            count += len(batch)
            print(f"Inserted {count} cards (final batch). Done!")

if __name__ == "__main__":
    stream_and_upload_cards(BULK_FILE, BATCH_SIZE)
