import json
import os
import sys
import uuid
from pymongo import MongoClient
from pymongo.errors import PyMongoError

def get_mongo_client():
    try:
        auth_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'auth.json')
        with open(auth_path) as f:
            auth = json.load(f)
    except FileNotFoundError:
        print("auth.json file not found. Please create it with your MongoDB credentials.")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error decoding auth.json. Please ensure it is valid JSON.")
        sys.exit(1)
    
    cosmos = auth.get('cosmos_db', {})
    connection_string = cosmos.get('connection_string')

    if not connection_string:
        print("MongoDB 'connection_string' must be set in auth.json under 'cosmos_db'.")
        sys.exit(1)

    try:
        client = MongoClient(connection_string)
        return client
    except PyMongoError as e:
        print(f"Failed to create MongoClient: {e}")
        sys.exit(1)

def add_card(collection, card_data):
    try:
        card_data['id'] = str(uuid.uuid4())  # Ensure each card has a unique ID
        collection.insert_one(card_data)
        print(f"Card added with ID: {card_data['id']}")
    except PyMongoError as e:
        print(f"Failed to add card: {e}")
        sys.exit(1)

def get_collection(client, db_name, collection_name):
    """
    Returns a collection object for the given database and collection name.
    """
    return client[db_name][collection_name]

if __name__ == '__main__':
    client = get_mongo_client()
    database_name = 'cards'
    container_name = 'mtgecorec'

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