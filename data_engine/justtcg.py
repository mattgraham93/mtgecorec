"""
justtcg.py - JustTCG API client for MTG card data and prices

This module provides functions to fetch data from the JustTCG API.
"""
import os
import requests


from dotenv import load_dotenv
load_dotenv()

JUSTTCG_API_BASE = "https://api.justtcg.com/v1"

class JustTCGClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get('JUSTTCG_API_KEY')
        if not self.api_key:
            raise ValueError("JUSTTCG_API_KEY must be set in environment or passed to constructor.")
        self.session = requests.Session()

    def _get_headers(self):
        return {
            'X-API-Key': self.api_key,
            'Accept': 'application/json'
        }

    def get_cards(self, game="mtg", page=1, page_size=100):
        url = f"{JUSTTCG_API_BASE}/cards"
        params = {
            'game': game,
            'page': page,
            'pageSize': page_size
        }
        resp = self.session.get(url, headers=self._get_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def get_card(self, card_id):
        url = f"{JUSTTCG_API_BASE}/cards/{card_id}"
        resp = self.session.get(url, headers=self._get_headers())
        resp.raise_for_status()
        return resp.json()

    def search_cards(self, name, game="mtg"):
        url = f"{JUSTTCG_API_BASE}/cards"
        params = {
            'game': game,
            'name': name
        }
        resp = self.session.get(url, headers=self._get_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def get_sets(self, game="mtg"):
        url = f"{JUSTTCG_API_BASE}/sets"
        params = {'game': game}
        resp = self.session.get(url, headers=self._get_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def get_games(self):
        url = f"{JUSTTCG_API_BASE}/games"
        resp = self.session.get(url, headers=self._get_headers())
        resp.raise_for_status()
        return resp.json()

def test_auth():
    try:
        client = JustTCGClient()
        # Try a simple request to verify authentication
        games = client.get_games()
        print(f"Authentication successful! Found {len(games.get('data', []))} games.")
        print("Games:")
        for g in games.get('data', []):
            print(f"- {g['name']} (id: {g['id']})")
    except Exception as e:
        print(f"Authentication failed: {e}")

def test_sets():
    try:
        client = JustTCGClient()
        sets = client.get_sets(game="mtg")
        data = sets.get('data', [])
        print(f"Found {len(data)} sets for Magic: The Gathering.")
        for s in data[:10]:  # Print first 10 sets for brevity
            print(f"- {s.get('name')} (id: {s.get('id')})")
        if len(data) > 10:
            print(f"...and {len(data)-10} more sets.")
    except Exception as e:
        print(f"Failed to fetch sets: {e}")

# Example usage (uncomment to test):
# client = JustTCGClient()
# print(client.get_cards())
# print(client.search_cards('Black Lotus'))

if __name__ == "__main__":
    print("Testing API authentication...")
    test_auth()
    print()
    print("Testing MTG sets...")
    test_sets()
    print()
