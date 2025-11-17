import os
import requests

from dotenv import load_dotenv

load_dotenv()

# Constants and environment variable loading
EXCHANGE_API_KEY = os.environ.get('EXCHANGE_API_KEY')
BASE_URL = 'https://v6.exchangerate-api.com/v6'

def test_auth():
    """
    Test if EXCHANGE_API_KEY is set and valid by making a simple API call.
    Prints the result of the test.
    """
    if not EXCHANGE_API_KEY:
        print("EXCHANGE_API_KEY environment variable is not set.")
        return False
    url = f"{BASE_URL}/{EXCHANGE_API_KEY}/latest/USD"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get('result') == 'success':
            print("API key is set and valid.")
            return True
        else:
            print(f"API key is set but invalid or unauthorized: {data.get('error-type')}")
            return False
    except Exception as e:
        print(f"Error testing API key: {e}")
        return False

def get_exchange_rates(base_currency='USD'):
    """
    Fetch latest exchange rates for the given base currency.
    Returns a dict of rates or None on error.
    """
    if not EXCHANGE_API_KEY:
        print("Error: EXCHANGE_API_KEY environment variable not set.")
        return None
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
    print("Testing API authentication...")
    test_auth()
    print()
    # rates = get_exchange_rates('USD')
    # if rates:
    #     print("Exchange rates for USD:")
    #     for k, v in rates.items():
    #         print(f"{k}: {v}")
    # else:
    #     print("Failed to fetch exchange rates.")
