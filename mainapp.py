from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from werkzeug.utils import secure_filename
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from image_recognition import predict_image
from jumia_scraper import scrape_jumia
from melcom_scraper import scrape_melcom
from compughana_scraper import scrape_compughana
from amazon_scraper import scrape_amazon
import time
import re
from currency_utils import convert_price
from datetime import datetime, timedelta
import json
import csv
from io import StringIO
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import schedule

try:
    from config import *
except ImportError:
    # Default email configuration if config.py doesn't exist
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USER = 'your-email@gmail.com'
    EMAIL_PASSWORD = 'your-app-password'
    PRICE_CHECK_INTERVAL_HOURS = 6
    MAX_PRICE_CHECKS_PER_RUN = 10
    DELAY_BETWEEN_CHECKS = 2
    SENDER_NAME = 'Pic2Price Price Alerts'
    EMAIL_SUBJECT_PREFIX = 'Price Alert:'

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

# Configurations
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
DATABASE = 'feedback.db'
SCRAPING_TIMEOUT = 30  # seconds

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Ensure database is initialized
def init_db():
    """Initialize the database with all required tables."""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        
        # Feedback table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_name TEXT,
                predicted_label TEXT,
                feedback TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Wishlist table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wishlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                product_name TEXT,
                product_link TEXT,
                store TEXT,
                price REAL,
                currency TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()

init_db()  # Initialize DB on app start

def send_price_alert_email(alert_data, current_price, store_currency):
    """Send email notification when target price is reached."""
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = alert_data['email']
        msg['Subject'] = f"Price Alert: {alert_data['name']} is now {store_currency} {current_price:.2f}!"
        
        # Email body
        body = f"""
        <html>
        <body>
            <h2>🎉 Price Alert Triggered!</h2>
            <p>Good news! The price of <strong>{alert_data['name']}</strong> has dropped to your target price!</p>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
                <h3>Price Details:</h3>
                <ul>
                    <li><strong>Product:</strong> {alert_data['name']}</li>
                    <li><strong>Current Price:</strong> {store_currency} {current_price:.2f}</li>
                    <li><strong>Your Target Price:</strong> {store_currency} {alert_data['target_price']:.2f}</li>
                    <li><strong>Store:</strong> {alert_data['store']}</li>
                </ul>
            </div>
            
            <p><a href="{alert_data['link']}" style="background: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px;">View Product</a></p>
            
            <p style="color: #666; font-size: 12px;">
                This alert will be automatically deactivated. You can create a new alert if needed.
            </p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Send email
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"Price alert email sent for {alert_data['name']} at {store_currency} {current_price:.2f}")
        return True
        
    except Exception as e:
        print(f"Error sending price alert email: {e}")
        return False

def check_price_for_alert(alert_id, alert_data, update_current_price=False):
    """Check current price for a specific alert and send notification if target is reached."""
    try:
        # Use existing scrapers to get current price
        product_name = alert_data['name']
        store = alert_data['store']
        
        print(f"DEBUG: Checking price for '{product_name}' on {store}")
        
        # Map store names to scraper functions and currencies
        store_scrapers = {
            'Jumia': (scrape_jumia, 'GHS'),
            'Melcom': (scrape_melcom, 'GHS'),
            'CompuGhana': (scrape_compughana, 'GHS'),
            'Amazon': (scrape_amazon, 'USD')
        }
        
        if store not in store_scrapers:
            print(f"Unknown store: {store}")
            return None
        
        # Scrape current price - only the specific store
        scraper_func, store_currency = store_scrapers[store]
        current_products = scraper_func(product_name, max_results=10)  # Get more results for better matching
        
        if not current_products:
            print(f"No products found for {product_name} on {store}")
            return None
        
        print(f"DEBUG: Found {len(current_products)} products on {store}")
        
        # Find the best match by name similarity and price
        best_product = None
        best_match_score = 0
        
        for product in current_products:
            current_name = product.get('name', '').lower()
            target_name = product_name.lower()
            
            # Simple name matching - check if key words match
            target_words = set(target_name.split())
            current_words = set(current_name.split())
            common_words = target_words.intersection(current_words)
            
            # Calculate match score based on common words
            if len(target_words) > 0:
                match_score = len(common_words) / len(target_words)
            else:
                match_score = 0
            
            print(f"DEBUG: Product '{product.get('name', '')}' - Match score: {match_score:.2f}")
            
            if match_score > best_match_score:
                best_match_score = match_score
                best_product = product
        
        if not best_product or best_match_score < 0.3:  # Require at least 30% word match
            print(f"DEBUG: No good match found for '{product_name}' on {store}")
            return None
        
        print(f"DEBUG: Best match found: '{best_product.get('name', '')}' (score: {best_match_score:.2f})")
        
        # Parse price
        current_price_str = best_product.get('price', '0')
        import re
        price_clean = re.sub(r'[^\d.,]', '', str(current_price_str))
        if price_clean:
            current_price = float(price_clean.replace(',', ''))
        else:
            current_price = 0
        
        print(f"DEBUG: Current price: {store_currency} {current_price:.2f}, Target: {store_currency} {alert_data['target_price']:.2f}")
        
        # Update current price in database if requested
        if update_current_price and current_price > 0:
            with sqlite3.connect(DATABASE) as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE price_alerts SET current_price = ? WHERE id = ?', (current_price, alert_id))
                conn.commit()
            print(f"DEBUG: Updated current price to {store_currency} {current_price:.2f} for alert {alert_id}")
        
        # Check if target price is reached (current price is lower than or equal to target)
        if current_price > 0 and current_price <= alert_data['target_price']:
            print(f"DEBUG: Target price reached! Current: {store_currency} {current_price:.2f} <= Target: {store_currency} {alert_data['target_price']:.2f}")
            # Send notification
            if send_price_alert_email(alert_data, current_price, store_currency):
                # Deactivate alert
                with sqlite3.connect(DATABASE) as conn:
                    cursor = conn.cursor()
                    cursor.execute('UPDATE price_alerts SET is_active = 0 WHERE id = ?', (alert_id,))
                    conn.commit()
                print(f"Alert {alert_id} deactivated - target price reached!")
            return current_price
        else:
            print(f"DEBUG: Target price not reached. Current: {store_currency} {current_price:.2f} > Target: {store_currency} {alert_data['target_price']:.2f}")
            return current_price
        
    except Exception as e:
        print(f"Error checking price for alert {alert_id}: {e}")
        return None

def check_all_price_alerts():
    """Check all active price alerts."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, product_name, target_price, current_price, product_link, store, email, created_at
                FROM price_alerts 
                WHERE is_active = 1
                ORDER BY created_at ASC
                LIMIT ?
            ''', (MAX_PRICE_CHECKS_PER_RUN,))
            active_alerts = cursor.fetchall()
        
        print(f"DEBUG: Found {len(active_alerts)} active price alerts")
        
        if not active_alerts:
            print("DEBUG: No active alerts found")
            return
        
        for alert in active_alerts:
            alert_data = {
                'id': alert[0],
                'name': alert[1],
                'target_price': alert[2],
                'current_price': alert[3],
                'link': alert[4],
                'store': alert[5],
                'email': alert[6],
                'created_at': alert[7]
            }
            
            print(f"DEBUG: Checking alert {alert[0]} for product: {alert[1]}")
            # Check price for this alert
            check_price_for_alert(alert[0], alert_data)
            
            # Small delay to avoid overwhelming servers
            time.sleep(DELAY_BETWEEN_CHECKS)
            
    except Exception as e:
        print(f"DEBUG: Error in check_all_price_alerts: {e}")

def start_price_monitoring():
    """Start the background price monitoring service."""
    def run_scheduler():
        # Schedule price checks based on config
        schedule.every(PRICE_CHECK_INTERVAL_HOURS).hours.do(check_all_price_alerts)
        
        # Run initial check after 5 minutes
        schedule.every(5).minutes.do(check_all_price_alerts)
        
        print(f"Price monitoring service started! Checking every {PRICE_CHECK_INTERVAL_HOURS} hours.")
        
        # Keep the scheduler running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    # Start monitoring in a separate thread
    monitor_thread = threading.Thread(target=run_scheduler, daemon=True)
    monitor_thread.start()
    print("Price monitoring service started!")

# Start price monitoring when app starts
start_price_monitoring()

def allowed_file(filename):
    """Check if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def scrape_with_timeout(scraper_func, args, timeout=SCRAPING_TIMEOUT):
    """Execute a scraping function with a timeout."""
    try:
        if isinstance(args, str):
            return scraper_func(args)
        return scraper_func(*args)
    except (TimeoutError, Exception) as e:
        print(f"Error in {scraper_func.__name__}: {str(e)}")
        return []

def scrape_all_sources(query, max_results=5):
    """Scrape all sources concurrently using ThreadPoolExecutor with timeout."""
    scrapers = {
        'products': (scrape_jumia, (query, max_results)),
        'melcom_products': (scrape_melcom, (query, max_results)),
        'compughana_products': (scrape_compughana, (query, max_results)),
        'amazon_products': (scrape_amazon, (query, max_results))
    }
    
    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
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
    
    return results

def scrape_selected_sources(query, selected_stores, max_results=5):
    """Scrape only selected sources based on store filter."""
    store_to_scraper = {
        'jumia': (scrape_jumia, 'products'),
        'melcom': (scrape_melcom, 'melcom_products'),
        'compughana': (scrape_compughana, 'compughana_products'),
        'amazon': (scrape_amazon, 'amazon_products')
    }
    
    results = {}
    with ThreadPoolExecutor(max_workers=len(selected_stores)) as executor:
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
    
    return results

def save_search_history(query, search_type, results_count):
    """Save search query to history."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO search_history (query, search_type, results_count)
                VALUES (?, ?, ?)
            ''', (query, search_type, results_count))
            conn.commit()
    except Exception as e:
        print(f"Error saving search history: {e}")

def save_price_history(products, currency):
    """Save current prices to history."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            for store, product_list in products.items():
                for product in product_list:
                    if product.get('converted_price'):
                        cursor.execute('''
                            INSERT INTO price_history (product_name, product_link, store, price, currency)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (product['name'], product['link'], product['store'], 
                              product['converted_price'], currency))
            conn.commit()
    except Exception as e:
        print(f"Error saving price history: {e}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            try:
                # Save and process the image
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                # Get selected model from form
                model_name = request.form.get('model', 'clip')
                currency = request.form.get('currency', 'GHS')
                results_per_page = int(request.form.get('results_per_page', 5))

                # Get image recognition results
                label, confidence = predict_image(file_path, model_name)
                
                # Start concurrent scraping with timeout
                scraping_results = scrape_all_sources(label, results_per_page)
                
                # Save search history
                total_results = sum(len(products) for products in scraping_results.values())
                save_search_history(label, 'image', total_results)
                
                # Helper to parse price strings
                def parse_price(price_str):
                    if not price_str or price_str == 'Price not available':
                        return None
                    # Remove currency symbols and common text
                    price_clean = re.sub(r'[^\d.,]', '', str(price_str))
                    if not price_clean:
                        return None
                    try:
                        # Handle comma-separated thousands
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
                for key in ['products', 'melcom_products', 'compughana_products', 'amazon_products']:
                    for p in scraping_results.get(key, []):
                        orig_price = parse_price(p['price'])
                        if orig_price is not None:
                            converted = convert_price(orig_price, currency, store_currency[key])
                            p['converted_price'] = converted if converted is not None else orig_price
                            p['converted_currency'] = currency
                        else:
                            p['converted_price'] = None
                            p['converted_currency'] = currency

                # Find the overall cheapest item (use converted_price)
                cheapest_item = None
                all_products = []
                if scraping_results.get('products', []):
                    for p in scraping_results['products']:
                        p['store'] = 'Jumia'
                    all_products.extend(scraping_results['products'])
                if scraping_results.get('melcom_products', []):
                    for p in scraping_results['melcom_products']:
                        p['store'] = 'Melcom'
                    all_products.extend(scraping_results['melcom_products'])
                if scraping_results.get('compughana_products', []):
                    for p in scraping_results['compughana_products']:
                        p['store'] = 'CompuGhana'
                    all_products.extend(scraping_results['compughana_products'])
                if scraping_results.get('amazon_products', []):
                    for p in scraping_results['amazon_products']:
                        p['store'] = 'Amazon'
                    all_products.extend(scraping_results['amazon_products'])
                def get_converted_price(x):
                    price = x.get('converted_price')
                    return price if price is not None else float('inf')
                if all_products:
                    cheapest_item = min(all_products, key=get_converted_price)
                # Find the cheapest product in each store (use converted_price)
                def get_cheapest(products):
                    if not products:
                        return None
                    try:
                        return min(products, key=get_converted_price)
                    except (ValueError, TypeError):
                        return None
                cheapest_jumia = get_cheapest(scraping_results.get('products', []))
                cheapest_melcom = get_cheapest(scraping_results.get('melcom_products', []))
                cheapest_compughana = get_cheapest(scraping_results.get('compughana_products', []))
                cheapest_amazon = get_cheapest(scraping_results.get('amazon_products', []))
                # Strip currency symbols from original price for local stores
                def strip_ghs(price):
                    return re.sub(r'^(GHS|GH₵|₵|GHC|Ghc|ghc|gh₵|Ghs|Ghs|GHS|GHS)\s*', '', str(price)).strip()
                for key in ['products', 'melcom_products', 'compughana_products']:
                    for p in scraping_results.get(key, []):
                        p['original_price_clean'] = strip_ghs(p['price'])
                        p['original_price_with_symbol'] = p['price']  # Keep original with symbol
                for p in scraping_results.get('amazon_products', []):
                    p['original_price_clean'] = p['price']
                    p['original_price_with_symbol'] = p['price']  # Keep original with symbol

                # Save price history
                save_price_history(scraping_results, currency)

                flash(f'Successfully found {total_results} products for "{label}"', 'success')
                return render_template(
                    'result.html',
                    label=label,
                    confidence=confidence,
                    filename=filename,
                    products=scraping_results.get('products', []),
                    melcom_products=scraping_results.get('melcom_products', []),
                    compughana_products=scraping_results.get('compughana_products', []),
                    amazon_products=scraping_results.get('amazon_products', []),
                    cheapest_item=cheapest_item,
                    cheapest_jumia=cheapest_jumia,
                    cheapest_melcom=cheapest_melcom,
                    cheapest_compughana=cheapest_compughana,
                    cheapest_amazon=cheapest_amazon,
                    selected_currency=currency
                )
            except Exception as e:
                print(f"Error processing upload: {str(e)}")
                flash('Error processing your request. Please try again.', 'error')
                return render_template('error.html', error="Error processing your request. Please try again.")

    return render_template('upload.html')

@app.route('/search', methods=['POST'])
def search_products():
    """Handle advanced product search."""
    query = request.form.get('query', '').strip()
    currency = request.form.get('currency', 'GHS')
    min_price = request.form.get('min_price')
    max_price = request.form.get('max_price')
    store_filter = request.form.get('store_filter')
    sort_by = request.form.get('sort_by', 'price_low')
    category = request.form.get('category')
    in_stock = request.form.get('in_stock')
    results_per_page = int(request.form.get('results_per_page', 20))
    page = int(request.form.get('page', 1))

    if not query:
        flash('Please enter a search query', 'error')
        return redirect(url_for('advanced_search'))

    try:
        # Determine which stores to scrape based on filter
        if store_filter and store_filter != '':
            # Only scrape the selected store
            selected_stores = [store_filter]
            scraping_results = scrape_selected_sources(query, selected_stores, results_per_page)
        else:
            # Scrape all stores
            scraping_results = scrape_all_sources(query, results_per_page)

        print(f"DEBUG: Scraping results keys: {list(scraping_results.keys())}")
        for key, products in scraping_results.items():
            print(f"DEBUG: {key} has {len(products)} products")

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

        print(f"DEBUG: Total products before price conversion: {len(all_products)}")

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
        for p in all_products:
            print(f"DEBUG: Processing product: {p.get('name', 'Unknown')[:50]}...")
            print(f"DEBUG: Original price: {p.get('price', 'None')}")
            
            # Ensure price field exists
            if 'price' not in p:
                p['price'] = None
                
            orig_price = parse_price(p['price'])
            print(f"DEBUG: Parsed price: {orig_price}")
            
            if orig_price is not None:
                try:
                    converted = convert_price(orig_price, currency, store_currency.get(p['source_key'], 'GHS'))
                    print(f"DEBUG: Converted price: {converted}")
                    p['converted_price'] = converted if converted is not None else orig_price
                except Exception as e:
                    print(f"DEBUG: Error in price conversion: {e}")
                    p['converted_price'] = orig_price
                p['converted_currency'] = currency
            else:
                p['converted_price'] = None
                p['converted_currency'] = currency
            print(f"DEBUG: Final converted_price: {p['converted_price']}")

        print(f"DEBUG: Starting price filtering...")
        # Apply advanced filters
        filtered_products = []
        for p in all_products:
            # Ensure all required fields exist
            if 'name' not in p:
                p['name'] = 'Unknown Product'
            if 'store' not in p:
                p['store'] = 'Unknown Store'
            if 'converted_price' not in p:
                p['converted_price'] = None
                
            # Price filter
            price = p.get('converted_price')
            print(f"DEBUG: Checking product {p.get('name', 'Unknown')[:30]} with price: {price}")
            
            if min_price and price is not None:
                try:
                    min_price_float = float(min_price)
                    print(f"DEBUG: Comparing {price} < {min_price_float}")
                    if price < min_price_float:
                        print(f"DEBUG: Skipping - price too low")
                        continue
                except (ValueError, TypeError) as e:
                    print(f"DEBUG: Error in min_price comparison: {e}")
                    pass
            if max_price and price is not None:
                try:
                    max_price_float = float(max_price)
                    print(f"DEBUG: Comparing {price} > {max_price_float}")
                    if price > max_price_float:
                        print(f"DEBUG: Skipping - price too high")
                        continue
                except (ValueError, TypeError) as e:
                    print(f"DEBUG: Error in max_price comparison: {e}")
                    pass
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

        print(f"DEBUG: Filtered products count: {len(filtered_products)}")
        # Sorting
        if sort_by == 'price_low':
            print(f"DEBUG: Sorting by price_low")
            filtered_products.sort(key=lambda x: x.get('converted_price', float('inf')) if x.get('converted_price') is not None else float('inf'))
        elif sort_by == 'price_high':
            print(f"DEBUG: Sorting by price_high")
            filtered_products.sort(key=lambda x: x.get('converted_price', float('-inf')) if x.get('converted_price') is not None else float('-inf'), reverse=True)
        elif sort_by == 'name':
            print(f"DEBUG: Sorting by name")
            filtered_products.sort(key=lambda x: x.get('name', '').lower())
        elif sort_by == 'store':
            print(f"DEBUG: Sorting by store")
            filtered_products.sort(key=lambda x: x.get('store', ''))

        print(f"DEBUG: Sorting completed")

        # Split filtered_products by store and limit to results_per_page
        jumia_products = [p for p in filtered_products if p.get('store') == 'Jumia'][:results_per_page]
        melcom_products = [p for p in filtered_products if p.get('store') == 'Melcom'][:results_per_page]
        compughana_products = [p for p in filtered_products if p.get('store') == 'CompuGhana'][:results_per_page]
        amazon_products = [p for p in filtered_products if p.get('store') == 'Amazon'][:results_per_page]

        print(f"DEBUG: Split products - Jumia: {len(jumia_products)}, Melcom: {len(melcom_products)}, CompuGhana: {len(compughana_products)}, Amazon: {len(amazon_products)}")

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
                print(f"DEBUG: Error in get_cheapest: {e}")
                return None
        print(f"DEBUG: Finding cheapest products...")
        cheapest_jumia = get_cheapest(jumia_products)
        cheapest_melcom = get_cheapest(melcom_products)
        cheapest_compughana = get_cheapest(compughana_products)
        cheapest_amazon = get_cheapest(amazon_products)
        print(f"DEBUG: Cheapest products found")

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
        print(f"DEBUG: Finding overall cheapest item from {len(filtered_products)} products")
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
            print(f"DEBUG: Overall cheapest item found: {cheapest_item.get('name', 'Unknown') if cheapest_item else 'None'}")
        except Exception as e:
            print(f"DEBUG: Error finding overall cheapest item: {e}")
            cheapest_item = None

        return render_template(
            'result.html',
            filename=None,
            label=query,
            confidence=100,
            products=jumia_products,
            melcom_products=melcom_products,
            compughana_products=compughana_products,
            amazon_products=amazon_products,
            all_products=filtered_products,
            cheapest_item=cheapest_item,
            cheapest_jumia=cheapest_jumia,
            cheapest_melcom=cheapest_melcom,
            cheapest_compughana=cheapest_compughana,
            cheapest_amazon=cheapest_amazon,
            selected_currency=currency,
            results_per_page=results_per_page,
            min_price=min_price,
            max_price=max_price,
            store_filter=store_filter,
            sort_by=sort_by,
            category=category,
            in_stock=in_stock,
            total_results=len(filtered_products)
        )
    except Exception as e:
        print(f"Error processing search: {str(e)}")
        flash('Error processing your search. Please try again.', 'error')
        return render_template('error.html', error="Error processing your search. Please try again.")

@app.route('/advanced-search', methods=['GET', 'POST'])
def advanced_search():
    """Handle advanced product search page."""
    if request.method == 'POST':
        return search_products()
    return render_template('advanced_search.html')

@app.route('/wishlist')
def wishlist():
    """Display user's wishlist."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM wishlist ORDER BY added_at DESC')
            wishlist_items = cursor.fetchall()
            
            # Calculate unique stores count
            unique_stores = set()
            for item in wishlist_items:
                if item[5]:  # item[5] is the store field
                    unique_stores.add(item[5])
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
                INSERT INTO wishlist (product_name, product_price, product_link, product_image, store)
                VALUES (?, ?, ?, ?, ?)
            ''', (data['name'], data['price'], data['link'], data.get('image', ''), data['store']))
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
            cursor.execute('DELETE FROM wishlist WHERE id = ?', (item_id,))
            conn.commit()
        
        flash('Item removed from wishlist', 'success')
        return redirect(url_for('wishlist'))
    except Exception as e:
        flash('Error removing item from wishlist', 'error')
        return redirect(url_for('wishlist'))

@app.route('/check-price-alerts', methods=['POST'])
def manual_check_price_alerts():
    """Manually trigger price alert checking for testing."""
    try:
        print("DEBUG: Manual price alert check triggered")
        check_all_price_alerts()
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
                WHERE id = ? AND is_active = 1
            ''', (alert_id,))
            alert_data = cursor.fetchone()
        
        if not alert_data:
            return jsonify({'success': False, 'message': 'Alert not found or inactive'})
        
        alert_info = {
            'id': alert_data[0],
            'name': alert_data[1],
            'target_price': alert_data[2],
            'current_price': alert_data[3],
            'link': alert_data[4],
            'store': alert_data[5],
            'email': alert_data[6],
            'created_at': alert_data[7]
        }
        
        # Check price for this specific alert
        current_price = check_price_for_alert(alert_id, alert_info, update_current_price=True)
        
        if current_price is not None:
            return jsonify({
                'success': True, 
                'message': 'Price updated successfully',
                'current_price': current_price
            })
        else:
            return jsonify({'success': False, 'message': 'Could not fetch current price'})
            
    except Exception as e:
        print(f"DEBUG: Error checking single alert {alert_id}: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/price-alerts')
def price_alerts():
    """Display price alerts."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, product_name, target_price, current_price, product_link, store, email, is_active, created_at
                FROM price_alerts 
                ORDER BY created_at DESC
            ''')
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
                INSERT INTO price_alerts (product_name, target_price, current_price, product_link, store, email)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (data['name'], data['target_price'], data['current_price'], 
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
            cursor.execute('DELETE FROM price_alerts WHERE id = ?', (alert_id,))
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
            cursor.execute('UPDATE price_alerts SET is_active = 0 WHERE id = ?', (alert_id,))
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
            cursor.execute('UPDATE price_alerts SET is_active = 1 WHERE id = ?', (alert_id,))
            conn.commit()
        
        return jsonify({'success': True, 'message': 'Price alert activated'})
    except Exception as e:
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
                GROUP BY search_type, DATE(created_at)
                ORDER BY date DESC
                LIMIT 30
            ''')
            search_stats = cursor.fetchall()
            
            # Get popular searches
            cursor.execute('''
                SELECT query, COUNT(*) as count
                FROM search_history 
                GROUP BY query 
                ORDER BY count DESC 
                LIMIT 10
            ''')
            popular_searches = cursor.fetchall()
            
            # Get price history trends
            cursor.execute('''
                SELECT product_name, store, AVG(price) as avg_price,
                       MIN(price) as min_price, MAX(price) as max_price,
                       COUNT(*) as price_count
                FROM price_history 
                GROUP BY product_name, store
                ORDER BY price_count DESC
                LIMIT 20
            ''')
            price_trends = cursor.fetchall()
            
            # Get total statistics
            cursor.execute('SELECT COUNT(*) FROM search_history')
            total_searches = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM wishlist')
            total_wishlist = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM price_alerts WHERE is_active = 1')
            active_alerts = cursor.fetchone()[0]
        
        return render_template('analytics.html', 
                             search_stats=search_stats,
                             popular_searches=popular_searches,
                             price_trends=price_trends,
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
                INSERT INTO feedback (image_name, predicted_label, feedback) 
                VALUES (?, ?, ?)
            ''', (image_name, predicted_label, feedback))
            conn.commit()
        flash('Thank you for your feedback!', 'success')
    else:
        flash('Please provide all feedback information', 'error')

    return redirect(url_for('home'))

@app.route('/admin')
def admin():
    """Admin dashboard."""
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            
            # Get feedback data
            cursor.execute('SELECT image_name, predicted_label, feedback, created_at FROM feedback ORDER BY created_at DESC')
            feedback_data = cursor.fetchall()
            
            # Get system statistics
            cursor.execute('SELECT COUNT(*) FROM search_history')
            total_searches = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM wishlist')
            total_wishlist = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM price_alerts')
            total_alerts = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM price_history')
            total_price_records = cursor.fetchone()[0]
        
        return render_template('admin.html', 
                             feedback_data=feedback_data,
                             total_searches=total_searches,
                             total_wishlist=total_wishlist,
                             total_alerts=total_alerts,
                             total_price_records=total_price_records)
    except Exception as e:
        flash('Error loading admin dashboard', 'error')
        return render_template('admin.html', 
                             feedback_data=[],
                             total_searches=0,
                             total_wishlist=0,
                             total_alerts=0,
                             total_price_records=0)

@app.route('/about')
def about():
    """About page describing the project."""
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True)
