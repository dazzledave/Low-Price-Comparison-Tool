#!/usr/bin/env python3
"""
Startup script optimized for deployment
"""

import os
import gc
import sys

# Memory optimization
gc.collect()

# Set environment variables for memory optimization
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Reduce TensorFlow logging
os.environ['CUDA_VISIBLE_DEVICES'] = ''  # Disable GPU to save memory

# Import and run the app
from mainapp import app

if __name__ == '__main__':
    # Get port from environment (for Render deployment)
    port = int(os.environ.get('PORT', 5000))
    
    # Run with memory optimization
    app.run(debug=False, host='0.0.0.0', port=port) 