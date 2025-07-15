import tensorflow as tf
from tensorflow.keras.applications.inception_v3 import InceptionV3, preprocess_input, decode_predictions
from tensorflow.keras.preprocessing import image
import numpy as np
import os

# OpenCLIP imports
import open_clip
import torch
from PIL import Image

# Load the pre-trained InceptionV3 model
model = InceptionV3(weights='imagenet')

# OpenCLIP model globals
openclip_model = None
openclip_preprocess = None
openclip_device = "cuda" if torch.cuda.is_available() else "cpu"


def load_openclip_model():
    """Load OpenCLIP model on first use (ViT-B-32, laion2b_s34b_b79k)"""
    global openclip_model, openclip_preprocess
    if openclip_model is None or openclip_preprocess is None:
        print("Loading OpenCLIP model (ViT-B-32, laion2b_s34b_b79k)...")
        openclip_model, _, openclip_preprocess = open_clip.create_model_and_transforms(
            'ViT-B-32',
            pretrained='laion2b_s34b_b79k',
            device=openclip_device
        )
        print("OpenCLIP model loaded successfully!")
    return openclip_model, openclip_preprocess


def predict_image(image_path, model_name='inceptionv3'):
    """Processes the image and returns the most accurate prediction using the selected model."""
    if not os.path.exists(image_path):
        return "Error: File not found", 0  # Handle missing file errors

    if model_name == 'inceptionv3':
        # Load and preprocess the image
        img = image.load_img(image_path, target_size=(299, 299))
        img_array = image.img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        img_array = preprocess_input(img_array)

        # Predict the content of the image
        predictions = model.predict(img_array)
        decoded_predictions = decode_predictions(predictions, top=1)[0]  # Get only top 1 prediction

        if decoded_predictions:
            label = decoded_predictions[0][1].replace('_', ' ')  # Class label with underscores replaced by spaces
            confidence = round(decoded_predictions[0][2] * 100, 2)  # Confidence as a percentage
            return label, confidence
        else:
            return "Unknown", 0
    elif model_name == 'clip':
        try:
            # Load OpenCLIP model
            openclip_model, openclip_preprocess = load_openclip_model()
            
            # Load and preprocess image for OpenCLIP
            image_pil = Image.open(image_path).convert('RGB')
            image_input = openclip_preprocess(image_pil).unsqueeze(0).to(openclip_device)
            
            # Define a more specific list of product-related text prompts for better recognition
            text_prompts = [
                # Electronics
                "keyboard", "mouse", "monitor", "laptop", "desktop computer", "smartphone", "tablet", "television", "camera", "printer", "scanner", "router", "projector", "speaker", "headphones", "earbuds", "microphone", "webcam", "game console", "smartwatch", "flash drive", "external hard drive", "memory card", "charger", "power bank",
                # Appliances
                "refrigerator", "microwave", "blender", "toaster", "kettle", "coffee maker", "washing machine", "air conditioner", "fan", "vacuum cleaner",
                # Accessories
                "bag", "backpack", "watch", "wallet", "belt", "sunglasses", "hat", "cap", "shoes", "sneakers", "sandals", "boots",
                # Office/School
                "notebook", "pen", "pencil", "stapler", "calculator", "desk lamp", "chair", "desk", "file cabinet",
                # Home
                "sofa", "table", "bed", "pillow", "blanket", "curtain", "lamp", "clock", "mirror",
                # Kitchen
                "pot", "pan", "plate", "cup", "glass", "bottle", "spoon", "fork", "knife", "cutting board",
                # Clothing
                "shirt", "t-shirt", "dress", "skirt", "trousers", "jeans", "jacket", "coat", "suit", "tie",
                # Toys
                "toy car", "doll", "action figure", "board game", "puzzle", "lego", "ball", "bicycle",
                # Books/Media
                "book", "magazine", "newspaper", "CD", "DVD", "vinyl record",
                # Food/Drink
                "apple", "banana", "orange", "bread", "milk", "egg", "cheese", "bottle of water", "can of soda"
            ]
            
            # Encode text prompts
            text_inputs = open_clip.tokenize(text_prompts).to(openclip_device)
            
            # Get image and text features
            with torch.no_grad():
                image_features = openclip_model.encode_image(image_input)
                text_features = openclip_model.encode_text(text_inputs)
                
                # Normalize features
                image_features /= image_features.norm(dim=-1, keepdim=True)
                text_features /= text_features.norm(dim=-1, keepdim=True)
                
                # Calculate similarity
                similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
                
                # Get the best match
                best_match_idx = similarity.argmax().item()
                confidence = round(similarity[0][best_match_idx].item() * 100, 2)
                label = text_prompts[best_match_idx]
                
                return label, confidence
                
        except Exception as e:
            print(f"OpenCLIP prediction error: {e}")
            return "OpenCLIP prediction failed", 0
    else:
        return "Unknown model", 0
