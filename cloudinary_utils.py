#!/usr/bin/env python3
"""
Cloudinary integration for trichology application
Handles secure file uploads and image management
"""

import os
import logging
import cloudinary
import cloudinary.uploader
import cloudinary.api
from werkzeug.utils import secure_filename
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cloudinary configuration
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', 'degzs8qch')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '742433344378438')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', 'de4PdV_21pSY5gleaA1ZDGcBqbY')

def init_cloudinary():
    """Initialize Cloudinary with credentials"""
    try:
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            secure=True
        )
        logger.info(f"✅ Cloudinary initialized with cloud: {CLOUDINARY_CLOUD_NAME}")
        return True
    except Exception as e:
        logger.error(f"❌ Cloudinary initialization failed: {str(e)}")
        return False

def upload_file_to_cloudinary(file_content, filename, folder, patient_pesel=None):
    """
    Upload file to Cloudinary with organized folder structure
    
    Args:
        file_content: File content (bytes)
        filename: Original filename
        folder: Type of file (trichoscopy, clinical, visits)
        patient_pesel: Patient PESEL for organization
    
    Returns:
        dict: Upload result with URL and public_id
    """
    try:
        # Initialize Cloudinary if not done
        init_cloudinary()
        
        # Create secure filename
        secure_name = secure_filename(filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Build folder path: trichology/{folder}/{patient_pesel}/
        cloudinary_folder = f"trichology/{folder}"
        if patient_pesel:
            cloudinary_folder += f"/{patient_pesel}"
        
        # Create public_id with timestamp
        base_name = os.path.splitext(secure_name)[0]
        public_id = f"{cloudinary_folder}/{timestamp}_{base_name}"
        
        logger.info(f"🔄 Uploading to Cloudinary: {public_id}")
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            file_content,
            public_id=public_id,
            folder=cloudinary_folder,
            resource_type="auto",  # Auto-detect file type
            overwrite=False,
            unique_filename=True,
            use_filename=True
        )
        
        logger.info(f"✅ File uploaded successfully: {result.get('secure_url')}")
        
        return {
            'success': True,
            'url': result.get('secure_url'),
            'public_id': result.get('public_id'),
            'width': result.get('width'),
            'height': result.get('height'),
            'format': result.get('format'),
            'bytes': result.get('bytes')
        }
        
    except Exception as e:
        logger.error(f"❌ Cloudinary upload failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def get_cloudinary_url(public_id, transformation=None):
    """
    Get optimized Cloudinary URL with optional transformations
    
    Args:
        public_id: Cloudinary public ID
        transformation: Optional transformations (resize, crop, etc.)
    
    Returns:
        str: Optimized image URL
    """
    try:
        if transformation:
            url = cloudinary.CloudinaryImage(public_id).build_url(**transformation)
        else:
            # Default optimization
            url = cloudinary.CloudinaryImage(public_id).build_url(
                quality="auto",
                fetch_format="auto"
            )
        return url
    except Exception as e:
        logger.error(f"❌ Error building Cloudinary URL: {str(e)}")
        return None

def delete_cloudinary_file(public_id):
    """
    Delete file from Cloudinary
    
    Args:
        public_id: Cloudinary public ID
    
    Returns:
        dict: Deletion result
    """
    try:
        result = cloudinary.uploader.destroy(public_id)
        logger.info(f"🗑️ File deleted from Cloudinary: {public_id}")
        return {'success': True, 'result': result}
    except Exception as e:
        logger.error(f"❌ Error deleting from Cloudinary: {str(e)}")
        return {'success': False, 'error': str(e)}

def list_cloudinary_files(folder_path):
    """
    List files in Cloudinary folder
    
    Args:
        folder_path: Folder path to list
    
    Returns:
        list: List of files in the folder
    """
    try:
        result = cloudinary.api.resources(
            type="upload",
            prefix=folder_path,
            max_results=500
        )
        return result.get('resources', [])
    except Exception as e:
        logger.error(f"❌ Error listing Cloudinary files: {str(e)}")
        return []

# Helper function for image transformations
def get_thumbnail_url(public_id, width=300, height=300):
    """Get thumbnail URL with specific dimensions"""
    return get_cloudinary_url(
        public_id, 
        {
            'width': width, 
            'height': height, 
            'crop': 'fill',
            'quality': 'auto',
            'fetch_format': 'auto'
        }
    )

def get_optimized_url(public_id, width=None, height=None):
    """Get optimized URL for web display"""
    transformation = {
        'quality': 'auto',
        'fetch_format': 'auto'
    }
    
    if width:
        transformation['width'] = width
    if height:
        transformation['height'] = height
        
    return get_cloudinary_url(public_id, transformation) 