import ijson

BULK_FILE = 'data_engine/scryfall-default-cards.json'

def count_cards_with_id(json_path):
    with open(json_path, 'rb') as f:
        cards = ijson.items(f, 'item')
        count = sum(1 for card in cards if 'id' in card)
    return count

if __name__ == "__main__":
    total = count_cards_with_id(BULK_FILE)
    print(f"Total cards with 'id' in {BULK_FILE}: {total}")