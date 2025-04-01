import tensorflow as tf
from tensorflow.keras.applications.inception_v3 import InceptionV3, preprocess_input, decode_predictions
from tensorflow.keras.preprocessing import image
import numpy as np

# Load pre-trained InceptionV3 model
model = InceptionV3(weights='imagenet')

def predict_image(image_path):
    """Processes the image and returns the top 3 predictions."""
    img = image.load_img(image_path, target_size=(299, 299))
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = preprocess_input(img_array)

    predictions = model.predict(img_array)
    decoded_predictions = decode_predictions(predictions, top=3)[0]

    results = [{"label": label, "score": round(score * 100, 2)} for (_, label, score) in decoded_predictions]
    return results
