# Example usage of Scrython to fetch a card by name
import scrython


def get_card_by_name(card_name):
	try:
		card = scrython.cards.Named(fuzzy=card_name)
		# Use set_code() instead of set(), and handle missing fields
		card_info = {
			'name': getattr(card, 'name', lambda: None)(),
			'set_code': getattr(card, 'set_code', lambda: None)(),
			'rarity': getattr(card, 'rarity', lambda: None)(),
			'image_url': None,
			'oracle_text': getattr(card, 'oracle_text', lambda: None)(),
			'mana_cost': getattr(card, 'mana_cost', lambda: None)(),
			'type_line': getattr(card, 'type_line', lambda: None)(),
		}
		# Handle image_uris if present
		try:
			image_uris = card.image_uris()
			if image_uris and 'normal' in image_uris:
				card_info['image_url'] = image_uris['normal']
		except Exception:
			card_info['image_url'] = None
		return card_info
	except Exception as e:
		print(f"Error fetching card: {e}")
		return None

if __name__ == "__main__":
	card_name = "Black Lotus"
	card_info = get_card_by_name(card_name)
	if card_info:
		print(f"Card info for {card_name}:")
		for k, v in card_info.items():
			print(f"{k}: {v}")
	else:
		print("Card not found.")
