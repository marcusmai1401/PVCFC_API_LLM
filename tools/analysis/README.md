# 🔍 Analysis Tools

Collection của các scripts phân tích và khảo sát dữ liệu.

## Scripts

- **analyze_chunks_*.py** - Phân tích chunk data và distribution
- **analyze_hybrid_pdf.py** - Phân tích PDF hybrid (text + image)
- **analyze_table_page15.py** - Phân tích bảng biểu trong page cụ thể
- **check_*.py** - Các scripts kiểm tra dữ liệu trong index
- **final_check_1420.py** - Kiểm tra document 1420 cụ thể
- **survey_ocr_language.py** - Khảo sát ngôn ngữ trong OCR results

## Cách sử dụng

Chạy từ project root:
```bash
python tools/analysis/<script_name>.py
```

## Mục đích

Các scripts này được dùng để:
- Phân tích chất lượng dữ liệu sau ingestion
- Kiểm tra distribution của chunks
- Debug các vấn đề về indexing
- Khảo sát và đánh giá OCR output
