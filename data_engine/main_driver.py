# Main driver for pushing/pulling data from Cosmos DB
from cosmos_driver import get_mongo_client, get_collection, add_card
from scryfall import get_card_by_name

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

if __name__ == "__main__":
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
