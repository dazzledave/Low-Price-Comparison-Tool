from flask import Flask, render_template, request, redirect, url_for, jsonify
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

app = Flask(__name__)

# Configurations
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
DATABASE = 'feedback.db'
SCRAPING_TIMEOUT = 30  # seconds

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Ensure database is initialized
def init_db():
    """Initialize the database with a feedback table if not exists."""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_name TEXT,
                predicted_label TEXT,
                feedback TEXT
            )
        ''')
        conn.commit()

init_db()  # Initialize DB on app start

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

def scrape_all_sources(query):
    """Scrape all sources concurrently using ThreadPoolExecutor with timeout."""
    scrapers = {
        'products': (scrape_jumia, query),
        'melcom_products': (scrape_melcom, query),
        'compughana_products': (scrape_compughana, query),
        'amazon_products': (scrape_amazon, query)
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

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)

        if file and allowed_file(file.filename):
            try:
                # Save and process the image
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                # Get selected model from form
                model_name = request.form.get('model', 'inceptionv3')
                currency = request.form.get('currency', 'GHS')

                # Get image recognition results
                label, confidence = predict_image(file_path, model_name)
                
                # Start concurrent scraping with timeout
                scraping_results = scrape_all_sources(label)
                
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
                            p['converted_price'] = converted
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
                    return x.get('converted_price', float('inf')) if x.get('converted_price') is not None else float('inf')
                if all_products:
                    cheapest_item = min(all_products, key=get_converted_price)
                # Find the cheapest product in each store (use converted_price)
                def get_cheapest(products):
                    return min(products, key=get_converted_price) if products else None
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
                return render_template('error.html', error="Error processing your request. Please try again.")

    return render_template('upload.html')

@app.route('/uploaded/<filename>/<label>/<confidence>')
def uploaded_file(filename, label, confidence):
    try:
        # Scrape all sources concurrently with timeout
        scraping_results = scrape_all_sources(label)
        
        return render_template(
            'result.html',
            filename=filename,
            label=label,
            confidence=confidence,
            **scraping_results
        )
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return render_template('error.html', error="Error processing your request. Please try again.")

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

    return redirect(url_for('home'))

@app.route('/admin')
def admin():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT image_name, predicted_label, feedback FROM feedback')
        feedback_data = cursor.fetchall()
    
    return render_template('admin.html', feedback_data=feedback_data)

@app.route('/search', methods=['POST'])
def search_products():
    """Handle text-based product search."""
    query = request.form.get('query', '').strip()
    currency = request.form.get('currency', 'GHS')
    
    if not query:
        return redirect(url_for('upload_file'))
    
    try:
        # Start concurrent scraping with timeout
        scraping_results = scrape_all_sources(query)
        
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
                    p['converted_price'] = converted
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
            return x.get('converted_price', float('inf')) if x.get('converted_price') is not None else float('inf')
        if all_products:
            cheapest_item = min(all_products, key=get_converted_price)
        # Find the cheapest product in each store (use converted_price)
        def get_cheapest(products):
            return min(products, key=get_converted_price) if products else None
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

        return render_template(
            'result.html',
            filename=None,  # No image for text search
            label=query,    # Use the search query as the label
            confidence=100, # Full confidence for text search
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
        print(f"Error processing search: {str(e)}")
        return render_template('error.html', error="Error processing your search. Please try again.")

def find_cheapest_item(products, melcom_products, compughana_products=None):
    """Find the cheapest item across all stores"""
    all_products = []
    
    # Add Jumia products
    for product in products:
        try:
            price_str = product['price'].replace('GH₵', '').replace('GHS', '').replace('₵', '').replace(',', '').strip()
            price = float(price_str)
            all_products.append({
                'name': product['name'],
                'price': price,
                'price_display': product['price'],
                'image': product.get('image', ''),
                'link': product['link'],
                'store': 'Jumia'
            })
        except (ValueError, KeyError):
            continue
    
    # Add Melcom products
    for product in melcom_products:
        try:
            price_str = product['price'].replace('GH₵', '').replace('GHS', '').replace('₵', '').replace(',', '').strip()
            price = float(price_str)
            all_products.append({
                'name': product['name'],
                'price': price,
                'price_display': product['price'],
                'image': product.get('image', ''),
                'link': product['link'],
                'store': 'Melcom'
            })
        except (ValueError, KeyError):
            continue
    
    # Add CompuGhana products
    if compughana_products:
        for product in compughana_products:
            try:
                price_str = product['price'].replace('GH₵', '').replace('GHS', '').replace('₵', '').replace(',', '').strip()
                price = float(price_str)
                all_products.append({
                    'name': product['name'],
                    'price': price,
                    'price_display': product['price'],
                    'image': product.get('image', ''),
                    'link': product['link'],
                    'store': 'CompuGhana'
                })
            except (ValueError, KeyError):
                continue
    
    if not all_products:
        return None
    
    # Find the cheapest item
    cheapest_item = min(all_products, key=lambda x: x['price'])
    return cheapest_item

if __name__ == '__main__':
    app.run(debug=True)
