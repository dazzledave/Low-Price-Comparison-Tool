from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import os
import sqlite3
from image_recognition import predict_image  # Import the image recognition function
from jumia_scraper import scrape_jumia
from tonaton_scraper import scrape_tonaton



app = Flask(__name__)

# Configurations
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
DATABASE = 'feedback.db'

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
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Call AI model to recognize the image
            label, confidence = predict_image(file_path)

            return redirect(url_for('uploaded_file', filename=filename, label=label, confidence=confidence))

    return render_template('upload.html')

@app.route('/uploaded/<filename>/<label>/<confidence>')
def uploaded_file(filename, label, confidence):
    # Scrape both Jumia and Tonaton
    jumia_products = scrape_jumia(label)
    tonaton_products = scrape_tonaton(label)

    return render_template(
        'result.html',
        filename=filename,
        label=label,
        confidence=confidence,
        products=jumia_products,
        tonaton_products=tonaton_products
    )

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

    return redirect(url_for('home'))  # Redirect back to homepage after submission

@app.route('/admin')
def admin():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT image_name, predicted_label, feedback FROM feedback')
        feedback_data = cursor.fetchall()
    
    return render_template('admin.html', feedback_data=feedback_data)


if __name__ == '__main__':
    app.run(debug=True)
