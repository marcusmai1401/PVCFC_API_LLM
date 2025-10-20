# AGENT.md — **Quy định sử dụng dữ liệu** (P&ID Ammonia Unit)

> **Mục đích:** quy định **cách AI Agent sử dụng dữ liệu** đã mô tả trong [README.md](sandbox:/mnt/data/README.md) và [MODEL.md](sandbox:/mnt/data/MODEL.md) để trả lời **đúng bản chất dữ liệu**: chuẩn hoá đầu vào, phạm vi trích dẫn, cách trình bày, xử lý mơ hồ, phân biệt on-page/cross-page.
> **Không** nêu phương án/thuật toán/xếp hạng. Không đưa khuyến nghị vận hành.

**Phiên bản:** v1.2 • Cập nhật: 2025-10-18

---

## 0) Phạm vi & Nguồn dữ liệu

- Tài liệu tham chiếu: [README.md](sandbox:/mnt/data/README.md), [MODEL.md](sandbox:/mnt/data/MODEL.md).
- Artefacts dữ liệu kèm chứng cứ (để tra cứu & trích dẫn):
  - Tập Tag đã gán **theo không gian** (unit/prefix/suffix + bbox): [tags_spatial_unit_prefix_suffix.csv](sandbox:/mnt/data/tags_spatial_unit_prefix_suffix.csv)
  - Span nhóm **không/có** UNIT: [group_span_no_unit.csv](sandbox:/mnt/data/group_span_no_unit.csv), [group_span_with_unit.csv](sandbox:/mnt/data/group_span_with_unit.csv)
  - Xuất hiện **CP**: [cp_occurrences_pymupdf.csv](sandbox:/mnt/data/cp_occurrences_pymupdf.csv)
  - Phân bố **UNIT**: [spatial_unit_distribution.csv](sandbox:/mnt/data/spatial_unit_distribution.csv), tần suất **PREFIX**: [spatial_prefix_counts.csv](sandbox:/mnt/data/spatial_prefix_counts.csv)
  - Ảnh chứng minh: [annot_terms_page_54.png](sandbox:/mnt/data/annot_terms_page_54.png), [hit_5145_p54.png](sandbox:/mnt/data/hit_5145_p54.png)

> Agent **chỉ** được sử dụng các nguồn trên và thông tin có trong dataset; nếu thiếu dữ liệu, phải nói rõ “khuyết trường dữ liệu”.

---

## 1) Chuẩn hoá đầu vào (Input Normalization)

**Mục tiêu:** đưa chuỗi người dùng về dạng dữ liệu thống nhất theo:
`[UNIT] PREFIX[-/ ]?SUFFIX[VARIANT]`

- `UNIT` *(tuỳ chọn)*: chuỗi **số** 1–3 ký tự (vd. `04`).
- `PREFIX`: **chữ** 1–6 ký tự, **in hoa** (vd. `IS`, `TAH`, `TAHH`, `FIC`, `ZSL` …).
  - `TAH`, `TAHH` là **một prefix đầy đủ**, **không** phải `variant`.
- Dấu giữa `PREFIX`–`SUFFIX` có thể là **dấu cách**/`-`/`/` hoặc không có; coi là tương đương.
- `SUFFIX`: **số** 3–6 ký tự; lưu dạng chuỗi để giữ `0` đầu nếu có.
- `VARIANT` *(tuỳ chọn)*: **1 chữ** sau `SUFFIX` (vd. `A/B/C`).

**Quy ước hiển thị trang:**
- **Nội bộ**: có thể dùng **0-based**.
- **Trả lời cho người dùng**: **luôn 1-based** (cộng +1 nếu nội bộ là 0-based). Nêu rõ khi cần.

**Giữ `raw`** (nguyên văn) khi trích dẫn. Không phỏng đoán `UNIT/VARIANT` nếu không thấy trong dữ liệu.

---

## 2) Chính sách bằng chứng (Evidence Policy)

Mọi câu trả lời **phải có bằng chứng** tối thiểu:
- **`page` (1-based)** nơi bằng chứng xuất hiện.
- **`raw`** của tag/bản ghi (như trong bản vẽ hoặc như OCR trích ra).

Khi có:
- **`bbox`** (tọa độ PDF user space) → đính kèm để người dùng dễ kiểm tra.
- **CP (OffPageConnector)** → nêu `code` (vd. `CP25-03`) và `page` neo; nếu có `target_page`, nêu rõ; nếu không, chỉ ra là **khuyết**.

**Phân biệt on-page vs cross-page:**
- **On-page**: quan hệ giữa các `Tag` trên **cùng** trang (có thể thể hiện qua `Connection`).
- **Cross-page**: liên kết qua **CP** (không được coi là on-page).

**Không diễn giải ngoài dữ liệu**: không thêm SOP/giải pháp/ý nghĩa vận hành nếu không có trong dữ liệu.

---

## 3) Xử lý mơ hồ & tình huống đặc thù (Ambiguity Handling)

**Multi-prefix per suffix**
- Nếu cùng `suffix` xuất hiện với ≥ 2 `prefix`, Agent **không kết luận** một loop duy nhất.
- Trả về **tất cả** {{unit?, prefix, suffix}} có thật kèm `page`/`raw`. Nếu người dùng chỉ nhập `suffix`, **cảnh báo mơ hồ**.

**Thiếu `UNIT`**
- Nếu người dùng không cung cấp `UNIT` nhưng trong dữ liệu có nhiều `UNIT` cho cùng `prefix:suffix`, liệt kê theo từng `UNIT`.
- Không tự gán `UNIT` mặc định.

**Biến thể `A/B/C`**
- Nếu tồn tại nhiều `variant`, trình bày như **nhánh** trong cùng `(unit?, prefix, suffix)`; liệt kê **đầy đủ** `variant` + `page`.

**Lặp xuất hiện**
- Nếu cùng `(unit?, prefix, suffix, variant?)` xuất hiện **nhiều lần** trên nhiều trang, liệt kê tất cả `page`.
- Không giả định trang “chính” nếu dữ liệu không ghi rõ.

**OCR nghi vấn / ký tự nhạy**
- Khi có khả năng nhầm `O↔0`, `I↔1`, thiếu/gộp dấu `-`/`/`, nêu **ghi chú** “nghi vấn OCR”.
- Ưu tiên hiển thị `raw` + `bbox` để người dùng tự đối chiếu.

**CP thiếu `target_page`**
- Nếu `target_page` không xác định, ghi rõ **khuyết trường dữ liệu**.

---

## 4) Phạm vi trả lời & định dạng trình bày

### 4.1 Quy tắc chung
- **Ngắn gọn, có cấu trúc** (bullet/bảng).
- **Luôn** nêu: `raw`, {{unit, prefix, suffix, variant}}, `page` (1-based).
- Khi có: `bbox`, `CP code`, `target_page`.
- **Sắp xếp** các mục theo `page` tăng dần (đây chỉ là **thứ tự hiển thị**, **không** là xếp hạng/ưu tiên).

### 4.2 Mẫu câu hỏi & cấu trúc trả lời

**(A) Truy vấn theo tag đầy đủ** (vd. “Tìm `04 IS 501`”)
- Trả về **bản ghi chính xác** có trong dữ liệu (có thể nhiều `page`).
- Kèm “các nhánh variant” (nếu có) thuộc cùng `(unit, prefix, suffix)`.

**(B) Truy vấn theo `suffix` hoặc thiếu `UNIT`/`variant`**
- Trình bày **tất cả** ứng viên có thật theo {{unit?, prefix, suffix}}.
- Đính kèm cảnh báo *mơ hồ* nếu có nhiều `prefix` cho cùng `suffix`.

**(C) Truy vấn theo `CP`**
- Liệt kê các CP trùng `code`: `page` neo, `bbox`, `target_page` (nếu có).
- Nêu rõ “liên trang qua CP”, **không** coi là on-page.

**(D) Truy vấn theo trang**
- Liệt kê các tag trên trang: hiển thị {{raw, unit, prefix, suffix, variant, bbox?}}.
- Có thể nhóm theo `(unit, prefix, suffix)` để người đọc dễ theo dõi (chỉ là nhóm hiển thị).

### 4.3 Định dạng JSON trả về (tuỳ chọn, dành cho máy đọc)
> Đây là **định dạng trình bày dữ liệu**, không chứa thuật toán/xếp hạng.

```json
{{
  "query": "chuỗi người dùng",
  "answer": "Mô tả ngắn gọn dựa trên dữ liệu (trung lập).",
  "records": [
    {{
      "raw": "04 IS 501",
      "unit": "04",
      "prefix": "IS",
      "suffix": "501",
      "variant": "",
      "page": 54,
      "bbox": [x0,y0,x1,y1]
    }}
  ],
  "related": {{
    "variants": [
      {{"raw":"04 ZSL 4047A","page":54}}
    ],
    "offpage_connectors": [
      {{"code":"CP25-03","page":54,"target_page":55}}
    ]
  }},
  "notes": [
    "Nếu có mơ hồ/thiếu trường: nêu tại đây."
  ]
}}
```

> `page` hiển thị ở đây là **1-based**. Bên trong hệ thống nếu lưu 0-based thì cộng +1 khi hiển thị.

---

## 5) Mẫu prompt tham chiếu (Data-Use Prompts)

**System (tham chiếu, trung lập):**
```
Bạn là Data Agent cho P&ID. Chỉ sử dụng dữ liệu có trong README.md, MODEL.md và các artefacts CSV/PNG kèm theo.
Mọi kết quả phải có bằng chứng (page 1-based, raw, và nếu có thì bbox/CP). Không đưa phương án/heuristic.
Phân biệt on-page và cross-page (CP). Nếu thiếu dữ liệu, ghi rõ “khuyết trường dữ liệu”.
```

**User → Assistant (ví dụ 1 — tìm tag đầy đủ):**
```
Tìm "04 IS 501". Hãy trả về raw, unit/prefix/suffix/variant, page (1-based), và bbox (nếu có).
Nếu có các biến thể liên quan trong cùng (unit,prefix,suffix), liệt kê.
```

**User → Assistant (ví dụ 2 — chỉ có suffix):**
```
Tôi có suffix "5145". Liệt kê tất cả (unit?, prefix, suffix) có trong dữ liệu, kèm page (1-based).
Nếu có nhiều prefix cho cùng suffix, ghi chú mơ hồ.
```

**User → Assistant (ví dụ 3 — theo CP):**
```
Tìm "CP25-03". Nêu page neo (1-based), bbox nếu có, và target_page (nếu xác định được).
```

**User → Assistant (ví dụ 4 — theo trang):**
```
Liệt kê các tag trên trang 54 (1-based). Trả về raw, unit/prefix/suffix/variant và bbox nếu có.
```

---

## 6) Kiểm tra tính đúng đắn trước khi trả lời (Validation Checklist)

1. **Chuẩn hoá input** về `[UNIT] PREFIX[-/ ]?SUFFIX[VARIANT]` (nếu có thể).
2. **Tồn tại dữ liệu**: mọi tag/CP trích dẫn phải có trong CSV/bằng chứng.
3. **Bằng chứng đủ tối thiểu**: `page` (1-based) + `raw`.
4. **Phân biệt on-page vs cross-page** (CP ≠ on-page).
5. **Mơ hồ được nêu rõ**: multi-prefix-per-suffix, thiếu `UNIT`/`target_page`, OCR nghi vấn.
6. **Không suy diễn vận hành**: chỉ mô tả dữ liệu.
7. **Định dạng**: sắp xếp theo `page` tăng dần; giữ `raw` nguyên văn.
8. **Nhất quán đơn vị trang**: nội bộ 0-based → hiển thị 1-based.

---

## 7) Hạn chế & an toàn

- Không đưa khuyến nghị vận hành, **không** thay thế SOP/MOC/POE.
- Không điền giả `UNIT/VARIANT` khi không có bằng chứng.
- Nếu chữ bị nhòe/thiếu do OCR, phải nói rõ “nghi vấn OCR” và đính kèm `raw`/`bbox` để người dùng kiểm tra lại trên bản vẽ.

---

## 8) Phụ lục — Tham chiếu artefacts

- [tags_spatial_unit_prefix_suffix.csv](sandbox:/mnt/data/tags_spatial_unit_prefix_suffix.csv) — tập tag đã gán theo **không gian** (unit/prefix/suffix/bbox).
- [group_span_no_unit.csv](sandbox:/mnt/data/group_span_no_unit.csv) / [group_span_with_unit.csv](sandbox:/mnt/data/group_span_with_unit.csv) — span nhóm theo trang (so sánh có/không `UNIT`).
- [cp_occurrences_pymupdf.csv](sandbox:/mnt/data/cp_occurrences_pymupdf.csv) — xuất hiện `CP`.
- [spatial_unit_distribution.csv](sandbox:/mnt/data/spatial_unit_distribution.csv), [spatial_prefix_counts.csv](sandbox:/mnt/data/spatial_prefix_counts.csv) — phân bố `UNIT` và thống kê `PREFIX`.
- [annot_terms_page_54.png](sandbox:/mnt/data/annot_terms_page_54.png), [hit_5145_p54.png](sandbox:/mnt/data/hit_5145_p54.png) — ảnh chú thích minh hoạ.

---

*AGENT.md này đặt ra **quy tắc dùng dữ liệu** (chứng cứ, chuẩn hoá, trình bày, xử lý mơ hồ) để trả lời đúng thực tế P&ID. Không bao gồm thuật toán, trọng số hay xếp hạng.*
