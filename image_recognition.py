import tensorflow as tf
from tensorflow.keras.applications.inception_v3 import InceptionV3, preprocess_input, decode_predictions
from tensorflow.keras.preprocessing import image
import numpy as np
import os

# Load the pre-trained InceptionV3 model
model = InceptionV3(weights='imagenet')

def predict_image(image_path):
    """Processes the image and returns the most accurate prediction."""
    if not os.path.exists(image_path):
        return "Error: File not found", 0  # Handle missing file errors

    # Load and preprocess the image
    img = image.load_img(image_path, target_size=(299, 299))
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = preprocess_input(img_array)

    # Predict the content of the image
    predictions = model.predict(img_array)
    decoded_predictions = decode_predictions(predictions, top=1)[0]  # Get only top 1 prediction

    if decoded_predictions:
        label = decoded_predictions[0][1]  # Class label
        confidence = round(decoded_predictions[0][2] * 100, 2)  # Confidence as a percentage
        return label, confidence
    else:
        return "Unknown", 0
