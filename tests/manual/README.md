# Manual Test Scripts

Thư mục này chứa các test scripts thủ công đã được di chuyển từ thư mục gốc. Các scripts này được sử dụng để kiểm tra thủ công các chức năng cụ thể của hệ thống.

## Danh sách Test Scripts

### Spatial & Clustering Tests
- `test_7_queries_spatial.py` - Test 7 queries với spatial indexing
- `test_spatial_indexing_page17.py` - Test spatial indexing cho page 17
- `test_clustering_page17.py` - Test clustering cho page 17

### P&ID Tests
- `test_pid_e2e.py` - End-to-end test cho P&ID pipeline
- `test_pid_accuracy_5queries.py` - Test độ chính xác với 5 queries
- `test_pid_accuracy_audit.py` - Audit test cho P&ID accuracy

### API & Query Tests
- `test_api_original_queries.py` - Test API với original queries
- `test_query_txi_2077.py` - Test query cho TXI_2077
- `test_query2_only.py` - Test query 2 riêng lẻ

### OCR & Extraction Tests
- `test_page103_ocr.py` - Test OCR cho page 103

### Validation Tests
- `test_page_validator_quick.py` - Quick validation test cho pages

### CAD Tests
- `test_cadlike_gate_ammonia.py` - Test CAD-like gate cho ammonia

## Cách sử dụng

Các scripts này có thể được chạy trực tiếp từ thư mục gốc của dự án:

```bash
# Chạy từ root directory
python tests/manual/test_pid_e2e.py

# Hoặc từ thư mục này
cd tests/manual
python test_pid_e2e.py
```

## Lưu ý

1. **Dependencies**: Đảm bảo đã cài đặt đầy đủ dependencies từ `requirements.txt`
2. **Environment**: Cần có file `.env` với đầy đủ cấu hình
3. **Data**: Một số tests yêu cầu dữ liệu đã được ingest sẵn
4. **Services**: Cần các services (OpenSearch, Weaviate, Redis) đang chạy

## Migration từ root

Các scripts này đã được di chuyển từ thư mục gốc vào đây để:
- Tổ chức cấu trúc dự án rõ ràng hơn
- Dễ dàng tìm kiếm và quản lý test scripts
- Tách biệt test code khỏi source code chính

---

**Ngày di chuyển**: 31/10/2025  
**Lý do**: Tổ chức lại cấu trúc thư mục dự án

