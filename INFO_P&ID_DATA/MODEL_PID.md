
# MODEL.md — **Mô hình & Ngữ nghĩa Dữ liệu** (P&ID Ammonia Unit)

> **Mục đích:** mô tả **mô hình dữ liệu** (entities, trường, ràng buộc, quan hệ, quy ước biểu diễn) để AI Agent hiểu **bản chất dữ liệu** trong P&ID.
> **Không** nêu phương án/thuật toán/xếp hạng. Tài liệu này chỉ quy định **cách dữ liệu được mô tả và hiểu**.

**Phiên bản:** v1.2 • Cập nhật: 2025-10-18

---

## 0) Tổng quan mô hình

Các thực thể chính và quan hệ giữa chúng:

```
Page ── contains ──> Tag
Tag  ── grouped_by (unit?, prefix, suffix) ──> LoopGroup
Tag  ── connected_on_page ──> Tag                      (Connection)
Tag  ── may anchor ──> OffPageConnector (CP) ── links_to ──> Page (target_page?)
```

- **Page**: siêu dữ liệu của mỗi trang P&ID.
- **Tag**: một ký hiệu thiết bị/điểm đo/nút logic hiển thị trên trang.
- **LoopGroup**: nhóm logic của các Tag có **cùng** `(unit?, prefix, suffix)`; `variant` là nhánh trong nhóm.
- **Connection** *(tuỳ chọn)*: liên kết **trên cùng trang** giữa các Tag (nếu trích xuất được).
- **OffPageConnector (CP)**: ký hiệu liên trang; neo ở một Page và có thể chỉ đến `target_page` khác.

> Lưu ý: mô hình này **mô tả dữ liệu** như hiện có trong P&ID; không bao gồm diễn giải vận hành hay quy tắc thiết kế ngoài tài liệu.

---

## 1) Quy ước định danh Tag

### 1.1 Dạng tổng quát

```
[UNIT] PREFIX[-/ ]?SUFFIX[VARIANT]
```

- **`UNIT`** *(tuỳ chọn)*: chuỗi **số** 1–3 ký tự (ví dụ `"04"`), là mã đơn vị/khu vực; trên bản vẽ thường nằm trong ô tam giác/góc.
- **`PREFIX`**: chuỗi **chữ** 1–6 ký tự in hoa (ví dụ: `IS`, `TAH`, `TAHH`, `FIC`, `ZSL`, …).
  - Các chuỗi như `TAH`, `TAHH` là **toàn bộ prefix**, **không** phải variant.
- **Phân tách** giữa `PREFIX` và `SUFFIX` có thể là **dấu cách**, `-`, `/`, hoặc **không có**, tuỳ bố cục ký hiệu.
- **`SUFFIX`**: chuỗi **số** 3–6 ký tự (ví dụ: `501`, `5145`).
- **`VARIANT`** *(tuỳ chọn)*: **1 chữ** in hoa **sau `SUFFIX`** (ví dụ: `A`, `B`, `C`) thể hiện nhánh song song/dự phòng theo quy ước site.

### 1.2 Ví dụ chuẩn hoá (từ dataset)
- `04 IS 501`  → `unit="04"`, `prefix="IS"`,   `suffix="501"`,  `variant=""`
- `04 TAH 5145` → `unit="04"`, `prefix="TAH"`,  `suffix="5145"`, `variant=""`
- `04 TAHH 5145`→ `unit="04"`, `prefix="TAHH"`, `suffix="5145"`, `variant=""`
- `04 ZSL 4047A`→ `unit="04"`, `prefix="ZSL"`,  `suffix="4047"`, `variant="A"`

### 1.3 Mẫu biểu thức chính quy (regex) tham chiếu
> Dùng để **kiểm tra hợp lệ dữ liệu** (validation), không phải mô tả thuật toán tách chuỗi.

- `unit`: `^\d{1,3}$`
- `prefix`: `^[A-Z]{1,6}$`
- `suffix`: `^\d{3,6}$`
- `variant`: `^[A-Z]?$` *(rỗng hoặc 1 chữ)*

**Kiểm tra mẫu trên chuỗi liền (sau khi loại bỏ xuống dòng):**
```
^(?:(?P<unit>\d{1,3})\s+)?(?P<prefix>[A-Z]{1,6})[-/ ]?(?P<suffix>\d{3,6})(?P<variant>[A-Z])?$
```

> Bảo toàn `raw` (nguyên văn từ bản vẽ) để truy vết khi dữ liệu bị chia dòng/ô.

---

## 2) Thực thể & Trường Dữ liệu

### 2.1 `Page`
| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|:---:|---|
| `index` | integer | ✓ | Số thứ tự trang trong PDF (0-based hoặc 1-based — cần cố định nhất quán khi dùng chung). |
| `title` | string |  | Tiêu đề trang nếu có. |
| `area` | string |  | Mã/khu vực tiến trình nếu có. |
| `width` | number |  | Chiều rộng trang (pt, nếu có). |
| `height` | number |  | Chiều cao trang (pt, nếu có). |
| `notes` | string |  | Ghi chú tự do. |

**Ràng buộc:** `index` là duy nhất trong file nguồn.

---

### 2.2 `Tag`
| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|:---:|---|
| `raw` | string | ✓ | Chuỗi thô như bản vẽ (để truy vết). Có thể gồm khoảng trắng/ngắt dòng. |
| `unit` | string |  | Mã số đơn vị/khu vực (ví dụ `"04"`). |
| `prefix` | string | ✓ | 1–6 chữ cái in hoa (ví dụ `IS`, `TAH`, `TAHH`, `FIC`…). |
| `suffix` | string | ✓ | 3–6 chữ số (lưu **dạng chuỗi** để giữ 0 đầu nếu có). |
| `variant` | string |  | `""` hoặc 1 chữ cái (ví dụ `A|B|C`). |
| `page` | integer | ✓ | Trang nơi tag xuất hiện. |
| `bbox` | `[number,number,number,number]` |  | Hộp bao quanh (x0,y0,x1,y1) theo **PDF user space** (origin trái–dưới). |
| `confidence` | number |  | Mức tin cậy khi nhận dạng/chuẩn hoá (0.0–1.0). |
| `attrs` | object |  | Thuộc tính mở rộng theo legend/site (không ép buộc). |

**Khoá & chỉ mục:**
- **Khoá hiển thị** (phân biệt một lần xuất hiện cụ thể): `(unit?, prefix, suffix, variant?, page, bbox?)`.
- **Khoá nhóm logic** (xem LoopGroup): `(unit?, prefix, suffix)`.

**Chuẩn hoá & ngữ nghĩa:**
- `prefix` là **chữ**; các hậu tố chức năng như `…H`/`…HH` thuộc **prefix**, **không** phải `variant`.
- `variant` là **chữ cuối sau suffix** nếu có.
- `suffix` để dạng **string** để bảo toàn mọi chữ số (kể cả 0 ở đầu).
- `unit` là **string số**, có thể rỗng nếu ký hiệu không kèm unit.

---

### 2.3 `LoopGroup`
| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|:---:|---|
| `key` | object | ✓ | `{ "unit": string?, "prefix": string, "suffix": string }` |
| `members` | `Tag[]` \| `string[]` |  | Danh sách Tag (hoặc id Tag) thuộc nhóm. |
| `pages` | `integer[]` |  | Các trang nơi nhóm xuất hiện. |
| `span` | integer |  | Độ trải trang: `max(pages) - min(pages)`. |
| `variants` | string |  | Chuỗi tổng hợp biến thể (ví dụ `"ABC"`, `"A"`, `""`). |
| `flags` | `string[]` |  | Cờ dữ liệu: ví dụ `"multi_prefix_suffix"`, `"ocr_suspect"`. |

**Ngữ nghĩa:**
- `LoopGroup` gom theo *định danh logic* `(unit?, prefix, suffix)`. `variant` là **nhánh** bên trong cùng nhóm.
- Không ngầm định loại thiết bị hay hành vi điều khiển; xem thêm `attrs` của Tag nếu có.

---

### 2.4 `OffPageConnector` (CP)
| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|:---:|---|
| `code` | string | ✓ | Mã CP (ví dụ: `CP25-03`), viết hoa. |
| `page` | integer | ✓ | Trang **neo** của CP. |
| `target_page` | integer |  | Trang đích nếu xác định được (có thể khuyết). |
| `bbox` | `[number,number,number,number]` |  | Hộp bao quanh ký hiệu CP. |
| `side` | string |  | Vị trí tương đối trên khung: `N,E,S,W,NE,NW,SE,SW,CENTER`. |
| `notes` | string |  | Ghi chú đi kèm. |

**Ràng buộc:**
- `code` **không nhất thiết duy nhất** toàn bộ file; có thể xuất hiện nhiều nơi.
- `target_page` có thể **khuyết** khi bản vẽ không ghi rõ.

---

### 2.5 `Connection` *(on-page, tuỳ chọn)*
| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|:---:|---|
| `from_tag` | string \| object | ✓ | Tham chiếu đến Tag nguồn (id hoặc đối tượng). |
| `to_tag` | string \| object | ✓ | Tham chiếu đến Tag đích. |
| `page` | integer | ✓ | Trang nơi quan sát kết nối. |
| `line_class` | string |  | Lớp đường ống/tín hiệu (nếu suy ra từ ký hiệu). |
| `direction` | string |  | Hướng nếu thể hiện (ví dụ `→`, `←`, `↔`). |
| `bbox` | `[number,number,number,number]` |  | Hộp bao quanh vùng kết nối. |
| `notes` | string |  | Ghi chú tự do. |

**Ngữ nghĩa:** `Connection` chỉ mô tả **kết nối trên cùng trang**; liên trang dùng `OffPageConnector`.

---

## 3) Quan hệ & ràng buộc toàn vẹn

- **Chứa–thuộc (containment)**: `Page.index` → `Tag.page` (một-nhiều).
- **Nhóm (grouping)**: `LoopGroup.key` = `(unit?, prefix, suffix)` → tập `Tag` có cùng bộ khoá.
- **Kết nối on-page**: `Connection.page` = `Tag.page` của cả `from_tag` và `to_tag`.
- **Liên trang (CP)**: `OffPageConnector.page` neo tại một trang; `target_page` nếu xác định được.

**Tính duy nhất & khoá:**
- `Page.index` là duy nhất trong file.
- `Tag` không bắt buộc duy nhất theo `(unit,prefix,suffix)` vì có thể lặp xuất hiện (nhiều `page`/`bbox`).
- `LoopGroup.key` xác định **duy nhất** một nhóm logic.

**Kiểu & hợp lệ giá trị:**
- `unit` là **string số** (không phải integer) để giữ nguyên hình thức gốc.
- `suffix` là **string số** (lưu dưới dạng chuỗi).
- `prefix`, `variant` là **chữ in hoa**.
- `bbox` theo **PDF user space**; origin **trái–dưới** (tuỳ engine).

---

## 4) Ví dụ bản ghi hợp lệ (từ dataset)

### 4.1 Tag
```json
{
  "raw": "04  TAH  5145",
  "unit": "04",
  "prefix": "TAH",
  "suffix": "5145",
  "variant": "",
  "page": 53,
  "bbox": [735.2, 405.6, 780.9, 422.1],
  "confidence": 0.93,
  "attrs": {}
}
```

```json
{
  "raw": "04 IS 501",
  "unit": "04",
  "prefix": "IS",
  "suffix": "501",
  "variant": "",
  "page": 53
}
```

### 4.2 OffPageConnector
```json
{
  "code": "CP25-03",
  "page": 53,
  "bbox": [120.0, 180.0, 138.0, 198.0],
  "side": "E",
  "target_page": 54
}
```

### 4.3 LoopGroup
```json
{
  "key": { "unit": "04", "prefix": "TAH", "suffix": "5145" },
  "members": ["04 TAH 5145", "04 TAHH 5145"],
  "pages": [53],
  "span": 0,
  "variants": "",
  "flags": []
}
```

> Số liệu `page` minh hoạ tính theo **0-based** trong dữ liệu phân tích; khi trình bày cho người dùng cuối có thể dùng **1-based** tuỳ quy ước.

---

## 5) JSON Schema (rút gọn, chuẩn hoá lưu trữ)

> Mục tiêu: đảm bảo định dạng thống nhất khi lưu CSV/JSON; **không** mô tả thuật toán.

```json
{
  "$id": "page.schema.json",
  "type": "object",
  "properties": {
    "index":{"type":"integer","minimum":0},
    "title":{"type":"string"},
    "area":{"type":"string"},
    "width":{"type":"number"},
    "height":{"type":"number"},
    "notes":{"type":"string"}
  },
  "required":["index"]
}
```

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
  "$id": "loopgroup.schema.json",
  "type": "object",
  "properties": {
    "key": {
      "type":"object",
      "properties": {
        "unit":{"type":"string"},
        "prefix":{"type":"string"},
        "suffix":{"type":"string"}
      },
      "required":["prefix","suffix"]
    },
    "members":{"type":"array"},
    "pages":{"type":"array","items":{"type":"integer"}},
    "span":{"type":"integer","minimum":0},
    "variants":{"type":"string"},
    "flags":{"type":"array","items":{"type":"string"}}
  },
  "required":["key"]
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
  "$id": "connection.schema.json",
  "type": "object",
  "properties": {
    "from_tag":{"type":["string","object"]},
    "to_tag":{"type":["string","object"]},
    "page":{"type":"integer","minimum":0},
    "line_class":{"type":"string"},
    "direction":{"type":"string"},
    "bbox":{"type":"array","items":{"type":"number"},"minItems":4,"maxItems":4},
    "notes":{"type":"string"}
  },
  "required":["from_tag","to_tag","page"]
}
```

---

## 6) Taxonomy (bảng nghĩa `prefix`) — phụ thuộc legend

> Bảng này **điền theo legend của bộ P&ID cụ thể**, không suy đoán. Ví dụ khung:

| Prefix | Nghĩa (per legend) | Nhóm (Instrument/Valve/Equip/…) | Ghi chú site |
|---|---|---|---|
| IS  | (theo legend) | Instrument | … |
| TAH | (theo legend) | … | … |
| TAHH| (theo legend) | … | … |
| FIC | Flow Indicating Controller | Instrument | … |
| ZSL | (theo legend) | Switch | … |
| …  | … | … | … |

---

## 7) Ghi chú đặc thù dữ liệu (trung lập)

- `UNIT` xuất hiện rộng rãi và **có ý nghĩa phân vùng**; nên giữ như trường riêng để phản ánh bản chất dữ liệu.
- Có hiện tượng một `suffix` đi kèm nhiều `prefix` khác nhau (tái sử dụng/mã hệ thống).
- `variant` (A/B/C) là nhánh song song/dự phòng; thuộc cùng `(unit?, prefix, suffix)`.
- `CP` là liên kết **liên trang**, không phải on-page; `target_page` có thể khuyết.

---

## 8) Phiên bản & Truy vết

- `model_version`: v1.2
- `updated_at`: 2025-10-18
- Thay đổi so với v1.1: mở rộng giải thích trường, thêm Page schema, Connection schema, ví dụ JSON minh hoạ.
