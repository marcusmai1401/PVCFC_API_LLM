"""
PaddleOCR Configuration Module
Provides PaddleOCR PP-OCRv5 initialization with GPU/CPU auto-detection
Replaces Tesseract OCR with PaddleOCR for higher accuracy
"""
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

# Import GPU utilities
try:
    from app.core.gpu_utils import get_gpu_initializer

    GPU_UTILS_AVAILABLE = True
except ImportError:
    GPU_UTILS_AVAILABLE = False
    logger.warning("GPU utilities not available. Will use default GPU detection.")

# Check PaddleOCR availability
OCR_AVAILABLE = False
OCR_ENGINE = None
PADDLE_OCR = None

try:
    import paddle
    from paddleocr import PaddleOCR

    OCR_AVAILABLE = True
    OCR_ENGINE = "PaddleOCR"
    logger.info(f"✓ PaddleOCR available (PaddlePaddle {paddle.__version__})")
except ImportError as e:
    logger.warning(f"PaddleOCR not available: {e}")
    OCR_AVAILABLE = False


# Import centralized config
from app.config import get_config

# Get config instance
_pipeline_config = get_config()

# PP-OCRv5 Model paths from config
PPOCRV5_DET_MODEL = _pipeline_config.DET_MODEL_DIR
PPOCRV5_REC_MODEL = _pipeline_config.REC_MODEL_DIR  # May be None for auto-download
PPOCRV5_CLS_MODEL = _pipeline_config.CLS_MODEL_DIR


def verify_ppocrv5_models() -> bool:
    """
    Verify that PP-OCRv5 models are available.

    Returns:
        True if required models exist, False otherwise
    """
    # Check required models (det and cls)
    required_models = [PPOCRV5_DET_MODEL, PPOCRV5_CLS_MODEL]

    for model_path in required_models:
        if not model_path.exists():
            logger.error(f"PP-OCRv5 model not found: {model_path}")
            return False

        # Check for .pdmodel and .pdiparams files
        pdmodel_file = model_path / "inference.pdmodel"
        pdiparams_file = model_path / "inference.pdiparams"

        if not pdmodel_file.exists() or not pdiparams_file.exists():
            logger.error(f"Model files missing in {model_path}")
            logger.error(f"  Expected: inference.pdmodel and inference.pdiparams")
            return False

    # Check optional rec model
    if PPOCRV5_REC_MODEL is not None and PPOCRV5_REC_MODEL.exists():
        logger.info("✓ All PP-OCRv5 models verified (including local rec model)")
    else:
        logger.info(
            "✓ Required PP-OCRv5 models verified (rec model will auto-download)"
        )

    return True


def get_gpu_config() -> Dict[str, Any]:
    """
    Get GPU configuration for PaddleOCR.

    Returns:
        Dictionary with use_gpu and device settings
    """
    if GPU_UTILS_AVAILABLE:
        try:
            gpu_init = get_gpu_initializer(prefer_gpu=True, verbose=True)
            gpu_info = gpu_init.initialize_gpu(device_id=0)

            if gpu_info.cuda_available:
                logger.info(f"✓ GPU available: {gpu_info.device_name}")
                if gpu_info.cuda_version:
                    logger.info(f"  CUDA: {gpu_info.cuda_version}")
                if gpu_info.cudnn_version:
                    logger.info(f"  cuDNN: {gpu_info.cudnn_version}")
                return {"use_gpu": True, "device": gpu_info.device_name}
            else:
                logger.warning(f"⚠ GPU not available: {gpu_info.initialization_error}")
                logger.warning("→ Fallback to CPU mode")
                return {"use_gpu": False, "device": "cpu"}
        except Exception as e:
            logger.error(f"GPU detection failed: {e}")
            return {"use_gpu": False, "device": "cpu"}
    else:
        # Fallback to basic Paddle GPU detection
        try:
            import paddle

            if paddle.is_compiled_with_cuda():
                logger.info("✓ GPU available (basic detection)")
                return {"use_gpu": True, "device": "gpu:0"}
            else:
                logger.warning("⚠ CUDA not available, using CPU")
                return {"use_gpu": False, "device": "cpu"}
        except Exception as e:
            logger.error(f"Basic GPU detection failed: {e}")
            return {"use_gpu": False, "device": "cpu"}


def initialize_paddleocr(
    use_gpu: Optional[bool] = None,
    use_angle_cls: bool = True,
    use_space_char: bool = True,
    show_log: bool = False,
) -> Optional[Any]:
    """
    Initialize PaddleOCR with PP-OCRv5 models.

    Args:
        use_gpu: Whether to use GPU (auto-detect if None)
        use_angle_cls: Whether to use text angle classification
        use_space_char: Whether to recognize space characters
        show_log: Whether to show PaddleOCR logs

    Returns:
        PaddleOCR instance or None if initialization fails
    """
    global PADDLE_OCR

    if not OCR_AVAILABLE:
        logger.error("PaddleOCR not available")
        return None

    # Verify models exist
    if not verify_ppocrv5_models():
        logger.error("PP-OCRv5 models not available")
        return None

    # Get GPU configuration if not specified
    if use_gpu is None:
        gpu_config = get_gpu_config()
        use_gpu = gpu_config["use_gpu"]

    try:
        # Get OCR config to check rec model status
        ocr_config = _pipeline_config.get_ocr_config()

        # Determine rec model source for logging
        if PPOCRV5_REC_MODEL is not None and PPOCRV5_REC_MODEL.exists():
            rec_model_info = f"Cached EN model (offline) - {PPOCRV5_REC_MODEL.name}"
            rec_note = "Using cached official EN rec model (offline-friendly)"
        else:
            rec_model_info = "Official EN PP-OCRv4 (auto-download)"
            rec_note = "Will auto-download official EN rec model on first use"

        logger.info("=" * 60)
        logger.info("INITIALIZING PP-OCRv5 (PaddleOCR)")
        logger.info("=" * 60)
        logger.info(f"Detection Model: {PPOCRV5_DET_MODEL.name} (local)")
        logger.info(f"Recognition Model: {rec_model_info}")
        logger.info(f"Classifier Model: {PPOCRV5_CLS_MODEL.name} (local)")
        logger.info(f"GPU Enabled: {use_gpu}")
        logger.info(f"Angle Classification: {use_angle_cls}")
        logger.info("=" * 60)
        logger.info(f"Note: {rec_note}")
        logger.info("=" * 60)

        # Update OCR config with runtime parameters
        ocr_config.update(
            {
                "use_angle_cls": use_angle_cls,
                "use_gpu": use_gpu,
                "use_space_char": use_space_char,
                "show_log": show_log,
            }
        )

        ocr = PaddleOCR(**ocr_config)

        PADDLE_OCR = ocr
        logger.info("✅ PaddleOCR initialized successfully!")
        logger.info("=" * 60)

        return ocr

    except Exception as e:
        logger.error(f"Failed to initialize PaddleOCR: {e}")
        logger.exception(e)

        # Try CPU fallback if GPU failed
        if use_gpu:
            logger.warning("Attempting CPU fallback...")
            try:
                ocr_config_cpu = _pipeline_config.get_ocr_config()
                ocr_config_cpu.update(
                    {
                        "use_angle_cls": use_angle_cls,
                        "use_gpu": False,  # Force CPU
                        "use_space_char": use_space_char,
                        "show_log": show_log,
                    }
                )

                ocr = PaddleOCR(**ocr_config_cpu)
                PADDLE_OCR = ocr
                logger.info("✅ PaddleOCR initialized in CPU mode")
                return ocr
            except Exception as e2:
                logger.error(f"CPU fallback also failed: {e2}")
                return None

        return None


# Thread-local storage for PaddleOCR instances
_thread_local = threading.local()


def get_paddleocr_instance() -> Optional[Any]:
    """
    Get a thread-local PaddleOCR instance.
    Each thread gets its own instance to avoid GPU tensor conflicts.

    Returns:
        PaddleOCR instance or None
    """
    # Check if current thread has an instance
    if not hasattr(_thread_local, "paddle_ocr") or _thread_local.paddle_ocr is None:
        logger.debug(
            f"Creating new PaddleOCR instance for thread {threading.current_thread().name}"
        )
        _thread_local.paddle_ocr = initialize_paddleocr()

    return _thread_local.paddle_ocr


def get_ocr_status() -> Dict[str, Any]:
    """
    Get OCR engine status information.

    Returns:
        Dictionary with OCR status details
    """
    status = {
        "ocr_enabled": OCR_AVAILABLE,
        "ocr_engine": OCR_ENGINE,
        "models_available": False,
        "gpu_available": False,
    }

    if OCR_AVAILABLE:
        status["models_available"] = verify_ppocrv5_models()
        gpu_config = get_gpu_config()
        status["gpu_available"] = gpu_config["use_gpu"]
        status["device"] = gpu_config["device"]

        try:
            import paddle

            status["paddle_version"] = paddle.__version__()
            status["cuda_compiled"] = paddle.is_compiled_with_cuda()
        except:
            pass

        try:
            import paddleocr

            status["paddleocr_version"] = paddleocr.__version__
        except:
            pass

    return status


# Auto-initialize on import (optional)
# Uncomment if you want to initialize immediately
# if OCR_AVAILABLE:
#     logger.info("Auto-initializing PaddleOCR...")
#     initialize_paddleocr()
