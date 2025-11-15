# Archive Directory

Thư mục này chứa các scripts và files tạm thời đã được di chuyển từ thư mục gốc để giữ cho cấu trúc dự án gọn gàng và dễ quản lý.

## Cấu trúc thư mục

### debug_scripts/
Chứa các scripts debug tạm thời được sử dụng trong quá trình phát triển và gỡ lỗi:
- Scripts debug cho các trang cụ thể (page17, page58, page103, page41)
- Scripts debug pipeline (PID, query transform, indexing)
- Files JSON output từ các lần debug

**Mục đích**: Các scripts này được tạo ra để debug các vấn đề cụ thể và có thể tái sử dụng khi cần troubleshoot lại.

### check_scripts/
Chứa các scripts kiểm tra và xác minh dữ liệu:
- Scripts kiểm tra tags (5058, page58, TXI_2077)
- Scripts xác minh extracted data

**Mục đích**: Các scripts validation và verification tạm thời cho việc kiểm tra chất lượng dữ liệu.

### maintenance_scripts/
Chứa các scripts bảo trì hệ thống:
- Scripts extract tags từ các trang cụ thể
- Scripts reindex dữ liệu
- Scripts force execution (OCR, extraction)

**Mục đích**: Các scripts thực hiện các tác vụ bảo trì một lần hoặc theo yêu cầu.

### misc_scripts/
Chứa các scripts linh tinh khác không thuộc các nhóm trên:
- Scripts so sánh queries
- Scripts kiểm tra đơn giản
- Scripts tạo báo cáo
- Scripts indexing spatial

**Mục đích**: Các utility scripts không được phân loại cụ thể.

### test_results/
Chứa các files JSON kết quả test từ các lần chạy trước:
- Kết quả test từ ngày 23-24/10/2025
- Format: `TEST_RESULTS_YYYYMMDD_HHMMSS.json`

**Mục đích**: Lưu trữ historical test results để tham khảo và so sánh.

## Lưu ý quan trọng

1. **Không xóa**: Các files trong archive có thể còn hữu ích cho việc tham khảo hoặc tái sử dụng trong tương lai.

2. **Tái sử dụng**: Khi cần debug hoặc kiểm tra tương tự, có thể copy scripts từ archive ra và sử dụng.

3. **Dọn dẹp định kỳ**: Nên review và xóa các files thực sự không còn cần thiết sau 3-6 tháng.

4. **Không commit git**: Hầu hết các files trong archive không cần thiết phải commit vào git repository.

## Test Scripts

Các test scripts thủ công đã được di chuyển vào `tests/manual/` thay vì archive, vì chúng vẫn có thể được sử dụng thường xuyên hơn.

---

**Ngày tạo**: 31/10/2025
**Lý do**: Dọn dẹp và tổ chức lại cấu trúc thư mục gốc
