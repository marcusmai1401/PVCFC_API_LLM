"""
OCR Configuration Module
Handles Tesseract OCR configuration and path detection
"""
import os
import platform
from pathlib import Path
from typing import Optional


def setup_tesseract_path() -> bool:
    """
    Setup Tesseract executable path for different platforms.
    Returns True if Tesseract is available, False otherwise.
    """
    try:
        import pytesseract

        # Common Tesseract installation paths
        if platform.system() == "Windows":
            # Common Windows installation paths
            possible_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                r"C:\Users\Admin\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
            ]

            for path in possible_paths:
                if Path(path).exists():
                    pytesseract.pytesseract.tesseract_cmd = path
                    return True

        # Try to use Tesseract from PATH
        try:
            pytesseract.get_tesseract_version()
            return True
        except pytesseract.TesseractNotFoundError:
            pass

    except ImportError:
        pass

    return False


def get_ocr_status() -> dict:
    """Get OCR availability status"""
    status = {
        "pytesseract_installed": False,
        "pillow_installed": False,
        "tesseract_available": False,
        "tesseract_path": None,
        "tesseract_version": None,
        "ocr_enabled": False,
    }

    try:
        import pytesseract

        status["pytesseract_installed"] = True

        if setup_tesseract_path():
            status["tesseract_available"] = True
            status["tesseract_path"] = pytesseract.pytesseract.tesseract_cmd
            try:
                status["tesseract_version"] = str(pytesseract.get_tesseract_version())
            except:
                pass
    except ImportError:
        pass

    try:
        from PIL import Image

        status["pillow_installed"] = True
    except ImportError:
        pass

    # OCR is enabled only if all components are available
    status["ocr_enabled"] = (
        status["pytesseract_installed"]
        and status["pillow_installed"]
        and status["tesseract_available"]
    )

    return status


# Initialize Tesseract path on module import
OCR_AVAILABLE = setup_tesseract_path()
