"""
Download PP-OCRv5 models (multilingual) và verify
"""
import os

os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import sys
import tarfile
import urllib.request
from pathlib import Path

# Model URLs for PP-OCRv5 multilingual
PPOCRV5_MODELS = {
    "det": {
        "url": "https://paddleocr.bj.bcebos.com/PP-OCRv5/ch/ch_PP-OCRv5_det_infer.tar",
        "filename": "ch_PP-OCRv5_det_infer.tar",
    },
    "rec": {
        "url": "https://paddleocr.bj.bcebos.com/PP-OCRv5/chinese/ch_PP-OCRv5_rec_infer.tar",
        "filename": "ch_PP-OCRv5_rec_infer.tar",
    },
    "cls": {
        "url": "https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar",
        "filename": "ch_ppocr_mobile_v2.0_cls_infer.tar",
    },
}

# Alternative multilingual rec model (if needed for Vietnamese)
MULTILINGUAL_REC = {
    "url": "https://paddleocr.bj.bcebos.com/PP-OCRv5/multilingual/en_PP-OCRv5_rec_infer.tar",
    "filename": "en_PP-OCRv5_rec_infer.tar",
}


def download_with_progress(url, dest_path):
    """Download file with progress bar"""
    print(f"\n📥 Downloading from: {url}")
    print(f"   Saving to: {dest_path}")

    def progress_hook(count, block_size, total_size):
        percent = int(count * block_size * 100 / total_size)
        sys.stdout.write(f"\r   Progress: {percent}%")
        sys.stdout.flush()

    urllib.request.urlretrieve(url, dest_path, progress_hook)
    print("\n   ✅ Download complete!")


def extract_tar(tar_path, extract_to):
    """Extract tar file"""
    print(f"📦 Extracting {tar_path.name}...")
    with tarfile.open(tar_path, "r") as tar:
        tar.extractall(extract_to)
    print(f"   ✅ Extracted to: {extract_to}")


def main():
    print("=" * 80)
    print("DOWNLOADING PP-OCRv5 MODELS (MULTILINGUAL)")
    print("=" * 80)

    # Setup paths
    base_dir = Path("artifacts/ocr/paddle/ppocrv5")
    base_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📁 Base directory: {base_dir.absolute()}")

    # Download and extract detection model
    det_tar = base_dir / PPOCRV5_MODELS["det"]["filename"]
    det_dir = base_dir / "det"

    if not det_tar.exists():
        download_with_progress(PPOCRV5_MODELS["det"]["url"], det_tar)
        extract_tar(det_tar, det_dir)
    else:
        print(f"\n✅ Detection model already downloaded: {det_tar}")

    # Download and extract recognition model (multilingual)
    print("\nℹ️  Using multilingual recognition model for Vietnamese/English support")
    rec_tar = base_dir / MULTILINGUAL_REC["filename"]
    rec_dir = base_dir / "rec"

    if not rec_tar.exists():
        download_with_progress(MULTILINGUAL_REC["url"], rec_tar)
        extract_tar(rec_tar, rec_dir)
    else:
        print(f"\n✅ Recognition model already downloaded: {rec_tar}")

    # Download and extract classifier (v2.0 still used)
    cls_tar = base_dir / PPOCRV5_MODELS["cls"]["filename"]
    cls_dir = base_dir / "cls"

    if not cls_tar.exists():
        download_with_progress(PPOCRV5_MODELS["cls"]["url"], cls_tar)
        extract_tar(cls_tar, cls_dir)
    else:
        print(f"\n✅ Classifier model already downloaded: {cls_tar}")

    print("\n" + "=" * 80)
    print("MODEL PATHS FOR PADDLEOCR INITIALIZATION:")
    print("=" * 80)

    # Find extracted model directories
    det_model_dirs = list((det_dir).glob("*PP-OCRv5*"))
    rec_model_dirs = list((rec_dir).glob("*PP-OCRv5*"))
    cls_model_dirs = list((cls_dir).glob("*cls*"))

    det_model_path = det_model_dirs[0] if det_model_dirs else "NOT FOUND"
    rec_model_path = rec_model_dirs[0] if rec_model_dirs else "NOT FOUND"
    cls_model_path = cls_model_dirs[0] if cls_model_dirs else "NOT FOUND"

    print(f'\ndet_model_dir = r"{det_model_path}"')
    print(f'rec_model_dir = r"{rec_model_path}"')
    print(f'cls_model_dir = r"{cls_model_path}"')

    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("1. Copy the paths above")
    print("2. Use them in PaddleOCR initialization:")
    print(
        """
ocr = PaddleOCR(
    det_model_dir=r"<det_path>",
    rec_model_dir=r"<rec_path>",
    cls_model_dir=r"<cls_path>",
    use_angle_cls=True,
    lang='vi',
    use_gpu=True,
    show_log=False
)
"""
    )

    # Verify v5
    has_v5 = "v5" in str(det_model_path).lower() and "v5" in str(rec_model_path).lower()

    if has_v5:
        print("\n🎉 SUCCESS: PP-OCRv5 models downloaded and ready!")
    else:
        print("\n⚠️  WARNING: Model verification needed. Check paths above.")

    print("=" * 80)


if __name__ == "__main__":
    main()
