import requests
import json
import os

# Load API key from auth.json
AUTH_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'auth.json')
with open(AUTH_PATH) as f:
    auth = json.load(f)

EXCHANGE_API_KEY = auth['exchange_rates']['api_key']
BASE_URL = 'https://v6.exchangerate-api.com/v6'


def get_exchange_rates(base_currency='USD'):
    """
    Fetch latest exchange rates for the given base currency.
    Returns a dict of rates or None on error.
    """
    url = f"{BASE_URL}/{EXCHANGE_API_KEY}/latest/{base_currency}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get('result') == 'success':
            return data['conversion_rates']
        else:
            print(f"API error: {data.get('error-type')}")
            return None
    except Exception as e:
        print(f"Error fetching exchange rates: {e}")
        return None

if __name__ == "__main__":
    rates = get_exchange_rates('USD')
    if rates:
        print("Exchange rates for USD:")
        for k, v in rates.items():
            print(f"{k}: {v}")
    else:
        print("Failed to fetch exchange rates.")
