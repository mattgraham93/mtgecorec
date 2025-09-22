import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from data_engine.cosmos_driver import get_mongo_client, get_collection

from dotenv import load_dotenv
load_dotenv()

def clear_cards_collection():
    client = get_mongo_client()
    collection = get_collection(client, 'mtgecorec', 'cards')
    result = collection.delete_many({})
    print(f"Cleared collection: deleted {result.deleted_count} documents.")
    client.close()

if __name__ == "__main__":
    clear_cards_collection()
