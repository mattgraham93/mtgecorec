import scrython

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


# def get_card_by_name(card_name):
# 	try:
# 		card = scrython.cards.Named(fuzzy=card_name)
# 		# Use set_code() instead of set(), and handle missing fields
# 		card_info = {
# 			'name': getattr(card, 'name', lambda: None)(),
# 			'set_code': getattr(card, 'set_code', lambda: None)(),
# 			'rarity': getattr(card, 'rarity', lambda: None)(),
# 			'image_url': None,
# 			'oracle_text': getattr(card, 'oracle_text', lambda: None)(),
# 			'mana_cost': getattr(card, 'mana_cost', lambda: None)(),
# 			'type_line': getattr(card, 'type_line', lambda: None)(),
# 		}
# 		# Handle image_uris if present
# 		try:
# 			image_uris = card.image_uris()
# 			if image_uris and 'normal' in image_uris:
# 				card_info['image_url'] = image_uris['normal']
# 		except Exception:
# 			card_info['image_url'] = None
# 		return card_info
# 	except Exception as e:
# 		print(f"Error fetching card: {e}")
# 		return None


if __name__ == "__main__":
	card_name = "Sol Ring"
	print(f"Testing get_card_by_name('{card_name}'):\n")
	card = get_card_by_name(card_name)
	if card:
		for k, v in card.items():
			print(f"{k}: {v}")
	else:
		print("Card not found.")

	print("\nTesting get_all_printings('{card_name}'):\n")
	printings = get_all_printings(card_name)
	print(f"Found {len(printings)} printings.")
	for c in printings:
		print(f"Set: {c.get('set_name')} | Released: {c.get('released_at')} | Collector #: {c.get('collector_number')}")
