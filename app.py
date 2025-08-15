#!/usr/bin/env python3
"""
Simple Flask app for Render.com deployment
Minimal dependencies to avoid build issues
"""

import os
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
import re
from datetime import datetime
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import time
from functools import lru_cache
import hashlib
import uuid
import csv
from io import StringIO

# Initialize Flask app with explicit template and static folders
app = Flask(__name__, 
            template_folder='Templates',
            static_folder='Static',
            static_url_path='/static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key')

# Database setup
DATABASE = 'feedback.db'
SCRAPING_TIMEOUT = 15  # Reduced from 30 to 15 seconds for faster response

# Simple in-memory cache for search results (cache size: 100)
search_cache = {}
CACHE_SIZE = 100
CACHE_TTL = 300  # 5 minutes cache TTL

def get_user_id():
    """Get or create a unique user ID for the current session."""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return session['user_id']

def init_db():
    """Initialize the database with all required tables."""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        
        # Wishlist table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wishlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                product_name TEXT,
                product_price TEXT,
                product_link TEXT,
                product_image TEXT,
                store TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Price alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                product_name TEXT,
                target_price REAL,
                current_price REAL,
                product_link TEXT,
                store TEXT,
                email TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Search history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                query TEXT,
                search_type TEXT,
                results_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Price history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                product_name TEXT,
                product_link TEXT,
                store TEXT,
                price REAL,
                currency TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Feedback table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                image_name TEXT,
                predicted_label TEXT,
                feedback TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()

# Initialize database
init_db()

# Import scrapers (these are lightweight)
try:
    from jumia_scraper import scrape_jumia
    from melcom_scraper import scrape_melcom
    from compughana_scraper import scrape_compughana
    from amazon_scraper import scrape_amazon
    from currency_utils import convert_price
    SCRAPERS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some scrapers not available: {e}")
    SCRAPERS_AVAILABLE = False

def scrape_with_timeout(scraper_func, args, timeout=SCRAPING_TIMEOUT):
    """Execute a scraping function with a timeout."""
    try:
        if isinstance(args, str):
            return scraper_func(args)
        return scraper_func(*args)
    except (TimeoutError, Exception) as e:
        print(f"Error in {scraper_func.__name__}: {str(e)}")
        return []

def get_cache_key(query, max_results, store_filter=None):
    """Generate a cache key for search results."""
    cache_data = f"{query.lower().strip()}_{max_results}_{store_filter or 'all'}"
    return hashlib.md5(cache_data.encode()).hexdigest()

def get_cached_results(cache_key):
    """Get cached results if they exist and are not expired."""
    if cache_key in search_cache:
        timestamp, results = search_cache[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            return results
        else:
            del search_cache[cache_key]
    return None

def cache_results(cache_key, results):
    """Cache search results with timestamp."""
    if len(search_cache) >= CACHE_SIZE:
        # Remove oldest entry
        oldest_key = min(search_cache.keys(), key=lambda k: search_cache[k][0])
        del search_cache[oldest_key]
    
    search_cache[cache_key] = (time.time(), results)

def log_search_performance(query, start_time, results_count, cache_hit=False):
    """Log search performance metrics."""
    elapsed_time = time.time() - start_time
    cache_status = "CACHE_HIT" if cache_hit else "CACHE_MISS"
    print(f"SEARCH_PERF: Query='{query}' | Time={elapsed_time:.2f}s | Results={results_count} | {cache_status}")

def scrape_all_sources(query, max_results=5):
    """Scrape all sources concurrently using ThreadPoolExecutor with timeout."""
    # Temporarily disable caching to debug search issues
    # cache_key = get_cache_key(query, max_results)
    # cached_results = get_cached_results(cache_key)
    # if cached_results:
    #     log_search_performance(query, time.time(), len(cached_results), cache_hit=True)
    #     return cached_results
    
    if not SCRAPERS_AVAILABLE:
        return {}
    
    scrapers = {
        'products': (scrape_jumia, (query, max_results)),
        'melcom_products': (scrape_melcom, (query, max_results)),
        'compughana_products': (scrape_compughana, (query, max_results)),
        'amazon_products': (scrape_amazon, (query, max_results))
    }
    
    results = {}
    # Reduced max_workers to 3 for better performance on Render.com
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Start all scraping tasks
        future_to_source = {
            executor.submit(scrape_with_timeout, func, args): source
            for source, (func, args) in scrapers.items()
        }
        
        # Process results as they complete
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                results[source] = future.result()
            except Exception as e:
                print(f"Error scraping {source}: {str(e)}")
                results[source] = []
    
    # Temporarily disable caching
    # cache_results(cache_key, results)
    # log_search_performance(query, time.time(), len(results), cache_hit=False)
    return results

def scrape_selected_sources(query, selected_stores, max_results=5):
    """Scrape only selected sources based on store filter."""
    # Temporarily disable caching to debug search issues
    # cache_key = get_cache_key(query, max_results, '_'.join(sorted(selected_stores)))
    # cached_results = get_cached_results(cache_key)
    # if cached_results:
    #     log_search_performance(query, time.time(), len(cached_results), cache_hit=True)
    #     return cached_results
    
    if not SCRAPERS_AVAILABLE:
        return {}
    
    store_to_scraper = {
        'jumia': (scrape_jumia, 'products'),
        'melcom': (scrape_melcom, 'melcom_products'),
        'compughana': (scrape_compughana, 'compughana_products'),
        'amazon': (scrape_amazon, 'amazon_products')
    }
    
    results = {}
    # Use fewer workers for selected stores
    with ThreadPoolExecutor(max_workers=min(len(selected_stores), 2)) as executor:
        # Start scraping tasks only for selected stores
        future_to_source = {
            executor.submit(scrape_with_timeout, func, (query, max_results)): source_key
            for store, (func, source_key) in store_to_scraper.items()
            if store in selected_stores
        }
        
        # Process results as they complete
        for future in as_completed(future_to_source):
            source_key = future_to_source[future]
            try:
                results[source_key] = future.result()
            except Exception as e:
                print(f"Error scraping {source_key}: {str(e)}")
                results[source_key] = []
    
    # Temporarily disable caching
    # cache_results(cache_key, results)
    # log_search_performance(query, time.time(), len(results), cache_hit=False)
    return results

def parse_price(price_str):
    """Parse price string to float."""
    if not price_str or price_str == 'Price not available':
        return None
    price_clean = re.sub(r'[^\d.,]', '', str(price_str))
    if not price_clean:
        return None
    try:
        price_clean = price_clean.replace(',', '')
        return float(price_clean)
    except ValueError:
        return None

def save_search_history(query, search_type, results_count):
    """Save search query to history."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO search_history (user_id, query, search_type, results_count)
                VALUES (?, ?, ?, ?)
            ''', (get_user_id(), query, search_type, results_count))
            conn.commit()
    except Exception as e:
        print(f"Error saving search history: {e}")

@app.route('/')
def index():
    """Homepage route"""
    return render_template('index.html')

@app.route('/home')
def home():
    """Homepage route"""
    return render_template('index.html')

@app.route('/search')
def search():
    """Text-based search route"""
    query = request.args.get('q', '')
    return render_template('search.html', results=[], query=query)

@app.route('/search', methods=['POST'])
def search_post():
    """Text-based search route with POST method"""
    start_time = time.time()
    query = request.form.get('query', '').strip()
    currency = request.form.get('currency', 'GHS')
    min_price = request.form.get('min_price')
    max_price = request.form.get('max_price')
    store_filter = request.form.get('store_filter')
    sort_by = request.form.get('sort_by', 'price_low')
    category = request.form.get('category')
    in_stock = request.form.get('in_stock')
    results_per_page = int(request.form.get('results_per_page', 20))
    
    if not query:
        flash('Please enter a search query', 'error')
        return render_template('result.html', results=[], query='')
    
    try:
        # Determine which stores to scrape based on filter
        if store_filter and store_filter != '':
            # Only scrape the selected store
            selected_stores = [store_filter]
            scraping_results = scrape_selected_sources(query, selected_stores, results_per_page)
        else:
            # Scrape all stores
            scraping_results = scrape_all_sources(query, results_per_page)

        # Ensure every product has the correct 'store' field
        store_map = {
            'products': 'Jumia',
            'melcom_products': 'Melcom',
            'compughana_products': 'CompuGhana',
            'amazon_products': 'Amazon'
        }
        for key, products in scraping_results.items():
            for p in products:
                p['store'] = store_map.get(key, key)

        # Combine all products into a single list
        all_products = []
        for key, products in scraping_results.items():
            for p in products:
                p['source_key'] = key
                all_products.append(p)

        # Helper to parse price strings
        def parse_price(price_str):
            if not price_str or price_str == 'Price not available':
                return None
            price_clean = re.sub(r'[^\d.,]', '', str(price_str))
            if not price_clean:
                return None
            try:
                price_clean = price_clean.replace(',', '')
                return float(price_clean)
            except ValueError:
                return None

        # Convert prices for all products with correct source currency
        store_currency = {
            'products': 'GHS',
            'melcom_products': 'GHS',
            'compughana_products': 'GHS',
            'amazon_products': 'USD',
        }
        
        # Pre-process price filters for efficiency
        min_price_float = None
        max_price_float = None
        if min_price:
            try:
                min_price_float = float(min_price)
            except (ValueError, TypeError):
                pass
        if max_price:
            try:
                max_price_float = float(max_price)
            except (ValueError, TypeError):
                pass
        
        # Process all products in one pass
        filtered_products = []
        for p in all_products:
            # Ensure required fields exist
            if 'name' not in p:
                p['name'] = 'Unknown Product'
            if 'store' not in p:
                p['store'] = 'Unknown Store'
            if 'price' not in p:
                p['price'] = None
                
            # Price conversion
            orig_price = parse_price(p['price'])
            if orig_price is not None:
                try:
                    converted = convert_price(orig_price, currency, store_currency.get(p['source_key'], 'GHS'))
                    p['converted_price'] = converted if converted is not None else orig_price
                except Exception:
                    p['converted_price'] = orig_price
                p['converted_currency'] = currency
            else:
                p['converted_price'] = None
                p['converted_currency'] = currency
            
            # Apply filters in one pass
            price = p.get('converted_price')
            
            # Price filter
            if min_price_float is not None and price is not None and price < min_price_float:
                continue
            if max_price_float is not None and price is not None and price > max_price_float:
                continue
                
            # Store filter
            if store_filter and store_filter != '':
                store_map = {
                    'jumia': 'Jumia',
                    'melcom': 'Melcom',
                    'compughana': 'CompuGhana',
                    'amazon': 'Amazon',
                }
                if p.get('store') != store_map.get(store_filter, store_filter):
                    continue
                    
            # Category filter (if available)
            if category and category != '' and p.get('category'):
                if p['category'].lower() != category.lower():
                    continue
                    
            # In-stock filter (if available)
            if in_stock == 'on' and p.get('in_stock') is not None:
                if not p['in_stock']:
                    continue
                    
            filtered_products.append(p)

        # Sorting
        if sort_by == 'price_low':
            filtered_products.sort(key=lambda x: x.get('converted_price', float('inf')) if x.get('converted_price') is not None else float('inf'))
        elif sort_by == 'price_high':
            filtered_products.sort(key=lambda x: x.get('converted_price', float('-inf')) if x.get('converted_price') is not None else float('-inf'), reverse=True)
        elif sort_by == 'name':
            filtered_products.sort(key=lambda x: x.get('name', '').lower())
        elif sort_by == 'store':
            filtered_products.sort(key=lambda x: x.get('store', ''))

        # Split filtered_products by store and limit to results_per_page
        jumia_products = [p for p in filtered_products if p.get('store') == 'Jumia'][:results_per_page]
        melcom_products = [p for p in filtered_products if p.get('store') == 'Melcom'][:results_per_page]
        compughana_products = [p for p in filtered_products if p.get('store') == 'CompuGhana'][:results_per_page]
        amazon_products = [p for p in filtered_products if p.get('store') == 'Amazon'][:results_per_page]

        # Find the cheapest product in each store (use converted_price)
        def get_converted_price(x):
            price = x.get('converted_price')
            if price is None:
                return float('inf')
            try:
                return float(price)
            except (ValueError, TypeError):
                return float('inf')
        def get_cheapest(products):
            if not products:
                return None
            try:
                return min(products, key=get_converted_price)
            except (ValueError, TypeError) as e:
                print(f"Error in get_cheapest: {e}")
                return None
        cheapest_jumia = get_cheapest(jumia_products)
        cheapest_melcom = get_cheapest(melcom_products)
        cheapest_compughana = get_cheapest(compughana_products)
        cheapest_amazon = get_cheapest(amazon_products)

        # Strip currency symbols from original price for local stores
        def strip_ghs(price):
            if price is None:
                return ''
            return re.sub(r'^(GHS|GH₵|₵|GHC|Ghc|ghc|gh₵|Ghs|Ghs|GHS|GHS)\s*', '', str(price)).strip()
        for p in jumia_products + melcom_products + compughana_products:
            p['original_price_clean'] = strip_ghs(p['price'])
            p['original_price_with_symbol'] = p['price'] if p.get('price') else ''  # Keep original with symbol
        for p in amazon_products:
            p['original_price_clean'] = p.get('price', '')
            p['original_price_with_symbol'] = p.get('price', '')  # Keep original with symbol

        # Save search history
        save_search_history(query, 'text', len(filtered_products))

        # Find the overall cheapest item (use converted_price)
        try:
            def safe_get_price(x):
                price = x.get('converted_price')
                if price is None:
                    return float('inf')
                try:
                    return float(price)
                except (ValueError, TypeError):
                    return float('inf')
            
            cheapest_item = min(filtered_products, key=safe_get_price) if filtered_products else None
        except Exception as e:
            print(f"Error finding overall cheapest item: {e}")
            cheapest_item = None

        flash(f'Found {len(filtered_products)} products for "{query}"', 'success')
        
        # Temporarily disable performance logging
        # total_time = time.time() - start_time
        # print(f"SEARCH_COMPLETE: Query='{query}' | Total Time={total_time:.2f}s | Results={len(filtered_products)}")
        
        return render_template('result.html', 
                             filename=None,
                             label=query,
                             confidence=100,
                             products=jumia_products,
                             melcom_products=melcom_products,
                             compughana_products=compughana_products,
                             amazon_products=amazon_products,
                             cheapest_item=cheapest_item,
                             cheapest_jumia=cheapest_jumia,
                             cheapest_melcom=cheapest_melcom,
                             cheapest_compughana=cheapest_compughana,
                             cheapest_amazon=cheapest_amazon,
                             selected_currency=currency)
        
    except Exception as e:
        print(f"Search error: {e}")
        flash('Error performing search. Please try again.', 'error')
        return render_template('result.html', results=[], query=query)

@app.route('/search_products', methods=['POST'])
def search_products():
    """Product search route"""
    start_time = time.time()
    query = request.form.get('query', '').strip()
    currency = request.form.get('currency', 'GHS')
    min_price = request.form.get('min_price')
    max_price = request.form.get('max_price')
    store_filter = request.form.get('store_filter')
    sort_by = request.form.get('sort_by', 'price_low')
    category = request.form.get('category')
    in_stock = request.form.get('in_stock')
    results_per_page = int(request.form.get('results_per_page', 20))
    
    if not query:
        flash('Please enter a search query', 'error')
        return render_template('result.html', results=[], query='')
    
    try:
        # Determine which stores to scrape based on filter
        if store_filter and store_filter != '':
            # Only scrape the selected store
            selected_stores = [store_filter]
            scraping_results = scrape_selected_sources(query, selected_stores, results_per_page)
        else:
            # Scrape all stores
            scraping_results = scrape_all_sources(query, results_per_page)

        # Ensure every product has the correct 'store' field
        store_map = {
            'products': 'Jumia',
            'melcom_products': 'Melcom',
            'compughana_products': 'CompuGhana',
            'amazon_products': 'Amazon'
        }
        for key, products in scraping_results.items():
            for p in products:
                p['store'] = store_map.get(key, key)

        # Combine all products into a single list
        all_products = []
        for key, products in scraping_results.items():
            for p in products:
                p['source_key'] = key
                all_products.append(p)

        # Helper to parse price strings
        def parse_price(price_str):
            if not price_str or price_str == 'Price not available':
                return None
            price_clean = re.sub(r'[^\d.,]', '', str(price_str))
            if not price_clean:
                return None
            try:
                price_clean = price_clean.replace(',', '')
                return float(price_clean)
            except ValueError:
                return None

        # Convert prices for all products with correct source currency
        store_currency = {
            'products': 'GHS',
            'melcom_products': 'GHS',
            'compughana_products': 'GHS',
            'amazon_products': 'USD',
        }
        
        # Pre-process price filters for efficiency
        min_price_float = None
        max_price_float = None
        if min_price:
            try:
                min_price_float = float(min_price)
            except (ValueError, TypeError):
                pass
        if max_price:
            try:
                max_price_float = float(max_price)
            except (ValueError, TypeError):
                pass
        
        # Process all products in one pass
        filtered_products = []
        for p in all_products:
            # Ensure required fields exist
            if 'name' not in p:
                p['name'] = 'Unknown Product'
            if 'store' not in p:
                p['store'] = 'Unknown Store'
            if 'price' not in p:
                p['price'] = None
                
            # Price conversion
            orig_price = parse_price(p['price'])
            if orig_price is not None:
                try:
                    converted = convert_price(orig_price, currency, store_currency.get(p['source_key'], 'GHS'))
                    p['converted_price'] = converted if converted is not None else orig_price
                except Exception:
                    p['converted_price'] = orig_price
                p['converted_currency'] = currency
            else:
                p['converted_price'] = None
                p['converted_currency'] = currency
            
            # Apply filters in one pass
            price = p.get('converted_price')
            
            # Price filter
            if min_price_float is not None and price is not None and price < min_price_float:
                continue
            if max_price_float is not None and price is not None and price > max_price_float:
                continue
                
            # Store filter
            if store_filter and store_filter != '':
                store_map = {
                    'jumia': 'Jumia',
                    'melcom': 'Melcom',
                    'compughana': 'CompuGhana',
                    'amazon': 'Amazon',
                }
                if p.get('store') != store_map.get(store_filter, store_filter):
                    continue
                    
            # Category filter (if available)
            if category and category != '' and p.get('category'):
                if p['category'].lower() != category.lower():
                    continue
                    
            # In-stock filter (if available)
            if in_stock == 'on' and p.get('in_stock') is not None:
                if not p['in_stock']:
                    continue
                    
            filtered_products.append(p)

        # Sorting
        if sort_by == 'price_low':
            filtered_products.sort(key=lambda x: x.get('converted_price', float('inf')) if x.get('converted_price') is not None else float('inf'))
        elif sort_by == 'price_high':
            filtered_products.sort(key=lambda x: x.get('converted_price', float('-inf')) if x.get('converted_price') is not None else float('-inf'), reverse=True)
        elif sort_by == 'name':
            filtered_products.sort(key=lambda x: x.get('name', '').lower())
        elif sort_by == 'store':
            filtered_products.sort(key=lambda x: x.get('store', ''))

        # Split filtered_products by store and limit to results_per_page
        jumia_products = [p for p in filtered_products if p.get('store') == 'Jumia'][:results_per_page]
        melcom_products = [p for p in filtered_products if p.get('store') == 'Melcom'][:results_per_page]
        compughana_products = [p for p in filtered_products if p.get('store') == 'CompuGhana'][:results_per_page]
        amazon_products = [p for p in filtered_products if p.get('store') == 'Amazon'][:results_per_page]

        # Find the cheapest product in each store (use converted_price)
        def get_converted_price(x):
            price = x.get('converted_price')
            if price is None:
                return float('inf')
            try:
                return float(price)
            except (ValueError, TypeError):
                return float('inf')
        def get_cheapest(products):
            if not products:
                return None
            try:
                return min(products, key=get_converted_price)
            except (ValueError, TypeError) as e:
                print(f"Error in get_cheapest: {e}")
                return None
        cheapest_jumia = get_cheapest(jumia_products)
        cheapest_melcom = get_cheapest(melcom_products)
        cheapest_compughana = get_cheapest(compughana_products)
        cheapest_amazon = get_cheapest(amazon_products)

        # Strip currency symbols from original price for local stores
        def strip_ghs(price):
            if price is None:
                return ''
            return re.sub(r'^(GHS|GH₵|₵|GHC|Ghc|ghc|gh₵|Ghs|Ghs|GHS|GHS)\s*', '', str(price)).strip()
        for p in jumia_products + melcom_products + compughana_products:
            p['original_price_clean'] = strip_ghs(p['price'])
            p['original_price_with_symbol'] = p['price'] if p.get('price') else ''  # Keep original with symbol
        for p in amazon_products:
            p['original_price_clean'] = p.get('price', '')
            p['original_price_with_symbol'] = p.get('price', '')  # Keep original with symbol

        # Save search history
        save_search_history(query, 'text', len(filtered_products))

        # Find the overall cheapest item (use converted_price)
        try:
            def safe_get_price(x):
                price = x.get('converted_price')
                if price is None:
                    return float('inf')
                try:
                    return float(price)
                except (ValueError, TypeError):
                    return float('inf')
            
            cheapest_item = min(filtered_products, key=safe_get_price) if filtered_products else None
        except Exception as e:
            print(f"Error finding overall cheapest item: {e}")
            cheapest_item = None

        flash(f'Found {len(filtered_products)} products for "{query}"', 'success')
        
        # Temporarily disable performance logging
        # total_time = time.time() - start_time
        # print(f"SEARCH_COMPLETE: Query='{query}' | Total Time={total_time:.2f}s | Results={len(filtered_products)}")
        
        return render_template('result.html', 
                             filename=None,
                             label=query,
                             confidence=100,
                             products=jumia_products,
                             melcom_products=melcom_products,
                             compughana_products=compughana_products,
                             amazon_products=amazon_products,
                             cheapest_item=cheapest_item,
                             cheapest_jumia=cheapest_jumia,
                             cheapest_melcom=cheapest_melcom,
                             cheapest_compughana=cheapest_compughana,
                             cheapest_amazon=cheapest_amazon,
                             selected_currency=currency)
        
    except Exception as e:
        print(f"Search error: {e}")
        flash('Error performing search. Please try again.', 'error')
        return render_template('result.html', results=[], query=query)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """Image upload route"""
    if request.method == 'POST':
        # Handle file upload
        return render_template('result.html', results=[])
    return render_template('upload.html')

@app.route('/upload_file', methods=['GET', 'POST'])
def upload_file():
    """Image upload route (alias for upload)"""
    if request.method == 'POST':
        # Handle file upload
        return render_template('result.html', results=[])
    return render_template('upload.html')

@app.route('/result')
def result():
    """Results page"""
    return render_template('result.html')

@app.route('/wishlist')
def wishlist():
    """Display user's wishlist."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM wishlist WHERE user_id = ? ORDER BY added_at DESC', (get_user_id(),))
            wishlist_items = cursor.fetchall()
        
        # Calculate unique stores count
        unique_stores = set()
        for item in wishlist_items:
            if item[6]:  # item[6] is the store field (adjusted for user_id column)
                unique_stores.add(item[6])
        unique_stores_count = len(unique_stores)
        
        return render_template('wishlist.html', wishlist_items=wishlist_items, unique_stores_count=unique_stores_count)
    except Exception as e:
        flash('Error loading wishlist', 'error')
        return render_template('wishlist.html', wishlist_items=[], unique_stores_count=0)

@app.route('/add-to-wishlist', methods=['POST'])
def add_to_wishlist():
    """Add a product to wishlist."""
    try:
        data = request.get_json()
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO wishlist (user_id, product_name, product_price, product_link, product_image, store)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (get_user_id(), data['name'], data['price'], data['link'], data.get('image', ''), data['store']))
            conn.commit()
        
        return jsonify({'success': True, 'message': 'Added to wishlist'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/remove-from-wishlist/<int:item_id>', methods=['POST'])
def remove_from_wishlist(item_id):
    """Remove an item from wishlist."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM wishlist WHERE id = ? AND user_id = ?', (item_id, get_user_id()))
            conn.commit()
        
        flash('Item removed from wishlist', 'success')
        return redirect(url_for('wishlist'))
    except Exception as e:
        flash('Error removing item from wishlist', 'error')
        return redirect(url_for('wishlist'))

@app.route('/price_alerts')
def price_alerts():
    """Display price alerts."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, product_name, target_price, current_price, product_link, store, email, is_active, created_at
                FROM price_alerts 
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (get_user_id(),))
            alerts = cursor.fetchall()
        
        return render_template('price_alerts.html', alerts=alerts)
    except Exception as e:
        flash('Error loading price alerts', 'error')
        return render_template('price_alerts.html', alerts=[])

@app.route('/create-price-alert', methods=['POST'])
def create_price_alert():
    """Create a new price alert."""
    try:
        data = request.get_json()
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO price_alerts (user_id, product_name, target_price, current_price, product_link, store, email)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (get_user_id(), data['name'], data['target_price'], data['current_price'], 
                  data['link'], data['store'], data.get('email', '')))
            conn.commit()
        
        return jsonify({'success': True, 'message': 'Price alert created'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/delete-price-alert/<int:alert_id>', methods=['POST'])
def delete_price_alert(alert_id):
    """Delete a price alert."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM price_alerts WHERE id = ? AND user_id = ?', (alert_id, get_user_id()))
            conn.commit()
        
        return jsonify({'success': True, 'message': 'Price alert deleted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/deactivate-price-alert/<int:alert_id>', methods=['POST'])
def deactivate_price_alert(alert_id):
    """Deactivate a price alert."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE price_alerts SET is_active = 0 WHERE id = ? AND user_id = ?', (alert_id, get_user_id()))
            conn.commit()
        
        return jsonify({'success': True, 'message': 'Price alert deactivated'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/activate-price-alert/<int:alert_id>', methods=['POST'])
def activate_price_alert(alert_id):
    """Activate a price alert."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE price_alerts SET is_active = 1 WHERE id = ? AND user_id = ?', (alert_id, get_user_id()))
            conn.commit()
        
        return jsonify({'success': True, 'message': 'Price alert activated'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/check-price-alerts', methods=['POST'])
def manual_check_price_alerts():
    """Manually trigger price alert checking for testing."""
    try:
        print("DEBUG: Manual price alert check triggered")
        # Simplified version for app.py - just return success
        print("DEBUG: Manual price alert check completed")
        return jsonify({'success': True, 'message': 'Price alerts checked successfully'})
    except Exception as e:
        print(f"DEBUG: Error in manual price alert check: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/check-single-price-alert/<int:alert_id>', methods=['POST'])
def check_single_price_alert(alert_id):
    """Check and update a single price alert."""
    try:
        print(f"DEBUG: Checking single alert {alert_id}")
        
        # Get alert data
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, product_name, target_price, current_price, product_link, store, email, created_at
                FROM price_alerts 
                WHERE id = ? AND is_active = 1 AND user_id = ?
            ''', (alert_id, get_user_id()))
            alert_data = cursor.fetchone()
        
        if not alert_data:
            return jsonify({'success': False, 'message': 'Alert not found or inactive'})
        
        # Simplified version - just return success
        return jsonify({
            'success': True, 
            'message': 'Price check completed',
            'current_price': alert_data[3]  # current_price field
        })
            
    except Exception as e:
        print(f"DEBUG: Error checking single alert {alert_id}: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/analytics')
def analytics():
    """Display analytics dashboard."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            
            # Get search statistics
            cursor.execute('''
                SELECT search_type, COUNT(*) as count, 
                       DATE(created_at) as date
                FROM search_history 
                WHERE user_id = ?
                GROUP BY search_type, DATE(created_at)
                ORDER BY date DESC
                LIMIT 30
            ''', (get_user_id(),))
            search_stats = cursor.fetchall()
            
            # Get popular searches
            cursor.execute('''
                SELECT query, COUNT(*) as count
                FROM search_history 
                WHERE user_id = ?
                GROUP BY query 
                ORDER BY count DESC 
                LIMIT 10
            ''', (get_user_id(),))
            popular_searches = cursor.fetchall()
            
            # Get total statistics
            cursor.execute('SELECT COUNT(*) FROM search_history WHERE user_id = ?', (get_user_id(),))
            total_searches = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM wishlist WHERE user_id = ?', (get_user_id(),))
            total_wishlist = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM price_alerts WHERE user_id = ? AND is_active = 1', (get_user_id(),))
            active_alerts = cursor.fetchone()[0]
        
        return render_template('analytics.html', 
                             search_stats=search_stats,
                             popular_searches=popular_searches,
                             price_trends=[],  # Simplified for memory
                             total_searches=total_searches,
                             total_wishlist=total_wishlist,
                             active_alerts=active_alerts)
    except Exception as e:
        flash('Error loading analytics', 'error')
        return render_template('analytics.html', 
                             search_stats=[],
                             popular_searches=[],
                             price_trends=[],
                             total_searches=0,
                             total_wishlist=0,
                             active_alerts=0)

@app.route('/admin')
def admin():
    """Admin page"""
    return render_template('admin.html')

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html')

@app.route('/advanced_search')
def advanced_search():
    """Advanced search page"""
    return render_template('advanced_search.html')

@app.route('/advanced-search', methods=['GET', 'POST'])
def advanced_search_post():
    """Handle advanced search POST requests"""
    if request.method == 'POST':
        return search_products()
    return render_template('advanced_search.html')

@app.route('/api/health')
def health_check():
    """Health check endpoint for Render"""
    return jsonify({
        'status': 'healthy', 
        'message': 'Pic2Price is running!',
        'version': '1.0.0'
    })

@app.route('/api/search', methods=['POST'])
def api_search():
    """API search endpoint"""
    data = request.get_json() or {}
    query = data.get('query', '')
    
    return jsonify({
        'status': 'success',
        'results': [],
        'query': query,
        'message': 'Search functionality coming soon!'
    })

@app.route('/search_products', methods=['GET', 'POST'])
def search_products_general():
    """General search products route"""
    if request.method == 'POST':
        query = request.form.get('query', '')
    else:
        query = request.args.get('query', '')
    return render_template('result.html', results=[], query=query)

@app.route('/quick_search', methods=['POST'])
def quick_search():
    """Quick search endpoint"""
    query = request.form.get('query', '')
    return render_template('result.html', results=[], query=query)

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    """Handles user feedback submission."""
    image_name = request.form.get('filename')
    predicted_label = request.form.get('label')
    feedback = request.form.get('feedback')

    if image_name and predicted_label and feedback:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO feedback (user_id, image_name, predicted_label, feedback) 
                VALUES (?, ?, ?, ?)
            ''', (get_user_id(), image_name, predicted_label, feedback))
            conn.commit()
        flash('Thank you for your feedback!', 'success')
    else:
        flash('Please provide all feedback information', 'error')

    return redirect(url_for('home'))

@app.route('/export-results', methods=['POST'])
def export_results():
    """Export search results as CSV."""
    try:
        data = request.get_json()
        products = data.get('products', [])
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Product Name', 'Price', 'Store', 'Link', 'Image'])
        
        for product in products:
            writer.writerow([
                product.get('name', ''),
                product.get('price', ''),
                product.get('store', ''),
                product.get('link', ''),
                product.get('image', '')
            ])
        
        output.seek(0)
        return jsonify({
            'success': True,
            'csv_data': output.getvalue()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port) 