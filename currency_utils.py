import requests
from cache_manager import CacheManager

EXCHANGERATE_API_KEY = "0487b3f707f95caba1c66d77"
BASE_CURRENCY = "USD"  # Used for fetching rates, but conversion should work between any two currencies
API_URL = f"https://v6.exchangerate-api.com/v6/{EXCHANGERATE_API_KEY}/latest/{BASE_CURRENCY}"


def fetch_and_cache_rates():
    """Fetch rates from exchangerate-api.com and cache them."""
    try:
        response = requests.get(API_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("result") == "success":
                rates = data["conversion_rates"]
                CacheManager().cache_currency_rates(rates)
                return rates
    except Exception as e:
        print(f"Error fetching currency rates: {e}")
    return None


def get_conversion_rate(source_currency, target_currency):
    """Get the conversion rate from source_currency to target_currency."""
    cache = CacheManager()
    rates = cache.get_cached_currency_rates()
    if not rates:
        rates = fetch_and_cache_rates()
    if not rates:
        return None  # Could not get rates
    source = source_currency.upper()
    target = target_currency.upper()
    if source not in rates or target not in rates:
        return None
    # Convert from source to USD, then USD to target (since all rates are relative to USD)
    usd_to_source = rates[source]
    usd_to_target = rates[target]
    # To convert from source to target: (amount / usd_to_source) * usd_to_target
    return usd_to_target / usd_to_source


def convert_price(amount, target_currency, source_currency):
    """Convert amount from source_currency to target_currency."""
    rate = get_conversion_rate(source_currency, target_currency)
    if rate is None:
        return None
    try:
        return round(float(amount) * rate, 2)
    except Exception:
        return None 