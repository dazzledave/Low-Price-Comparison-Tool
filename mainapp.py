from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from image_recognition import predict_image
from jumia_scraper import scrape_jumia
from melcom_scraper import scrape_melcom
import time

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

def scrape_with_timeout(scraper_func, query, max_results=5):
    """Run a scraper with timeout"""
    try:
        with ThreadPoolExecutor() as executor:
            future = executor.submit(scraper_func, query, max_results)
            return future.result(timeout=SCRAPING_TIMEOUT)
    except (TimeoutError, Exception) as e:
        print(f"Error in {scraper_func.__name__}: {str(e)}")
        return []

def scrape_all_sources(query):
    """Scrape all sources concurrently using ThreadPoolExecutor with timeout."""
    scrapers = {
        'products': (scrape_jumia, []),
        'melcom_products': (scrape_melcom, [])
    }
    
    results = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Start all scraping tasks
        future_to_source = {
            executor.submit(scrape_with_timeout, func, query): source
            for source, (func, _) in scrapers.items()
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
                
                return render_template(
                    'result.html',
                    filename=filename,
                    label=label,
                    confidence=confidence,
                    **scraping_results
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

if __name__ == '__main__':
    app.run(debug=True)
