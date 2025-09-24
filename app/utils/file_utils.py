"""
File handling utilities
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


def ensure_dir(path: Path) -> Path:
    """
    Ensure directory exists, create if not
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(data: Any, file_path: Path, indent: int = 2):
    """
    Save data to JSON file
    """
    file_path = Path(file_path)
    ensure_dir(file_path.parent)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)

    logger.debug(f"Saved JSON to {file_path}")


def load_json(file_path: Path) -> Any:
    """
    Load data from JSON file
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.debug(f"Loaded JSON from {file_path}")
    return data


def list_files(
    directory: Path, pattern: str = "*", recursive: bool = True
) -> List[Path]:
    """
    List files in directory matching pattern
    """
    directory = Path(directory)

    if not directory.exists():
        logger.warning(f"Directory not found: {directory}")
        return []

    if recursive:
        files = list(directory.rglob(pattern))
    else:
        files = list(directory.glob(pattern))

    return sorted(files)


def read_text_file(file_path: Path) -> str:
    """
    Read text file content
    """
    file_path = Path(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    return content


def write_text_file(content: str, file_path: Path):
    """
    Write text to file
    """
    file_path = Path(file_path)
    ensure_dir(file_path.parent)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.debug(f"Wrote text file to {file_path}")


def get_file_size(file_path: Path) -> int:
    """
    Get file size in bytes
    """
    file_path = Path(file_path)
    return file_path.stat().st_size if file_path.exists() else 0


def format_file_size(size_bytes: int) -> str:
    """
    Format file size for display
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


# Alias for compatibility
ensure_directory = ensure_dir

__all__ = [
    "ensure_dir",
    "ensure_directory",
    "save_json",
    "load_json",
    "list_files",
    "read_text_file",
    "write_text_file",
    "get_file_size",
    "format_file_size",
]
