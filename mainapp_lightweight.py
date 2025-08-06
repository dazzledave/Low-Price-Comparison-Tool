#!/usr/bin/env python3
"""
Lightweight version of mainapp for Render.com deployment
AI models are loaded only when needed to save memory
"""

import os
import gc
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import logging

# Memory optimization
gc.collect()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///pic2price.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

# Lazy loading for AI models
ai_model = None
clip_model = None

def load_ai_models():
    """Load AI models only when needed"""
    global ai_model, clip_model
    if ai_model is None:
        try:
            logger.info("Loading AI models...")
            # Import AI models only when needed
            from image_recognition import load_clip_model
            clip_model = load_clip_model()
            ai_model = True  # Mark as loaded
            logger.info("AI models loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load AI models: {e}")
            ai_model = False

@app.route('/')
def index():
    """Homepage route"""
    return render_template('index.html')

@app.route('/search')
def search():
    """Text-based search route"""
    query = request.args.get('q', '')
    if not query:
        return render_template('search.html', results=[])
    
    # Simple search without AI for now
    return render_template('search.html', results=[], query=query)

@app.route('/upload', methods=['GET', 'POST'])
def upload_image():
    """Image upload route with lazy AI loading"""
    if request.method == 'POST':
        # Load AI models only when image upload is requested
        load_ai_models()
        
        if ai_model:
            # Process image with AI
            return jsonify({'status': 'success', 'message': 'AI processing available'})
        else:
            return jsonify({'status': 'error', 'message': 'AI processing temporarily unavailable'})
    
    return render_template('upload.html')

@app.route('/api/health')
def health_check():
    """Health check endpoint for Render"""
    return jsonify({'status': 'healthy', 'memory': 'optimized'})

@app.route('/api/search', methods=['POST'])
def api_search():
    """API search endpoint"""
    data = request.get_json()
    query = data.get('query', '')
    
    # Simple search response
    return jsonify({
        'status': 'success',
        'results': [],
        'query': query,
        'message': 'Search functionality available'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port) 