import os
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
from image_recognition import predict_image  # Import the image recognition function

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
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

            # Perform image recognition
            predictions = predict_image(file_path)

            return render_template('result.html', filename=filename, predictions=predictions)

    return render_template('upload.html')

@app.route('/uploaded/<filename>')
def uploaded_file(filename):
    return f"File '{filename}' uploaded successfully!"

if __name__ == '__main__':
    app.run(debug=True)
