"""
GPU/cuDNN Initialization Utilities

Provides automatic detection and configuration of NVIDIA DLL paths for:
- CUDA Runtime (cu11)
- cuDNN (v8.x)
- cuBLAS

This module ensures proper DLL loading for PaddlePaddle GPU inference
with automatic fallback to CPU if GPU initialization fails.
"""

import importlib.util
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """GPU and CUDA configuration information"""

    cuda_available: bool
    device_name: str
    cuda_version: Optional[str] = None
    cudnn_version: Optional[str] = None
    dll_paths_added: List[str] = None
    initialization_error: Optional[str] = None

    def __post_init__(self):
        if self.dll_paths_added is None:
            self.dll_paths_added = []


class GPUInitializer:
    """
    Handles GPU initialization with automatic DLL path configuration
    and fallback to CPU on failure.
    """

    def __init__(self, prefer_gpu: bool = True, verbose: bool = True):
        """
        Initialize GPU configurator.

        Args:
            prefer_gpu: Whether to prefer GPU over CPU
            verbose: Whether to log initialization details
        """
        self.prefer_gpu = prefer_gpu
        self.verbose = verbose
        self._gpu_info: Optional[GPUInfo] = None
        self._dll_paths_configured = False

    def configure_nvidia_dll_paths(self) -> List[str]:
        """
        Auto-detect and prepend NVIDIA DLL paths to system PATH and DLL directories.

        This ensures PaddlePaddle can find the correct cuDNN/CUDA runtime libraries
        even when multiple versions are installed.

        Returns:
            List of DLL paths that were successfully added
        """
        if self._dll_paths_configured:
            if self.verbose:
                logger.info("NVIDIA DLL paths already configured")
            return self._gpu_info.dll_paths_added if self._gpu_info else []

        added_paths = []

        # NVIDIA packages to search (in priority order)
        nvidia_packages = [
            ("nvidia.cuda_runtime", "bin"),  # CUDA runtime (cu11)
            ("nvidia.cudnn", "bin"),  # cuDNN v8.x
            ("nvidia.cublas", "bin"),  # cuBLAS
        ]

        try:
            for pkg_name, subdir in nvidia_packages:
                spec = importlib.util.find_spec(pkg_name)
                if spec and spec.submodule_search_locations:
                    pkg_dir = spec.submodule_search_locations[0]
                    bin_dir = os.path.join(pkg_dir, subdir)

                    if os.path.isdir(bin_dir):
                        # Prepend to PATH for dynamic loader
                        current_path = os.environ.get("PATH", "")
                        os.environ["PATH"] = bin_dir + os.pathsep + current_path

                        # Add to DLL search directories (Windows)
                        if hasattr(os, "add_dll_directory"):
                            os.add_dll_directory(bin_dir)

                        added_paths.append(bin_dir)

                        if self.verbose:
                            logger.info(f"✓ Added NVIDIA DLL path: {bin_dir}")

            if not added_paths:
                msg = "No NVIDIA DLL paths found (packages not installed via pip)"
                if self.verbose:
                    logger.warning(f"⚠ {msg}")

            self._dll_paths_configured = True

        except Exception as e:
            error_msg = f"Failed to configure NVIDIA DLL paths: {e}"
            logger.error(f"✗ {error_msg}")
            if self.verbose:
                logger.exception(e)

        return added_paths

    def get_cuda_version_info(self) -> Dict[str, Optional[str]]:
        """
        Get CUDA and cuDNN version information.

        Returns:
            Dictionary with 'cuda_version', 'cudnn_version', 'cudnn_major',
            'cudnn_minor', 'cudnn_patch'
        """
        version_info = {
            "cuda_version": None,
            "cudnn_version": None,
            "cudnn_major": None,
            "cudnn_minor": None,
            "cudnn_patch": None,
        }

        try:
            import paddle

            # CUDA version from Paddle
            if paddle.is_compiled_with_cuda():
                try:
                    cuda_version = paddle.version.cuda()
                    version_info["cuda_version"] = cuda_version
                except:
                    pass

            # cuDNN version from Paddle
            try:
                cudnn_version = paddle.get_cudnn_version()
                version_info["cudnn_version"] = str(cudnn_version)

                # Parse major.minor.patch
                if cudnn_version:
                    # cuDNN version is typically an integer like 8900 (for 8.9.0)
                    major = cudnn_version // 1000
                    minor = (cudnn_version % 1000) // 100
                    patch = cudnn_version % 100

                    version_info["cudnn_major"] = str(major)
                    version_info["cudnn_minor"] = str(minor)
                    version_info["cudnn_patch"] = str(patch)
            except:
                pass

        except Exception as e:
            if self.verbose:
                logger.warning(f"Could not retrieve CUDA/cuDNN version: {e}")

        return version_info

    def initialize_gpu(self, device_id: int = 0) -> GPUInfo:
        """
        Initialize GPU with proper configuration and fallback.

        Args:
            device_id: GPU device ID (default: 0)

        Returns:
            GPUInfo object with initialization status
        """
        if self._gpu_info is not None:
            return self._gpu_info

        # Step 1: Configure DLL paths
        dll_paths = self.configure_nvidia_dll_paths()

        # Step 2: Try to initialize Paddle GPU
        cuda_available = False
        device_name = "cpu"
        cuda_version = None
        cudnn_version = None
        initialization_error = None

        if not self.prefer_gpu:
            if self.verbose:
                logger.info("GPU disabled by configuration (prefer_gpu=False)")
            device_name = "cpu"
        else:
            try:
                import paddle

                if self.verbose:
                    logger.info(f"PaddlePaddle version: {paddle.__version__}")
                    logger.info(f"Compiled with CUDA: {paddle.is_compiled_with_cuda()}")

                if not paddle.is_compiled_with_cuda():
                    initialization_error = "PaddlePaddle not compiled with CUDA"
                    if self.verbose:
                        logger.warning(f"⚠ {initialization_error}")
                else:
                    # Try to set GPU device
                    try:
                        paddle.set_device(f"gpu:{device_id}")

                        # Test GPU with a simple operation
                        test_tensor = paddle.randn([2, 3])
                        device_place = str(test_tensor.place)

                        if "gpu" in device_place.lower():
                            cuda_available = True
                            device_name = f"gpu:{device_id}"

                            # Get version info
                            version_info = self.get_cuda_version_info()
                            cuda_version = version_info["cuda_version"]
                            cudnn_version = version_info["cudnn_version"]

                            if self.verbose:
                                logger.info(
                                    f"✓ GPU initialized successfully: {device_name}"
                                )
                                logger.info(f"  Device place: {device_place}")
                                if cuda_version:
                                    logger.info(f"  CUDA version: {cuda_version}")
                                if cudnn_version:
                                    cudnn_major = version_info.get("cudnn_major", "?")
                                    cudnn_minor = version_info.get("cudnn_minor", "?")
                                    cudnn_patch = version_info.get("cudnn_patch", "?")
                                    logger.info(
                                        f"  cuDNN version: {cudnn_major}.{cudnn_minor}.{cudnn_patch} (raw: {cudnn_version})"
                                    )
                        else:
                            initialization_error = (
                                f"Tensor not on GPU (place: {device_place})"
                            )
                            if self.verbose:
                                logger.warning(f"⚠ {initialization_error}")

                    except Exception as e:
                        initialization_error = (
                            f"GPU device initialization failed: {str(e)}"
                        )
                        if self.verbose:
                            logger.error(f"✗ {initialization_error}")
                            logger.exception(e)

            except ImportError as e:
                initialization_error = f"Could not import paddle: {str(e)}"
                if self.verbose:
                    logger.error(f"✗ {initialization_error}")

        # Create GPU info
        self._gpu_info = GPUInfo(
            cuda_available=cuda_available,
            device_name=device_name,
            cuda_version=cuda_version,
            cudnn_version=cudnn_version,
            dll_paths_added=dll_paths,
            initialization_error=initialization_error,
        )

        return self._gpu_info

    def get_ocr_config(self) -> Dict[str, any]:
        """
        Get recommended OCR configuration based on GPU availability.

        Returns:
            Dictionary with 'use_gpu' and 'device' keys
        """
        if self._gpu_info is None:
            self.initialize_gpu()

        use_gpu = self._gpu_info.cuda_available

        return {
            "use_gpu": use_gpu,
            "device": self._gpu_info.device_name,
            "fallback_reason": self._gpu_info.initialization_error
            if not use_gpu
            else None,
        }

    def log_summary(self):
        """Log a summary of GPU initialization status"""
        if self._gpu_info is None:
            logger.warning("GPU not yet initialized")
            return

        logger.info("=" * 60)
        logger.info("GPU INITIALIZATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"CUDA Available: {self._gpu_info.cuda_available}")
        logger.info(f"Device: {self._gpu_info.device_name}")

        if self._gpu_info.cuda_version:
            logger.info(f"CUDA Version: {self._gpu_info.cuda_version}")

        if self._gpu_info.cudnn_version:
            logger.info(f"cuDNN Version: {self._gpu_info.cudnn_version}")

        if self._gpu_info.dll_paths_added:
            logger.info(f"DLL Paths Added: {len(self._gpu_info.dll_paths_added)}")
            for path in self._gpu_info.dll_paths_added:
                logger.info(f"  - {path}")

        if self._gpu_info.initialization_error:
            logger.warning(
                f"Initialization Error: {self._gpu_info.initialization_error}"
            )
            logger.warning("→ Fallback to CPU mode")

        logger.info("=" * 60)


# Global initializer instance
_global_initializer: Optional[GPUInitializer] = None


def get_gpu_initializer(
    prefer_gpu: bool = True, verbose: bool = True
) -> GPUInitializer:
    """
    Get or create the global GPU initializer instance.

    Args:
        prefer_gpu: Whether to prefer GPU over CPU
        verbose: Whether to log initialization details

    Returns:
        GPUInitializer instance
    """
    global _global_initializer

    if _global_initializer is None:
        _global_initializer = GPUInitializer(prefer_gpu=prefer_gpu, verbose=verbose)

    return _global_initializer


def initialize_gpu_environment(
    prefer_gpu: bool = True, device_id: int = 0, verbose: bool = True
) -> GPUInfo:
    """
    Convenience function to initialize GPU environment.

    Args:
        prefer_gpu: Whether to prefer GPU over CPU
        device_id: GPU device ID
        verbose: Whether to log initialization details

    Returns:
        GPUInfo object with initialization status
    """
    initializer = get_gpu_initializer(prefer_gpu=prefer_gpu, verbose=verbose)
    gpu_info = initializer.initialize_gpu(device_id=device_id)

    if verbose:
        initializer.log_summary()

    return gpu_info
