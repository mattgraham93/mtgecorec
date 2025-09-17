"""
delete_all_cards.py - Script to delete all cards in the Cosmos DB collection for a clean slate.
"""
import sys
import os
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from data_engine.cosmos_driver import get_mongo_client, get_collection

load_dotenv()

def batched_delete(collection, batch_size=10):
    total_deleted = 0
    while True:
        ids = list(collection.find({}, {'_id': 1}).limit(batch_size))
        if not ids:
            break
        id_list = [doc['_id'] for doc in ids]
        result = collection.delete_many({'_id': {'$in': id_list}})
        total_deleted += result.deleted_count
        print(f"Deleted {result.deleted_count} cards (total: {total_deleted})...")
        time.sleep(0.1)  # Sleep 100ms to avoid rate limiting
    print(f"All done. Deleted {total_deleted} cards in total.")

def main():
    db_name = os.environ.get('COSMOS_DB_NAME', 'cards')
    container_name = os.environ.get('COSMOS_CONTAINER_NAME', 'mtgecorec')
    client = get_mongo_client()
    collection = get_collection(client, container_name, db_name)
    batched_delete(collection, batch_size=500)

if __name__ == "__main__":
    main()
