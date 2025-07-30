from dotenv import load_dotenv
import os
load_dotenv()

import requests
from bs4 import BeautifulSoup
from cache_manager import CacheManager
import concurrent.futures
import time
import re

# Use the key from the .env file
SCRAPERAPI_KEY = os.getenv('SCRAPER_API', '')
print(f"[JUMIA SCRAPER] Using API key: {SCRAPERAPI_KEY[:6]}... (length: {len(SCRAPERAPI_KEY)})")

def scrape_jumia(query, max_results=5):
    cache = CacheManager()
    
    # Try to get cached results first
    cached_results = cache.get_cached_results(query, 'jumia')
    if cached_results:
        print("Returning cached Jumia results")
        return cached_results

    # Use the key from the .env file
    # SCRAPERAPI_KEY is already set above
    try:
        results = _scraper_api_request(query, max_results, SCRAPERAPI_KEY)
        if results:
            cache.cache_results(query, 'jumia', results)
            return results
    except Exception as e:
        print(f"ScraperAPI request failed: {e}")

    return []

def _scraper_api_request(query, max_results, api_key, timeout=30):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }

    target_url = f"https://www.jumia.com.gh/catalog/?q={query.replace(' ', '+')}"
    
    # Add ScraperAPI parameters for better success rate
    params = {
        'api_key': api_key,
        'url': target_url
    }
    
    search_url = 'http://api.scraperapi.com/'
    
    try:
        response = requests.get(search_url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()  # Raise exception for bad status codes
        
        return _parse_results(response.text, max_results)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status code: {e.response.status_code}")
            print(f"Response headers: {e.response.headers}")
        raise

def _parse_results(html_content, max_results):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try different selectors for product containers - updated for new structure
    products = soup.select('article.prd') or soup.select('article[class*="prd"]') or soup.select('div.c-prd') or soup.select('div[data-prd]')
    
    print(f"Found {len(products)} product containers")
    
    if not products:
        print("No products found with any selector")
        return []

    results = []
    for i, product in enumerate(products[:max_results]):
        try:
            print(f"\nProcessing product {i+1}:")
            
            # Updated selectors based on the HTML structure shown in the logs
            name_tag = (
                product.select_one('h2.name') or 
                product.select_one('h2[class*="name"]') or
                product.select_one('h3.name') or 
                product.select_one('h3[class*="name"]') or
                product.select_one('div[class*="name"]') or
                product.select_one('a[class*="name"]')
            )
            
            price_tag = (
                product.select_one('p.prc') or
                product.select_one('p[class*="prc"]') or
                product.select_one('div.prc') or
                product.select_one('div[class*="prc"]') or
                product.select_one('div[class*="price"]')
            )
            
            # Look for product links - find the first <a> with href starting with '/' and not containing '/cart/' or '/customer/'
            link_tag = None
            for a in product.find_all('a', href=True):
                href = a['href']
                if href.startswith('/') and '/cart/' not in href and '/customer/' not in href and '.html' in href:
                    link_tag = a
                    break
                    
            print(f"  Name tag found: {name_tag is not None}")
            print(f"  Price tag found: {price_tag is not None}")
            print(f"  Link tag found: {link_tag is not None}")
            
            if not all([name_tag, price_tag, link_tag]):
                print(f"  Missing required elements for product {i+1}")
                continue

            name = name_tag.get_text(strip=True)
            price = price_tag.get_text(strip=True)
            link = link_tag.get('href')
            
            print(f"  Name: {name}")
            print(f"  Price: {price}")
            print(f"  Link: {link}")
            
            if link and not link.startswith('http'):
                link = 'https://www.jumia.com.gh' + link
            link = link.split('?')[0]  # Remove query parameters
            
            image_tag = product.select_one('img')

            # Get image URL
            image = ''
            if image_tag:
                image = image_tag.get('data-src') or image_tag.get('src', '')
                if image and not image.startswith('http'):
                    image = 'https://www.jumia.com.gh' + image

            # Generate a more reliable link
            reliable_link = _generate_reliable_link(name, link)
            
            # Check for out-of-stock indicator
            in_stock = True
            out_of_stock_tag = product.find(string=re.compile("out of stock", re.I))
            if out_of_stock_tag:
                in_stock = False

            results.append({
                'name': name or '',
                'price': price or '',
                'link': reliable_link or '',
                'image': image or '',
                'in_stock': in_stock if in_stock is not None else True
            })
            
            print(f"  Successfully processed product {i+1}")
            
        except Exception as e:
            print(f"Error parsing product {i+1}: {e}")
            continue

    print(f"\nTotal products successfully parsed: {len(results)}")
    return results

def _generate_reliable_link(name, original_link):
    """Generate a more reliable product link"""
    try:
        # Clean the product name for URL generation
        clean_name = re.sub(r'[^\w\s-]', '', name.lower())
        clean_name = re.sub(r'[-\s]+', '-', clean_name)
        clean_name = clean_name.strip('-')
        
        # If we have a good original link, use it
        if original_link and 'jumia.com.gh' in original_link:
            return original_link
        
        # Otherwise, create a search link
        search_query = name.replace(' ', '+')
        return f"https://www.jumia.com.gh/catalog/?q={search_query}"
        
    except Exception as e:
        print(f"Error generating reliable link: {e}")
        # Fallback to search page
        search_query = name.replace(' ', '+')
        return f"https://www.jumia.com.gh/catalog/?q={search_query}"
