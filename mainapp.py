from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from image_recognition import predict_image
from jumia_scraper import scrape_jumia
from melcom_scraper import scrape_melcom
from compughana_scraper import scrape_compughana
import time
import re

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
        'compughana_products': (scrape_compughana, query)
    }
    
    results = {}
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

                # Get image recognition results
                label, confidence = predict_image(file_path)
                
                # Start concurrent scraping with timeout
                scraping_results = scrape_all_sources(label)
                
                # Helper to parse price strings
                def parse_price(price_str):
                    price_num = re.sub(r'[^\d.]', '', str(price_str))
                    try:
                        return float(price_num)
                    except ValueError:
                        return float('inf')

                # Find the overall cheapest item
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
                if all_products:
                    cheapest_item = min(all_products, key=lambda x: parse_price(x['price']))

                # Find the cheapest product in each store
                def get_cheapest(products):
                    return min(products, key=lambda x: parse_price(x['price'])) if products else None
                cheapest_jumia = get_cheapest(scraping_results.get('products', []))
                cheapest_melcom = get_cheapest(scraping_results.get('melcom_products', []))
                cheapest_compughana = get_cheapest(scraping_results.get('compughana_products', []))

                return render_template(
                    'result.html',
                    label=label,
                    confidence=confidence,
                    filename=filename,
                    products=scraping_results.get('products', []),
                    melcom_products=scraping_results.get('melcom_products', []),
                    compughana_products=scraping_results.get('compughana_products', []),
                    cheapest_item=cheapest_item,
                    cheapest_jumia=cheapest_jumia,
                    cheapest_melcom=cheapest_melcom,
                    cheapest_compughana=cheapest_compughana
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
    
    if not query:
        return redirect(url_for('upload_file'))
    
    try:
        # Start concurrent scraping with timeout
        scraping_results = scrape_all_sources(query)
        
        # Helper to parse price strings
        def parse_price(price_str):
            price_num = re.sub(r'[^\d.]', '', str(price_str))
            try:
                return float(price_num)
            except ValueError:
                return float('inf')

        # Find the overall cheapest item
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
        if all_products:
            cheapest_item = min(all_products, key=lambda x: parse_price(x['price']))

        # Find the cheapest product in each store
        def get_cheapest(products):
            return min(products, key=lambda x: parse_price(x['price'])) if products else None
        cheapest_jumia = get_cheapest(scraping_results.get('products', []))
        cheapest_melcom = get_cheapest(scraping_results.get('melcom_products', []))
        cheapest_compughana = get_cheapest(scraping_results.get('compughana_products', []))

        return render_template(
            'result.html',
            filename=None,  # No image for text search
            label=query,    # Use the search query as the label
            confidence=100, # Full confidence for text search
            products=scraping_results.get('products', []),
            melcom_products=scraping_results.get('melcom_products', []),
            compughana_products=scraping_results.get('compughana_products', []),
            cheapest_item=cheapest_item,
            cheapest_jumia=cheapest_jumia,
            cheapest_melcom=cheapest_melcom,
            cheapest_compughana=cheapest_compughana
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
