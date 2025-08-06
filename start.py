#!/usr/bin/env python3
"""
Startup script optimized for Render.com deployment
Memory-optimized for 512MB RAM constraint
"""

import os
import gc
import sys

# Memory optimization
gc.collect()

# Set environment variables for memory optimization
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Reduce TensorFlow logging
os.environ['CUDA_VISIBLE_DEVICES'] = ''  # Disable GPU to save memory
os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'  # Prevent GPU memory allocation
os.environ['TF_MEMORY_ALLOCATION'] = '0.1'  # Limit TensorFlow memory usage

# Disable TensorFlow warnings
import warnings
warnings.filterwarnings('ignore', category=UserWarning)

# Import and run the app
from mainapp import app

if __name__ == '__main__':
    # Get port from environment (for Render deployment)
    port = int(os.environ.get('PORT', 5000))
    
    # Run with memory optimization
    app.run(debug=False, host='0.0.0.0', port=port) 