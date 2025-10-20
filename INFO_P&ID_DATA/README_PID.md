
# P&ID Dataset README — **Mô tả dữ liệu chi tiết** (Ammonia Unit)

> **Mục đích của tài liệu này:** mô tả **bản chất dữ liệu** có trong bộ P&ID để AI Agent hiểu đúng **thành phần, cấu trúc, quan hệ, quy ước ký hiệu, ràng buộc và hiện tượng quan sát** trong dữ liệu.
> **KHÔNG** nêu phương án/thuật toán/xếp hạng. Chỉ trình bày dữ liệu và các đặc tính đã được kiểm tra bằng chứng (CSV/ảnh).

---

## 1) Phạm vi, nguồn gốc & an toàn

**Nguồn dữ liệu chính:** `01. P&ID Ammonia Unit Rev12 (04000).pdf` — bản P&ID của cụm Ammonia.
**Quy mô:** 117 trang (theo file hiện có).
**Toàn vẹn:** SHA-256 = `169d144a8502e7e38e3e5dbec95adceb92bf6338e96c9d59ed7dd01a23c0c0e7`, kích thước tệp ~ 15.03 MB.

**Bảo lưu & an toàn sử dụng**
- Tài liệu này phục vụ **tham khảo dữ liệu** (data description). **Không** thay thế SOP/MOC/POE hay quyết định vận hành.
- Khi có tranh chấp giữa kết quả text/spatial với hình gốc, cần trích dẫn song song và kiểm tra lại trên bản vẽ gốc hoặc hệ thống tại hiện trường (DCS/PLC).

**Manifest**
| file                                      | pages | size | sha256 | imported_at |
|-------------------------------------------|-------|------|--------|-------------|
| 01. P&ID Ammonia Unit Rev12 (04000).pdf | 117 | 15.03 MB | 169d144a8502e7e38e3e5dbec95adceb92bf6338e96c9d59ed7dd01a23c0c0e7 | 2025-10-18 |

---

## 2) Cấu trúc ký hiệu tag trong dữ liệu

**Dạng tổng quát (được quan sát ổn định trong file này):**
```
[UNIT] PREFIX[-/ ]?SUFFIX[VARIANT]
```
- **`UNIT`** *(tùy chọn)*: **mã số** đơn vị/khu vực (ví dụ: `04`). Trên bản vẽ thường nằm trong **ô tam giác/góc**.
- **`PREFIX`**: 1–6 **chữ cái** in hoa (ví dụ: `IS`, `TAH`, `TAHH`, `FIC`, `ZSL`, …).
  - Các chuỗi như **`TAH`**, **`TAHH`** là **toàn bộ prefix**, không phải biến thể.
- **Phân tách**: có thể là **dấu cách**, `-`, `/`, hoặc không có (tuỳ cách bố cục trên ký hiệu).
- **`SUFFIX`**: 3–6 **chữ số** (ví dụ: `501`, `5145`).
- **`VARIANT`** *(tuỳ chọn)*: 1 **chữ cái** sau `suffix` (ví dụ: `A|B|C`), biểu diễn nhánh song song/dự phòng (tùy site).

**Ví dụ trích từ dữ liệu (đã kiểm chứng bằng spatial + ảnh):**
- `04 IS 501` → `unit="04"`, `prefix="IS"`, `suffix="501"`, `variant=""`
- `04 TAH 5145` → `unit="04"`, `prefix="TAH"`, `suffix="5145"`
- `04 TAHH 5145` → `unit="04"`, `prefix="TAHH"`, `suffix="5145"`
- `04 ZSL 4047A` → `unit="04"`, `prefix="ZSL"`, `suffix="4047"`, `variant="A"`

> **Nguyên tắc mô tả:** phần này **chỉ** ghi nhận cấu trúc dữ liệu. Không hàm ý các quy tắc thiết kế/logic ngoài dữ liệu.

---

## 3) Thực thể & trường dữ liệu (để diễn tả file P&ID)

**3.1 `Tag`** — một ký hiệu thiết bị/điểm đo/nút logic hiển thị trên trang
- Trường cốt lõi:
  - `raw`: chuỗi thô đúng như bản vẽ (giữ lại để truy vết).
  - `unit`: số (vd. `"04"`) — **tuỳ chọn**.
  - `prefix`: 1–6 chữ cái (vd. `"IS"`, `"TAH"`, `"TAHH"`, …).
  - `suffix`: 3–6 chữ số (vd. `"501"`, `"5145"`).
  - `variant`: `""|"A"|"B"|"C"`.
  - `page`: số trang (0-based hoặc 1-based, cần quy ước nhất quán khi sử dụng chung).
  - `bbox` *(tuỳ chọn)*: toạ độ hộp bao quanh trên trang (PDF user space, origin trái–dưới).
  - `confidence` *(tuỳ chọn)*: mức tin cậy khi trích văn bản/chuẩn hoá.
- **Khoá nhận diện hiển thị**: `(unit?, prefix, suffix, variant?, page)`.
- **Khoá nhóm logic**: `(unit?, prefix, suffix)`.

**3.2 `LoopGroup`** — nhóm logic gồm các `Tag` có **cùng** `(unit?, prefix, suffix)`
- Thuộc tính mô tả: `members`, `pages`, `span`, `variants`, `flags` (ví dụ: `"multi_prefix_suffix"`, `"ocr_suspect"`).
- Mục đích: **mô tả dữ liệu** theo nhóm; *không* ngụ ý hành vi/thuật toán.

**3.3 `OffPageConnector (CP)`** — ký hiệu nối **liên trang**
- Thuộc tính: `code` (vd. `CP25-03`), `page` neo, `target_page` *(nếu xác định được)*, `bbox`, `side` (N/E/S/W/NE/NW/SE/SW/CENTER), `notes`.
- Lưu ý: `code` có thể xuất hiện nhiều lần ở nhiều trang; `target_page` có thể khuyết.

**3.4 `Connection`** *(nếu trích được)* — liên kết **trên cùng trang**
- Thuộc tính: `{ from_tag, to_tag, page, line_class?, direction?, bbox?, notes? }`.

**3.5 `Page`** — siêu dữ liệu trang
- Thuộc tính: `{ index, title?, area?, notes? }`. `index` là duy nhất trong file.

---

## 4) Quy ước chuỗi & chuẩn hoá (để thể hiện dữ liệu nhất quán)

- **Chữ hoa** cho `unit/prefix/variant`; **chữ số** cho `suffix`.
- Cho phép dấu `-`, `/`, hoặc **dấu cách** giữa `prefix` và `suffix`.
- `variant` **chỉ** là chữ cái **sau `suffix`** (nếu có).
- **Giữ `raw`** để đối chiếu với bản vẽ khi có nghi vấn (ví dụ từ bị xuống dòng, tách ô).
- **Lỗi OCR thường gặp**: `O↔0`, `I↔1`; có thể thiếu/gộp dấu `-`/`/`. Đây là **nhiễu dữ liệu** cần ghi chú, không phải quy tắc.

---

## 5) Đặc tính dữ liệu đã quan sát (mô tả định lượng)

### 5.1 Mức độ “gần nhau theo trang” của các nhóm
Đo theo **span trang** của mỗi nhóm (max(page)–min(page)).

- **Khoá nhóm = `(prefix:suffix)` (không tính UNIT)**
  - Số nhóm: **3601**
  - Nằm trong **1 trang**: **3183** (~**88.39%**)
  - Nằm trong **≤ 1 trang** (cùng hoặc kề nhau): **3253** (~**90.34%**)
  - Nằm trong **≤ 2 trang**: **3318** (~**92.14%**)

- **Khoá nhóm = `(unit:prefix:suffix)` (có tính UNIT)**
  - Số nhóm: **5628**
  - Nằm trong **1 trang**: **5098** (~**90.58%**)
  - Nằm trong **≤ 1 trang**: **5200** (~**92.4%**)
  - Nằm trong **≤ 2 trang**: **5278** (~**93.78%**)

> **Kết luận mô tả**: Khi **tính cả `UNIT`**, tỉ lệ “cùng/ gần nhau theo trang” **tăng rõ rệt**. Điều này phù hợp với thực tế site: mã `UNIT` giúp định vị phạm vi logic.

Các bảng chi tiết:
- Không tính UNIT: [group_span_no_unit.csv](sandbox:/mnt/data/group_span_no_unit.csv)
- Có tính UNIT: [group_span_with_unit.csv](sandbox:/mnt/data/group_span_with_unit.csv)

### 5.2 Off-page connectors (CP)
- Tổng số lần xuất hiện: **1317**
- Số mã CP khác nhau: **63**
- Bảng chi tiết: [cp_occurrences_pymupdf.csv](sandbox:/mnt/data/cp_occurrences_pymupdf.csv)

### 5.3 Ví dụ đã kiểm chứng bằng ảnh (trang 1-based)
- **`04 IS 501`**: **2** lần; xuất hiện ở **trang: 53, 54**.
- **`04 TAH 5145`**: **0** lần; trang: **—**.
- **`04 TAHH 5145`**: **0** lần; trang: **—**.

Ảnh chú thích (đã vẽ khung quanh chuỗi trên trang):
- [annot_terms_page_54.png](sandbox:/mnt/data/annot_terms_page_54.png) (đánh dấu “5145”/“TAH”/“IS” trên trang 54)
- [hit_5145_p54.png](sandbox:/mnt/data/hit_5145_p54.png) (đánh dấu riêng “5145” trên trang 54)

**Tập thẻ đã gán theo không gian (có bbox):**
- [tags_spatial_unit_prefix_suffix.csv](sandbox:/mnt/data/tags_spatial_unit_prefix_suffix.csv)
- Phân bố UNIT: [spatial_unit_distribution.csv](sandbox:/mnt/data/spatial_unit_distribution.csv)
- Tần suất PREFIX: [spatial_prefix_counts.csv](sandbox:/mnt/data/spatial_prefix_counts.csv)

> Lưu ý: với bố cục P&ID (ô tam giác/tròn/vuông), các phần `UNIT|PREFIX|SUFFIX` có thể **không nằm cùng một dòng chữ** → mô tả dữ liệu **ưu tiên dùng “gán theo không gian” (spatial)** để lưu `unit/prefix/suffix` đúng như bố cục.

---

## 6) Chất lượng dữ liệu & hiện tượng cần chú ý

- **Tách dòng/ô**: `UNIT`, `PREFIX`, `SUFFIX` thường nằm ở **các ô khác nhau** → trong dữ liệu text thô có thể bị **rời**.
- **OCR & font**: nguy cơ nhầm `O↔0`, `I↔1`; ký tự mảnh/dấu gạch có thể bị mất.
- **Multi-prefix per suffix**: cùng một `suffix` có thể đi với **nhiều `prefix`** (mã hệ thống/tái sử dụng). Đây là **đặc tính dữ liệu**, không ngụ ý một loop duy nhất.
- **Biến thể `A/B/C`**: xuất hiện như **nhánh song song/dự phòng** cho cùng `(unit?, prefix, suffix)`.
- **CP liên trang**: tạo mối liên hệ logic giữa các trang nhưng **không** phải kết nối on-page.
- **Toạ độ (`bbox`)**: hệ **PDF user space**, origin **trái–dưới** (tuỳ engine). Khi hiển thị, cần quy đổi phù hợp.

---

## 7) Lược đồ (Schema) rút gọn phục vụ mô tả dữ liệu

> Mục tiêu: đảm bảo **cách lưu trữ dữ liệu nhất quán** cho các file CSV/JSON — *không* mô tả xử lý.

```json
{
  "$id": "tag.schema.json",
  "type": "object",
  "properties": {
    "raw": {"type":"string"},
    "unit":{"type":"string","pattern":"^\\d{1,3}$"},
    "prefix":{"type":"string","pattern":"^[A-Z]{1,6}$"},
    "suffix":{"type":"string","pattern":"^\\d{3,6}$"},
    "variant":{"type":"string","pattern":"^[A-Z]?$"},
    "page":{"type":"integer","minimum":0},
    "bbox":{"type":"array","items":{"type":"number"},"minItems":4,"maxItems":4},
    "confidence":{"type":"number","minimum":0,"maximum":1},
    "attrs":{"type":"object"}
  },
  "required":["raw","prefix","suffix","page"]
}
```

```json
{
  "$id": "offpage.schema.json",
  "type": "object",
  "properties": {
    "code":{"type":"string"},
    "page":{"type":"integer","minimum":0},
    "bbox":{"type":"array","items":{"type":"number"},"minItems":4,"maxItems":4},
    "side":{"type":"string"},
    "target_page":{"type":"integer","minimum":0},
    "notes":{"type":"string"}
  },
  "required":["code","page"]
}
```

```json
{
  "$id": "loopgroup.schema.json",
  "type": "object",
  "properties": {
    "key":{"type":"object","properties":{"unit":{"type":"string"},"prefix":{"type":"string"},"suffix":{"type":"string"}}},
    "members":{"type":"array"},
    "pages":{"type":"array","items":{"type":"integer"}},
    "span":{"type":"integer","minimum":0},
    "variants":{"type":"string"},
    "flags":{"type":"array","items":{"type":"string"}}
  }
}
```

---

## 8) Phiên bản & truy vết

- `dataset_version`: v1.1 (cập nhật mô tả `UNIT` và ví dụ minh hoạ)
- `source_file`: `01. P&ID Ammonia Unit Rev12 (04000).pdf`
- `sha256`: `169d144a8502e7e38e3e5dbec95adceb92bf6338e96c9d59ed7dd01a23c0c0e7`
- `imported_at`: 2025-10-18
- **Artifacts kèm theo**:
  - [tags_spatial_unit_prefix_suffix.csv](sandbox:/mnt/data/tags_spatial_unit_prefix_suffix.csv) — tập thẻ đã gán theo không gian (unit/prefix/suffix/bbox)
  - [group_span_no_unit.csv](sandbox:/mnt/data/group_span_no_unit.csv), [group_span_with_unit.csv](sandbox:/mnt/data/group_span_with_unit.csv) — span nhóm (không/có UNIT)
  - [cp_occurrences_pymupdf.csv](sandbox:/mnt/data/cp_occurrences_pymupdf.csv) — xuất hiện CP
  - [annot_terms_page_54.png](sandbox:/mnt/data/annot_terms_page_54.png), [hit_5145_p54.png](sandbox:/mnt/data/hit_5145_p54.png) — ảnh chú thích

---

*README này nhằm giúp AI Agent hiểu **bản chất dữ liệu** có trong P&ID: cấu trúc tag `[UNIT] PREFIX SUFFIX [VARIANT]`, ý nghĩa `UNIT/PREFIX/SUFFIX/VARIANT`, các thực thể mô tả (`Tag/LoopGroup/CP`), và đặc tính định lượng (span trang, CP…). Không chứa phương án hay thuật toán xử lý.*
