# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Image Processing Utilities for file uploads.

Provides image compression, resizing, and format conversion.
Adapted from SUNA project's staged_files_api.py image handling.
"""

import io
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Default settings
MAX_IMAGE_WIDTH = 2048
MAX_IMAGE_HEIGHT = 2048
JPEG_QUALITY = 85
PNG_COMPRESS_LEVEL = 6


def is_image_mime(mime_type: str) -> bool:
    """
    Check if MIME type is an image (excluding SVG).
    
    Args:
        mime_type: MIME type string
        
    Returns:
        True if it's an image type
    """
    if not mime_type:
        return False
    return mime_type.startswith("image/") and mime_type != "image/svg+xml"


def get_image_dimensions(image_bytes: bytes) -> Optional[Tuple[int, int]]:
    """
    Get image dimensions without fully loading the image.
    
    Args:
        image_bytes: Raw image bytes
        
    Returns:
        Tuple of (width, height) or None if not an image
    """
    try:
        from PIL import Image
        
        img = Image.open(io.BytesIO(image_bytes))
        return img.size
    except ImportError:
        logger.warning("Pillow not installed, cannot get image dimensions")
        return None
    except Exception as e:
        logger.warning(f"Failed to get image dimensions: {e}")
        return None


def compress_image(
    image_bytes: bytes,
    mime_type: str,
    max_width: int = MAX_IMAGE_WIDTH,
    max_height: int = MAX_IMAGE_HEIGHT,
    quality: int = JPEG_QUALITY,
) -> Tuple[bytes, str]:
    """
    Compress and resize an image.
    
    This function:
    - Resizes images larger than max dimensions
    - Compresses based on output format
    - Converts RGBA/transparent images to RGB with white background
    
    Args:
        image_bytes: Raw image bytes
        mime_type: Original MIME type
        max_width: Maximum output width
        max_height: Maximum output height
        quality: JPEG quality (1-100)
        
    Returns:
        Tuple of (compressed_bytes, output_mime_type)
    """
    try:
        from PIL import Image
        
        img = Image.open(io.BytesIO(image_bytes))
        original_size = img.size
        
        # Handle transparency (RGBA, LA, P modes)
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            # Paste with alpha mask
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background
        
        # Resize if larger than max dimensions
        width, height = img.size
        if width > max_width or height > max_height:
            ratio = min(max_width / width, max_height / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.debug(f"Resized image from {original_size} to {img.size}")
        
        # Save to output buffer
        output = io.BytesIO()
        
        if mime_type == "image/gif":
            # Preserve GIF format
            img.save(output, format="GIF", optimize=True)
            return output.getvalue(), "image/gif"
        elif mime_type == "image/png":
            # PNG with optimization
            img.save(output, format="PNG", optimize=True, compress_level=PNG_COMPRESS_LEVEL)
            return output.getvalue(), "image/png"
        elif mime_type == "image/webp":
            # WebP with quality
            img.save(output, format="WEBP", quality=quality, optimize=True)
            return output.getvalue(), "image/webp"
        else:
            # Default to JPEG for everything else
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(output, format="JPEG", quality=quality, optimize=True)
            return output.getvalue(), "image/jpeg"
            
    except ImportError:
        logger.warning("Pillow not installed, returning original image")
        return image_bytes, mime_type
    except Exception as e:
        logger.warning(f"Image compression failed: {e}, using original")
        return image_bytes, mime_type


def convert_to_data_url(
    image_bytes: bytes,
    mime_type: str,
) -> str:
    """
    Convert image bytes to a data URL.
    
    Args:
        image_bytes: Raw image bytes
        mime_type: MIME type
        
    Returns:
        Data URL string (e.g., "data:image/png;base64,...")
    """
    import base64
    
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def data_url_to_bytes(data_url: str) -> Tuple[bytes, str]:
    """
    Convert a data URL back to bytes.
    
    Args:
        data_url: Data URL string
        
    Returns:
        Tuple of (bytes, mime_type)
    """
    import base64
    
    if not data_url.startswith("data:"):
        raise ValueError("Invalid data URL format")
    
    # Parse data URL
    header, encoded = data_url.split(",", 1)
    mime_type = header.split(";")[0].replace("data:", "")
    
    image_bytes = base64.b64decode(encoded)
    return image_bytes, mime_type


def get_image_format_extension(mime_type: str) -> str:
    """
    Get file extension for image MIME type.
    
    Args:
        mime_type: Image MIME type
        
    Returns:
        File extension without dot (e.g., "jpg", "png")
    """
    ext_map = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
        "image/bmp": "bmp",
        "image/tiff": "tiff",
    }
    return ext_map.get(mime_type, "jpg")


def create_thumbnail(
    image_bytes: bytes,
    size: Tuple[int, int] = (150, 150),
    mime_type: str = "image/jpeg",
) -> Tuple[bytes, str]:
    """
    Create a thumbnail from an image.
    
    Args:
        image_bytes: Raw image bytes
        size: Thumbnail size (width, height)
        mime_type: Output MIME type
        
    Returns:
        Tuple of (thumbnail_bytes, mime_type)
    """
    try:
        from PIL import Image
        
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background
        
        # Create thumbnail (preserves aspect ratio)
        img.thumbnail(size, Image.Resampling.LANCZOS)
        
        output = io.BytesIO()
        
        if mime_type == "image/png":
            img.save(output, format="PNG", optimize=True)
        else:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(output, format="JPEG", quality=80, optimize=True)
            mime_type = "image/jpeg"
        
        return output.getvalue(), mime_type
        
    except ImportError:
        logger.warning("Pillow not installed, cannot create thumbnail")
        return image_bytes, mime_type
    except Exception as e:
        logger.warning(f"Thumbnail creation failed: {e}")
        return image_bytes, mime_type
