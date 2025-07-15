import requests
from bs4 import BeautifulSoup
import concurrent.futures
import time
import os
import re
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def scrape_amazon(query, max_results=5):
    # Get API key from environment
    SCRAPERAPI_KEY = os.getenv('SCRAPER_API')
    
    # Try multiple ScraperAPI configurations for Amazon
    configs_to_try = [
        {
            'name': 'Basic configuration',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
            }
        },
        {
            'name': 'With country code US',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': f"https://www.amazon.com/s?k={query.replace(' ', '+')}",
                'country_code': 'us'
            }
        },
        {
            'name': 'With premium proxies',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': f"https://www.amazon.com/s?k={query.replace(' ', '+')}",
                'premium': 'true'
            }
        },
        {
            'name': 'With residential proxies',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': f"https://www.amazon.com/s?k={query.replace(' ', '+')}",
                'residential': 'true'
            }
        },
        {
            'name': 'With JavaScript rendering',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': f"https://www.amazon.com/s?k={query.replace(' ', '+')}",
                'render': 'true',
                'wait': '5000'
            }
        },
        {
            'name': 'With custom headers',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': f"https://www.amazon.com/s?k={query.replace(' ', '+')}",
                'keep_headers': 'true'
            }
        },
        {
            'name': 'With session handling',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': f"https://www.amazon.com/s?k={query.replace(' ', '+')}",
                'session_number': '1'
            }
        },
        {
            'name': 'With geolocation',
            'params': {
                'api_key': SCRAPERAPI_KEY,
                'url': f"https://www.amazon.com/s?k={query.replace(' ', '+')}",
                'geo': 'United States'
            }
        }
    ]
    
    for i, config in enumerate(configs_to_try, 1):
        try:
            print(f"Attempt {i}: {config['name']}")
            results = _scraper_api_request_with_config(config, max_results, timeout=60)
            if results:
                print(f"✅ Success with {config['name']}!")
                return results
        except Exception as e:
            print(f"❌ {config['name']} failed: {e}")
            if i < len(configs_to_try):  # Don't sleep after last attempt
                time.sleep(2)
    
    print("❌ All ScraperAPI configurations failed")
    return []

def _scraper_api_request_with_config(config, max_results, timeout=60):
    """Make ScraperAPI request with specific configuration"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    search_url = 'https://api.scraperapi.com/'
    
    try:
        print(f"  Making request with {config['name']}...")
        response = requests.get(search_url, params=config['params'], headers=headers, timeout=timeout)
        
        print(f"  Status Code: {response.status_code}")
        print(f"  Response Size: {len(response.text)} characters")
        
        if response.status_code == 200:
            print(f"  ✅ Response received successfully")
            
            return _parse_results(response.text, max_results)
        else:
            print(f"  ❌ HTTP {response.status_code}: {response.text[:200]}...")
            return []
            
    except requests.exceptions.Timeout:
        print(f"  ❌ Request timed out after {timeout} seconds")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Request failed: {e}")
        return []
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return []

def _parse_results(html_content, max_results):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try different selectors for Amazon product containers
    products = (
        soup.select('div[data-component-type="s-search-result"]') or
        soup.select('div.s-result-item') or
        soup.select('div[class*="s-result-item"]') or
        soup.select('div[data-asin]') or
        soup.select('div[class*="sg-col"]')
    )
    
    print(f"Found {len(products)} product containers")
    
    if not products:
        print("No products found with any selector")
        return []

    results = []
    for i, product in enumerate(products[:max_results]):
        try:
            print(f"\nProcessing product {i+1}:")
            
            # Try multiple selectors for product name
            name_tag = (
                product.select_one('h2 a span') or
                product.select_one('h2 span') or
                product.select_one('h2 a') or
                product.select_one('span[data-component-type="s-product-image"] a') or
                product.select_one('a[class*="a-link-normal"] span') or
                product.select_one('span[class*="a-text-normal"]')
            )
            
            # Try multiple selectors for price
            price_tag = (
                product.select_one('span.a-price-whole') or
                product.select_one('span.a-price span.a-offscreen') or
                product.select_one('span.a-price') or
                product.select_one('span[class*="a-price"]') or
                product.select_one('span[data-a-color="price"]') or
                product.select_one('span[class*="a-text-price"]')
            )
            
            # Try multiple selectors for product link
            link_tag = (
                product.select_one('h2 a') or
                product.select_one('a[class*="a-link-normal"]') or
                product.select_one('a[href*="/dp/"]') or
                product.select_one('a[data-component-type="s-product-image"]')
            )
            
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
            
            # Clean up the link
            if link and not link.startswith('http'):
                link = 'https://www.amazon.com' + link
            link = link.split('?')[0]  # Remove query parameters
            
            # Try multiple selectors for image
            image_tag = (
                product.select_one('img.s-image') or
                product.select_one('img[data-image-latency]') or
                product.select_one('img[src*="images/I"]') or
                product.select_one('img[class*="s-image"]')
            )

            # Get image URL
            image = ''
            if image_tag:
                image = image_tag.get('src') or image_tag.get('data-src', '')
                if image and not image.startswith('http'):
                    image = 'https://www.amazon.com' + image
            
            # Clean up price text
            price = re.sub(r'[^\d.,]', '', price)  # Keep only digits, dots, and commas
            if price:
                # Add currency symbol back
                price = f"${price}"
            
            # Get ASIN (Amazon Standard Identification Number) if available
            asin = product.get('data-asin', '')
            
            result = {
                'name': name,
                'price': price,
                'link': link,
                'image': image,
                'asin': asin
            }
            
            print(f"  ✅ Product {i+1} processed successfully")
            results.append(result)
            
        except Exception as e:
            print(f"  ❌ Error processing product {i+1}: {e}")
            continue
    
    print(f"\n✅ Successfully processed {len(results)} products")
    return results

def _generate_reliable_link(name, original_link):
    """Generate a more reliable Amazon search link if the original link fails"""
    if not original_link or original_link == '#':
        # Create a search link based on the product name
        search_query = re.sub(r'[^\w\s]', '', name)  # Remove special characters
        search_query = re.sub(r'\s+', '+', search_query.strip())  # Replace spaces with +
        return f"https://www.amazon.com/s?k={search_query}"
    return original_link 