import requests
from bs4 import BeautifulSoup
import os
import re
import time
from cache_manager import CacheManager

def scrape_compughana(query, max_results=5):
    SCRAPERAPI_KEY = os.getenv('SCRAPERAPI_KEY', '38bde1db8b81b05543c7c870d085a6f7')
    cache = CacheManager()
    cached_results = cache.get_cached_results(query, 'compughana')
    if cached_results:
        print("Returning cached CompuGhana results")
        return cached_results

    search_url = f"https://compughana.com/catalogsearch/result/?q={query.replace(' ', '+')}"
    configs_to_try = [
        {
            'name': 'Basic configuration',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': search_url
            }
        },
        {
            'name': 'With country code GH',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': search_url,
                'country_code': 'gh'
            }
        },
        {
            'name': 'With premium proxies',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': search_url,
                'premium': 'true'
            }
        },
        {
            'name': 'With residential proxies',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': search_url,
                'residential': 'true'
            }
        },
        {
            'name': 'With JavaScript rendering',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': search_url,
                'render': 'true',
                'wait': '3000'
            }
        },
        {
            'name': 'With custom headers',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': search_url,
                'keep_headers': 'true'
            }
        },
        {
            'name': 'With session handling',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': search_url,
                'session_number': '1'
            }
        },
        {
            'name': 'With geolocation',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': search_url,
                'geo': 'Ghana'
            }
        }
    ]

    for i, config in enumerate(configs_to_try, 1):
        try:
            print(f"Attempt {i}: {config['name']}")
            results = _scraper_api_request_with_config(config, max_results, timeout=60)
            if results:
                print(f"✅ Success with {config['name']}!")
                cache.cache_results(query, 'compughana', results)
                return results
        except Exception as e:
            print(f"❌ {config['name']} failed: {e}")
            if i < len(configs_to_try):
                time.sleep(2)

    print("❌ All ScraperAPI configurations failed")
    return []

def _scraper_api_request_with_config(config, max_results, timeout=60):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    search_url = 'https://api.scraperapi.com/'
    print(f"  Making request with {config['name']}...")
    response = requests.get(search_url, params=config['params'], headers=headers, timeout=timeout)
    print(f"  Status Code: {response.status_code}")
    print(f"  Response Size: {len(response.text)} characters")
    if response.status_code == 200:
        print(f"  ✅ Response received successfully")
        debug_filename = f"compughana_debug_{config['name'].replace(' ', '_').lower()}.html"
        with open(debug_filename, 'w', encoding='utf-8') as f:
            f.write(response.text)
        return _parse_results(response.text, max_results)
    else:
        print(f"  ❌ HTTP {response.status_code}: {response.text[:200]}...")
        return []

def _parse_results(html_content, max_results):
    soup = BeautifulSoup(html_content, 'html.parser')
    products = soup.select('li.product-item')
    print(f"Found {len(products)} product containers")
    results = []
    for i, product in enumerate(products):
        if len(results) >= max_results:
            break
        try:
            name_tag = product.select_one('.product-item-link')
            price_tag = product.select_one('.price')
            link_tag = name_tag
            # Try multiple selectors for image
            image_tag = (
                product.select_one('img.product-image-photo') or
                product.select_one('img')
            )
            name = name_tag.get_text(strip=True) if name_tag else ''
            price = price_tag.get_text(strip=True) if price_tag else 'Price not available'
            link = link_tag['href'] if link_tag and link_tag.has_attr('href') else ''
            # Try all possible image attributes
            image = ''
            if image_tag:
                for attr in ['data-src', 'src', 'data-original', 'data-lazy']:
                    image = image_tag.get(attr)
                    if image:
                        break
                if image and not image.startswith('http'):
                    image = 'https://compughana.com' + image
            if not image:
                print(f"No image found for product {i+1}, HTML: {str(product)[:300]}")
            if link and not link.startswith('http'):
                link = 'https://compughana.com' + link
            if name:
                results.append({
                    'name': name,
                    'price': price,
                    'link': link,
                    'image': image
                })
        except Exception as e:
            print(f"Error parsing product {i+1}: {e}")
            continue
    print(f"Total products successfully parsed: {len(results)}")
    return results

def _generate_reliable_link(name, original_link):
    """Generate a more reliable product link"""
    try:
        # Clean the product name for URL generation
        clean_name = re.sub(r'[^\w\s-]', '', name.lower())
        clean_name = re.sub(r'[-\s]+', '-', clean_name)
        clean_name = clean_name.strip('-')
        
        # If we have a good original link, use it
        if original_link and 'compughana.com' in original_link:
            return original_link
        
        # Otherwise, create a search link
        search_query = name.replace(' ', '+')
        return f"https://compughana.com/search?q={search_query}"
        
    except Exception as e:
        print(f"Error generating reliable link: {e}")
        # Fallback to search page
        search_query = name.replace(' ', '+')
        return f"https://compughana.com/search?q={search_query}" 