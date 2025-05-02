from flask import Flask, request, jsonify
import requests
import base64
from io import BytesIO
from PIL import Image
from datetime import datetime, timezone, timedelta
import os

app = Flask(__name__)

CLIENT_ID = '4ff9020eec9b4251af896cd23f5270f8'
CLIENT_SECRET = '4c3525d2fdbb4878b5729c021157a1d2'

TOKEN_URL = 'https://oauth.fatsecret.com/connect/token'
IMAGE_API_URL = 'https://platform.fatsecret.com/rest/image-recognition/v1'

# Token management
token = None
token_expiry = None

def get_access_token():
    global token, token_expiry
    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    data = {'grant_type': 'client_credentials', 'scope': 'premier image-recognition'}

    response = requests.post(TOKEN_URL, auth=auth, data=data)
    response.raise_for_status()

    token_data = response.json()
    token = token_data['access_token']
    token_expiry = datetime.now(timezone.utc) + timedelta(seconds=token_data['expires_in'] - 60)
    return token

def process_image(file_storage):
    """Convert image to optimized JPEG format"""
    img = Image.open(file_storage.stream)
    img = img.convert('RGB')

    # Resize if needed (recommended for FatSecret API)
    if max(img.size) > 1024:
        img.thumbnail((1024, 1024))

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    buffer.seek(0)

    return base64.b64encode(buffer.read()).decode('utf-8')

def recognize_food(base64_image, access_token):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    # Structured JSON payload according to API specs
    payload = {
        "image_b64": base64_image,
        "output_format": "json",
        "include_food_data": True,
        "region": "US",
        "language": "en",
        "eaten_foods": [],
        "MarketLocale": "US",  # Add MarketLocale
        "LanguageLocale": ""    # Add LanguageLocale if needed
    }

    response = requests.post(IMAGE_API_URL, headers=headers, json=payload)

    # Log the request and response for debugging
    print("Request Payload:", payload)
    print("Response Status Code:", response.status_code)
    print("Response Text:", response.text)

    if response.status_code == 200 and not response.text.strip():
        return {"food_recognition_results": []}

    response.raise_for_status()
    return response.json()

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    try:
        # Validate image size < 4MB
        file = request.files['image']
        if file.content_length > 4 * 1024 * 1024:
            return jsonify({'error': 'Image too large (max 4MB)'}), 400

        base64_image = process_image(file)
        token = get_access_token()
        result = recognize_food(base64_image, token)

        # Check if results are empty and log the response for debugging
        if not result.get('food_recognition_results'):
            print("No food recognition results found:", result)

        return jsonify({
            'status': 'success',
            'results': result.get('food_recognition_results', [])
        })

    except requests.exceptions.HTTPError as e:
        return jsonify({
            'error': f'API Error: {str(e)}',
            'details': e.response.text
        }), e.response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
