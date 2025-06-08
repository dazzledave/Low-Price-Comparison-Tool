import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
from cache_manager import CacheManager
import concurrent.futures
import time

def scrape_melcom(query, max_results=5):
    cache = CacheManager()
    
    # Try to get cached results first
    cached_results = cache.get_cached_results(query, 'melcom')
    if cached_results:
        print("Returning cached Melcom results")
        return cached_results

    # Try mobile API with timeout
    try:
        results = _mobile_api_request(query, max_results)
        if results:
            cache.cache_results(query, 'melcom', results)
            return results
    except Exception as e:
        print(f"Mobile API request failed: {e}")

    # Fall back to ScraperAPI
    try:
        results = _scraper_api_request(query, max_results)
        if results:
            cache.cache_results(query, 'melcom', results)
            return results
    except Exception as e:
        print(f"ScraperAPI request failed: {e}")

    return []

def _mobile_api_request(query, max_results, timeout=15):
    encoded_query = urllib.parse.quote(query)
    api_url = f"https://melcom.com/rest/V1/products?searchCriteria[filterGroups][0][filters][0][field]=name&searchCriteria[filterGroups][0][filters][0][value]=%25{encoded_query}%25&searchCriteria[filterGroups][0][filters][0][conditionType]=like&searchCriteria[pageSize]={max_results}&searchCriteria[currentPage]=1"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
        'Accept': 'application/json',
        'Store': 'default'
    }

    response = requests.get(api_url, headers=headers, timeout=timeout)
    if response.status_code != 200:
        raise Exception(f"Mobile API request failed with status code: {response.status_code}")

    data = response.json()
    if not isinstance(data, dict) or 'items' not in data:
        raise Exception("Invalid API response format")

    results = []
    for item in data['items'][:max_results]:
        try:
            name = item.get('name', '')
            price = str(item.get('price', '0.00'))
            sku = item.get('sku', '')
            
            # Get the first image if available
            image = ''
            if 'media_gallery_entries' in item and item['media_gallery_entries']:
                image = item['media_gallery_entries'][0].get('file', '')
                if image and not image.startswith('http'):
                    image = f"https://melcom.com/media/catalog/product{image}"
            
            # Construct the product URL
            url_key = item.get('url_key', '') or sku
            link = f"https://melcom.com/catalog/product/view/id/{item.get('id', '')}"
            if url_key:
                link = f"https://melcom.com/{url_key}.html"
            
            results.append({
                'name': name,
                'price': f"GHS {price}",
                'link': link,
                'image': image
            })
        except Exception as e:
            print(f"Error processing product from API: {e}")
            continue

    return results

def _scraper_api_request(query, max_results, timeout=30):
    SCRAPERAPI_KEY = 'afb25771be473a63ced548fe95761266'
    target_url = f"https://melcom.com/catalogsearch/result/?q={urllib.parse.quote(query)}"
    search_url = f"http://api.scraperapi.com/?api_key={SCRAPERAPI_KEY}&render=true&premium=true&country_code=gh&url={target_url}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    
    response = requests.get(search_url, headers=headers, timeout=timeout)
    if response.status_code != 200:
        raise Exception(f"ScraperAPI request failed with status code: {response.status_code}")

    return _parse_html_results(response.text, max_results)

def _parse_html_results(html_content, max_results):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try multiple selectors
    product_cards = (
        soup.select("ol.products.list.items.product-items > li.item.product.product-item") or
        soup.select(".products-grid .product-item") or
        soup.select(".product-items .product-item") or
        soup.select("[data-container='product-grid'] .product-item")
    )
    
    results = []
    for card in product_cards[:max_results]:
        try:
            # Product name
            name_elem = (
                card.select_one("a.product-item-link") or
                card.select_one("a.product-name") or
                card.select_one("strong.product.name.product-item-name a")
            )
            
            # Price
            price_elem = (
                card.select_one("span[data-price-type='finalPrice'] .price") or
                card.select_one(".special-price .price") or
                card.select_one(".price-box .price")
            )
            
            # Link
            link_elem = name_elem if name_elem else card.select_one("a[href*='/catalog/']")
            
            # Image
            image_elem = (
                card.select_one("img.product-image-photo") or
                card.select_one("img.photo.image")
            )
            
            if not all([name_elem, price_elem, link_elem]):
                continue
                
            name = name_elem.text.strip()
            price = price_elem.text.strip()
            link = link_elem['href']
            image = image_elem['src'] if image_elem and image_elem.has_attr('src') else ""

            results.append({
                "name": name,
                "price": price,
                "link": link,
                "image": image
            })
        except Exception as e:
            print(f"Error parsing product from HTML: {e}")
            continue

    return results
