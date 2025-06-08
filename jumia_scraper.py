import requests
from bs4 import BeautifulSoup
from cache_manager import CacheManager
import concurrent.futures
import time

def scrape_jumia(query, max_results=5):
    cache = CacheManager()
    
    # Try to get cached results first
    cached_results = cache.get_cached_results(query, 'jumia')
    if cached_results:
        print("Returning cached Jumia results")
        return cached_results

    SCRAPERAPI_KEY = 'afb25771be473a63ced548fe95761266'
    
    # First try direct request
    try:
        results = _direct_request(query, max_results)
        if results:
            cache.cache_results(query, 'jumia', results)
            return results
    except Exception as e:
        print(f"Direct request failed: {e}")

    # Fall back to ScraperAPI if direct request fails
    try:
        results = _scraper_api_request(query, max_results, SCRAPERAPI_KEY)
        if results:
            cache.cache_results(query, 'jumia', results)
            return results
    except Exception as e:
        print(f"ScraperAPI request failed: {e}")

    return []

def _direct_request(query, max_results, timeout=10):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }

    url = f"https://www.jumia.com.gh/catalog/?q={query.replace(' ', '+')}"
    
    response = requests.get(url, headers=headers, timeout=timeout)
    if response.status_code != 200:
        raise Exception(f"Direct request failed with status code: {response.status_code}")

    return _parse_results(response.text, max_results)

def _scraper_api_request(query, max_results, api_key, timeout=30):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    }

    target_url = f"https://www.jumia.com.gh/catalog/?q={query.replace(' ', '+')}"
    search_url = f"http://api.scraperapi.com/?api_key={api_key}&url={target_url}"

    response = requests.get(search_url, headers=headers, timeout=timeout)
    if response.status_code != 200:
        raise Exception(f"ScraperAPI request failed with status code: {response.status_code}")

    return _parse_results(response.text, max_results)

def _parse_results(html_content, max_results):
    soup = BeautifulSoup(html_content, 'html.parser')
    products = soup.select('article.prd')

    results = []
    for product in products[:max_results]:
        try:
            name_tag = product.select_one('h3.name')
            price_tag = product.select_one('div.prc')
            link_tag = product.find('a', href=True)
            image_tag = product.select_one('img')

            if not all([name_tag, price_tag, link_tag]):
                continue

            name = name_tag.get_text(strip=True)
            price = price_tag.get_text(strip=True)
            link = 'https://www.jumia.com.gh' + link_tag['href'].split('?')[0]
            image = image_tag['data-src'] if image_tag and image_tag.has_attr('data-src') else ''

            results.append({
                'name': name,
                'price': price,
                'link': link,
                'image': image
            })
        except Exception as e:
            print(f"Error parsing product: {e}")
            continue

    return results
