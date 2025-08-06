#!/usr/bin/env python3
"""
Simple Flask app for Render.com deployment
Minimal dependencies to avoid build issues
"""

import os
from flask import Flask, render_template, request, jsonify

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key')

@app.route('/')
def index():
    """Homepage route"""
    return render_template('index.html')

@app.route('/search')
def search():
    """Text-based search route"""
    query = request.args.get('q', '')
    return render_template('search.html', results=[], query=query)

@app.route('/upload')
def upload():
    """Image upload route"""
    return render_template('upload.html')

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port) 