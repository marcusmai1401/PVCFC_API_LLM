import paddle
from paddleocr import PaddleOCR

print(
    f"Paddle: {paddle.__version__} CUDA: {paddle.is_compiled_with_cuda()} Device: {paddle.device.get_device()}"
)

print("\n=== Testing PP-OCRv4 (Stable & Working) ===")

try:
    ocr = PaddleOCR(
        lang="en",  # English model works for Vietnamese (Latin alphabet)
        use_textline_orientation=True,
    )

    print("\n✅ PP-OCRv4 initialized successfully!")
    print("✅ Ready to use for Vietnamese/English OCR")

    # Test với một ảnh (nếu có)
    import os

    test_images = ["test.jpg", "test.png", "sample.jpg"]
    test_img = None
    for img in test_images:
        if os.path.exists(img):
            test_img = img
            break

    if test_img:
        print(f"\n📸 Testing with image: {test_img}")
        result = ocr.ocr(test_img, cls=True)
        if result and result[0]:
            print(f"✅ Found {len(result[0])} text regions")
            for idx, line in enumerate(result[0][:3]):  # Show first 3 results
                text = line[1][0]
                conf = line[1][1]
                print(f"   {idx+1}. '{text}' (confidence: {conf:.2f})")
        else:
            print("No text detected")
    else:
        print(f"\nℹ️ No test image found. But initialization is successful!")
        print("You can now use: result = ocr.ocr('your_image.jpg', cls=True)")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()
