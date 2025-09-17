from datetime import datetime, timezone
# Main driver for pushing/pulling data from Cosmos DB
from cosmos_driver import get_mongo_client, get_collection, add_card
from scryfall import get_card_by_name
from exchange_rate import get_exchange_rates


DATABASE_NAME = 'cards'
CONTAINER_NAME = 'mtgecorec'

def pull_all_cards():
	"""Fetch all cards from the Cosmos DB collection."""
	client = get_mongo_client()
	collection = get_collection(client, CONTAINER_NAME, DATABASE_NAME)
	cards = list(collection.find({}, {'_id': 0}))
	return cards

def insert_card_from_scryfall(card_name):
	"""Fetch a card from Scryfall and insert it into Cosmos DB."""
	card_data = get_card_by_name(card_name)
	if card_data:
		client = get_mongo_client()
		collection = get_collection(client, CONTAINER_NAME, DATABASE_NAME)
		add_card(collection, card_data)
		print(f"Inserted card: {card_data['name']}")
	else:
		print(f"Card '{card_name}' not found on Scryfall.")

def create_exchange_rates_collection():
	"""
	Create an 'exchange_rates' database and 'rates' collection in Cosmos DB.
	Returns the collection object.
	"""
	client = get_mongo_client()
	db = client['exchange_rates']
	collection = db['rates']
	print("Exchange rates collection ready.")
	return collection

def insert_exchange_rates(base_currency):
	"""
	Fetch latest exchange rates and insert into the 'rates' collection in Cosmos DB.
	"""
	rates = get_exchange_rates(base_currency)
	if not rates:
		print("No rates to insert.")
		return
	client = get_mongo_client()
	db = client['exchange_rates']
	collection = db['rates']
	doc = {
		'base': base_currency,
		'rates': rates,
		'inserted_at': datetime.now(timezone.utc).isoformat()
	}
	result = collection.insert_one(doc)
	print(f"Inserted exchange rates for {base_currency} with _id: {result.inserted_id}")

def pull_latest_exchange_rates(base_currency):
	"""
	Pull and print the most recently inserted exchange rates document from Cosmos DB.
	"""
	client = get_mongo_client()
	db = client['exchange_rates']
	collection = db['rates']
	doc = collection.find_one(sort=[('inserted_at', -1)])
	if doc:
		print(f"Latest exchange rates (base: {doc['base']}, inserted_at: {doc['inserted_at']}):")
		for k, v in doc['rates'].items():
			print(f"{k}: {v}")
	else:
		print("No exchange rates found in DB.")


if __name__ == "__main__":
    # Create exchange rates collection
	# create_exchange_rates_collection()

	# Insert latest exchange rates
	insert_exchange_rates('USD')
 
 	# Pull and print latest exchange rates
	pull_latest_exchange_rates('USD')
  
	# Example usage
	print("All cards in DB:")
	for card in pull_all_cards():
		print(card)

	# Example: insert a card from Scryfall
	insert_card_from_scryfall("Sol Ring")
 	# Example usage
	print("All cards in DB:")
	for card in pull_all_cards():
		print(card)
