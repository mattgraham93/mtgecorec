import json
import os
import sys
import uuid
from pymongo import MongoClient
from pymongo.errors import PyMongoError

def get_mongo_client():
    conn_str = os.environ.get('COSMOS_CONNECTION_STRING')
    if not conn_str:
        raise RuntimeError("Missing Cosmos DB connection string in environment variables.")
    return MongoClient(conn_str)

def add_card(collection, card_data):
    try:
        card_data['id'] = str(uuid.uuid4())  # Ensure each card has a unique ID
        collection.insert_one(card_data)
        print(f"Card added with ID: {card_data['id']}")
    except PyMongoError as e:
        print(f"Failed to add card: {e}")
        sys.exit(1)

def upsert_card(collection, card_data):
    # Upsert by 'id' (replace if exists, insert if not)
    collection.replace_one({'id': card_data['id']}, card_data, upsert=True)

def get_collection(client, db_name, collection_name):
    """
    Returns a collection object for the given database and collection name.
    """
    return client[db_name][collection_name]

if __name__ == '__main__':
    client = get_mongo_client()
    database_name = os.environ.get('COSMOS_DB_NAME', 'cards')
    container_name = os.environ.get('COSMOS_CONTAINER_NAME', 'mtgecorec')

    db = client[container_name]
    collection = db[database_name]

    # Example card data
    card_data = {
        "name": "Black Lotus",
        "type": "Artifact",
        "set": "Alpha",
        "rarity": "Rare",
        "price": 100000.00,
        "image_url": "http://example.com/black_lotus.jpg",
        "colors": [],
        "mana_cost": "{0}",
        "text": "{T}, Sacrifice Black Lotus: Add three mana of any one color.",
        "flavor_text": "",
        "artist": "Christopher Rush",
        "number": "233",
        "power_toughness": None,
        "loyalty": None,
        "border_color": "Black",
        "legalities": {"Vintage": "Legal", "Legacy": "Legal", "Commander": "Legal"},
        "release_date": "1993-08-05",
        "foil_availability": False,
        "non_foil_availability": True
    }

    add_card(collection, card_data)

    collection = get_collection(client, container_name, database_name)

    print("Cards in collection:")
    for card in collection.find():
        print(card)