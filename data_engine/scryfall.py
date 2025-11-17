import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

import scrython
import ijson
import decimal
import datetime
from data_engine.cosmos_driver import get_mongo_client, get_collection, upsert_card
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import logging
logging.getLogger("pymongo").setLevel(logging.ERROR)
import time
from pymongo.errors import BulkWriteError

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

def upload_cards_to_cosmos(cards, batch_size=500, day_uploaded=None, total_count=None):
    """
    Upserts cards to Cosmos DB in batches, adding a day_uploaded field.
    """
    client = get_mongo_client()
    collection = get_collection(client, 'mtgecorec', 'cards')
    today = day_uploaded or datetime.date.today().isoformat()
    batch = []
    total_success = 0
    total_failed = 0
    batch_num = 0
    for card in cards:
        card = convert_decimals(card)
        card['day_uploaded'] = today
        batch.append(card)
        if len(batch) >= batch_size:
            batch_num += 1
            success_count = 0
            fail_count = 0
            for c in batch:
                try:
                    upsert_card(collection, c)
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    print(f"\nBatch {batch_num}: Upsert error: {e}")
            total_success += success_count
            total_failed += fail_count
            if total_count:
                percent = (total_success / total_count) * 100
                print(f"\rUpserted {total_success} cards... ({percent:.1f}%)", end="", flush=True)
            else:
                print(f"Upserted {total_success} cards...", end="\r", flush=True)
            batch = []
    if batch:
        batch_num += 1
        success_count = 0
        fail_count = 0
        for c in batch:
            try:
                upsert_card(collection, c)
                success_count += 1
            except Exception as e:
                fail_count += 1
                print(f"\nBatch {batch_num}: Upsert error: {e}")
        total_success += success_count
        total_failed += fail_count
        if total_count:
            percent = (total_success / total_count) * 100
            print(f"\rUpserted {total_success} cards (final batch). Done! ({percent:.1f}%)", end="", flush=True)
        else:
            print(f"Upserted {total_success} cards (final batch). Done!", end="\r", flush=True)
    print(f"\nTotal successfully upserted: {total_success} cards.")
    if total_failed > 0:
        print(f"Total failed upserts: {total_failed} cards.")


def insert_cards_to_cosmos(cards, batch_size=50, day_uploaded=None, total_count=None):
    """
    Fast initial upload: insert cards in batches using insert_many (no deduplication).
    Use only when the collection is empty!
    Shows % complete if total_count is provided.
    """
    client = get_mongo_client()
    collection = get_collection(client, 'mtgecorec', 'cards')
    today = day_uploaded or datetime.date.today().isoformat()
    batch = []
    total_success = 0
    total_failed = 0
    batch_num = 0
    for card in cards:
        card = convert_decimals(card)
        card['day_uploaded'] = today
        batch.append(card)
        if len(batch) >= batch_size:
            batch_num += 1
            try:
                for c in batch:
                    if 'day_uploaded' not in c:
                        c['day_uploaded'] = today
                result = collection.insert_many(batch, ordered=False)
                success_count = len(result.inserted_ids)
                fail_count = len(batch) - success_count
            except BulkWriteError as bwe:
                # Count successful inserts from error details
                success_count = bwe.details.get('nInserted', 0)
                fail_count = len(batch) - success_count
                print(f"\nBatch {batch_num}: Bulk write error. Inserted {success_count}, Failed {fail_count}.", flush=True)
            else:
                fail_count = 0
            total_success += success_count
            total_failed += fail_count
            if total_count:
                percent = (total_success / total_count) * 100
                print(f"\rInserted {total_success} cards... ({percent:.1f}%)", end="", flush=True)
            else:
                print(f"Inserted {total_success} cards...", end="\r", flush=True)
            batch = []
            time.sleep(0.1)
    if batch:
        batch_num += 1
        try:
            for c in batch:
                if 'day_uploaded' not in c:
                    c['day_uploaded'] = today
            result = collection.insert_many(batch, ordered=False)
            success_count = len(result.inserted_ids)
            fail_count = len(batch) - success_count
        except BulkWriteError as bwe:
            success_count = bwe.details.get('nInserted', 0)
            fail_count = len(batch) - success_count
            print(f"\nBatch {batch_num}: Bulk write error. Inserted {success_count}, Failed {fail_count}.")
        else:
            fail_count = 0
        total_success += success_count
        total_failed += fail_count
        if total_count:
            percent = (total_success / total_count) * 100
            print(f"\rInserted {total_success} cards (final batch). Done! ({percent:.1f}%)", end="", flush=True)
        else:
            print(f"Inserted {total_success} cards (final batch). Done!", end="\r", flush=True)
    print(f"\nTotal successfully inserted: {total_success} cards.")
    if total_failed > 0:
        print(f"Total failed inserts: {total_failed} cards.")


if __name__ == "__main__":
    import json
    BULK_FILE = 'data_engine/scryfall-default-cards.json'
    # Count total cards for progress reporting
    with open(BULK_FILE, 'r', encoding='utf-8') as f:
        total_count = sum(1 for _ in json.load(f))

    print("Streaming and upserting all cards...")
    cards = stream_bulk_cards(BULK_FILE, set_code=None)
    upload_cards_to_cosmos(cards, batch_size=500, total_count=total_count)
    print("Done.")
