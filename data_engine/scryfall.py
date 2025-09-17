import scrython
import decimal
import ijson
import datetime
from data_engine.cosmos_driver import get_mongo_client, get_collection, upsert_card

def get_card_by_name(card_name):
	"""
	Fetch a card by name (fuzzy match). Returns a dict with all available fields from Scryfall.
	"""
	try:
		card = scrython.cards.Named(fuzzy=card_name)
		return card.scryfallJson
	except Exception as e:
		print(f"Error fetching card: {e}")
		return None

def get_all_printings(card_name):
	"""
	Fetch all printings of a card by exact name. Returns a list of dicts (all available fields).
	Uses Scryfall's search: !"Card Name"
	"""
	try:
		all_cards = []
		search = scrython.cards.Search(q=f'!"{card_name}"')
		all_cards.extend(search.data())
		# Use next_page_uri to fetch all pages
		while getattr(search, 'next_page_uri', None):
			search = scrython.cards.Search(url=search.next_page_uri)
			all_cards.extend(search.data())
		return all_cards
	except Exception as e:
		print(f"Error fetching printings: {e}")
		return []


def stream_bulk_cards(json_path, set_code=None):
    """
    Generator that yields cards from the Scryfall bulk file, optionally filtered by set_code.
    """
    with open(json_path, 'rb') as f:
        cards = ijson.items(f, 'item')
        for card in cards:
            if set_code and card.get('set') != set_code:
                continue
            yield card

def convert_decimals(obj):
    if isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    else:
        return obj

def upload_cards_to_cosmos(cards, batch_size=500, day_uploaded=None):
    """
    Upserts cards to Cosmos DB in batches, adding a day_uploaded field.
    """
    client = get_mongo_client()
    collection = get_collection(client, 'mtgecorec', 'cards')
    today = day_uploaded or datetime.date.today().isoformat()
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
    if batch:
        for c in batch:
            upsert_card(collection, c)
        count += len(batch)
        print(f"Upserted {count} cards (final batch). Done!")


if __name__ == "__main__":
    # Example usage: upload only cards from set 'mh3' in the bulk file
    BULK_FILE = 'data_engine/scryfall-default-cards.json'
    print("Streaming and uploading cards from set 'mh3'...")
    cards = stream_bulk_cards(BULK_FILE, set_code='mh3')
    upload_cards_to_cosmos(cards, batch_size=500)
    print("Done.")
