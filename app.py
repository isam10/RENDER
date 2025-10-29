"""
Flask Backend for Background Removal Service
Optimized for Render.com deployment with CPU-based processing
"""

import os
import io
import logging
from datetime import datetime
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from PIL import Image
from rembg import remove, new_session
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# CORS configuration - Allow requests from Vercel frontend
CORS(app, resources={
    r"/api/*": {
        "origins": ["*"],  # Update with your Vercel domain for production
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

# Global session - Initialize once and reuse for all requests
# This significantly improves performance by keeping the model in memory
rembg_session = None

def init_model():
    """Initialize rembg model on startup"""
    global rembg_session
    try:
        logger.info("Initializing rembg model (isnet-general-use)...")
        rembg_session = new_session("isnet-general-use")
        logger.info("Model initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize model: {str(e)}")
        raise

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_image_file(file):
    """Validate uploaded image file"""
    if not file:
        return False, "No file provided"
    
    if file.filename == '':
        return False, "No file selected"
    
    if not allowed_file(file.filename):
        return False, f"File type not allowed. Supported: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        return False, f"File too large. Maximum size: {MAX_FILE_SIZE / (1024*1024)}MB"
    
    return True, None

@app.route('/', methods=['GET'])
def home():
    """API documentation endpoint"""
    return jsonify({
        "service": "Background Removal API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "POST /api/remove-bg": {
                "description": "Remove background from image",
                "accepts": "multipart/form-data",
                "parameters": {
                    "image": "Image file (PNG, JPG, JPEG, WEBP) - Max 10MB"
                },
                "returns": "PNG image with transparent background"
            },
            "GET /health": {
                "description": "Health check endpoint",
                "returns": "Service health status"
            }
        },
        "documentation": "https://github.com/yourusername/FileFlex",
        "timestamp": datetime.utcnow().isoformat()
    }), 200

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    try:
        model_status = "loaded" if rembg_session is not None else "not_loaded"
        return jsonify({
            "status": "healthy",
            "model": model_status,
            "timestamp": datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 503

@app.route('/api/remove-bg', methods=['POST', 'OPTIONS'])
def remove_background():
    """
    Remove background from uploaded image
    Returns PNG with transparent background
    """
    # Handle preflight CORS request
    if request.method == 'OPTIONS':
        return '', 204
    
    start_time = datetime.now()
    logger.info(f"[{start_time.isoformat()}] New background removal request")
    
    try:
        # Check if model is initialized
        if rembg_session is None:
            logger.error("Model not initialized")
            return jsonify({
                "error": "Service not ready",
                "message": "Background removal model is not loaded"
            }), 503
        
        # Validate request
        if 'image' not in request.files:
            return jsonify({
                "error": "Bad request",
                "message": "No image file provided in request"
            }), 400
        
        file = request.files['image']
        
        # Validate file
        is_valid, error_message = validate_image_file(file)
        if not is_valid:
            return jsonify({
                "error": "Invalid file",
                "message": error_message
            }), 400
        
        logger.info(f"Processing image: {secure_filename(file.filename)}")
        
        # Read image data into memory
        input_data = file.read()
        
        # Open image with PIL for validation and potential conversion
        try:
            img = Image.open(io.BytesIO(input_data))
            
            # Convert to RGB if necessary (handles RGBA, grayscale, etc.)
            if img.mode not in ('RGB', 'RGBA'):
                logger.info(f"Converting image from {img.mode} to RGB")
                img = img.convert('RGB')
            
            # Convert back to bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            input_data = img_byte_arr.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to open/process image: {str(e)}")
            return jsonify({
                "error": "Invalid image",
                "message": "Could not process image file. Please ensure it's a valid image."
            }), 400
        
        # Remove background using rembg
        logger.info("Removing background...")
        output_data = remove(
            input_data,
            session=rembg_session,
            post_process_mask=True  # Improves edge quality
        )
        
        # Create output image in memory
        output_image = io.BytesIO(output_data)
        output_image.seek(0)
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Background removed successfully in {processing_time:.2f}s")
        
        # Return PNG with transparent background
        return send_file(
            output_image,
            mimetype='image/png',
            as_attachment=False,
            download_name='removed_bg.png'
        )
    
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "message": "An error occurred while processing your image. Please try again."
        }), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    return jsonify({
        "error": "File too large",
        "message": f"Maximum file size is {MAX_FILE_SIZE / (1024*1024)}MB"
    }), 413

@app.errorhandler(500)
def internal_server_error(error):
    """Handle internal server errors"""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        "error": "Internal server error",
        "message": "An unexpected error occurred"
    }), 500

if __name__ == '__main__':
    # Initialize model before starting server
    init_model()
    
    # Get port from environment variable (Render provides this)
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app
    # In production, this will be handled by gunicorn
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False
    )
