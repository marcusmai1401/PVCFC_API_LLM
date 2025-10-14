# Design_UI.md — PVCFC RAG • Material Design 3 (Material You) — **Expressive** Style

> Audience: AI Agent (UI/UX + Frontend).
> Goal: Redesign toàn bộ UI cho PVCFC RAG theo **Material Design 3 (Material You) – Expressive**: hiện đại, tinh tế, dễ đọc, nhất quán, hỗ trợ dark mode, a11y tốt.
> Scope: Web dashboard “RAG QA + cấu hình”, có thể áp dụng dần cho những màn khác.

---

## 1) Tóm tắt phong cách (Style Overview)
- **Tên style:** Material Design 3 (**M3 / Material You**) – nhánh **Expressive**.
- **Đặc trưng:** màu sắc giàu sắc độ (tonal), **shape bo lớn (pill)**, **motion mượt mà**, **layout rõ ràng**, **typography dẫn hướng**; tập trung vào “**containment**” (thẻ, chip, thanh điều khiển) để nhấn mạnh ngữ cảnh.
- **Điểm mấu chốt:**
  - **Dynamic Color / Tonal Palettes**: sinh palette tự động từ “màu seed” (có thể lấy từ brand), đảm bảo đồng bộ cả light/dark.
  - **Design Tokens** (color roles, type, shape, elevation) → ánh xạ trực tiếp vào CSS vars/theme.
  - **Expressive motion**: chuyển động thông tin, mượt, giúp định vị chú ý.
  - **A11y**: tương phản chuẩn AA, focus ring nổi bật, trạng thái rõ.

> Tham khảo: Material 3 & Expressive, color/roles/tokens, elevation/shape/motion/type, a11y contrast. (Nguồn ở mục **Tài liệu** cuối file.)

---

## 2) Hệ **Design Tokens** (phải có)
> Tất cả màu, kích thước, bo góc, bóng, typographic scale, spacing… **phải** qua token để đổi nhanh giữa light/dark và kiểm thử.

### 2.1 Color tokens (vai trò → biến)
- **Vai trò chính (roles):** `primary`, `onPrimary`, `primaryContainer`, `onPrimaryContainer`, `secondary`, `tertiary`, `error`, `surface`, `onSurface`, `surfaceVariant`, `outline`, `inverseSurface`, `inverseOnSurface`, `inversePrimary`, v.v.
- **Tonal palettes:** 0–100 (10 bậc), pick theo role.
- **Dynamic Color:** nếu có “seed color” của PVCFC → sinh **tonal palettes** cho cả light/dark.
- **Biến gợi ý (CSS variables):**
  ```css
  :root {
    --sys-color-primary:        ...;
    --sys-color-on-primary:     ...;
    --sys-color-surface:        ...;
    --sys-color-on-surface:     ...;
    --sys-color-surface-variant:...;
    --sys-color-outline:        ...;
    /* ... đầy đủ roles cần dùng */
  }
  ```

### 2.2 Type tokens
- **Type roles:** `display`, `headline`, `title`, `label`, `body`.
- **Scale:** 15 **baseline** + 15 **emphasized** (variable size/weight).
- **Font:** ưu tiên sans-serif biến thể variable (ví dụ: *Inter*, *Roboto Flex*) để tinh chỉnh weight/grade.

### 2.3 Shape tokens (bo góc)
- Thang **10 cấp** bo góc (từ vuông → tròn).
- Với Expressive: dùng **pill / large round** cho FAB, button group, chip; card/list dùng bo vừa.

### 2.4 Elevation tokens (độ cao/bóng)
- **Resting:** cấp 0 → +3.
- **Interactive:** **+4** (hover) và **+5** (drag/raised).
- Kết hợp **state layer** (màu đè) để thể hiện hover/pressed rõ ràng.

---

## 3) Màu sắc (Color System)
### 3.1 Chiến lược
1) Chọn **seed color** (ví dụ xanh PVCFC).
2) Sinh **tonal palettes** (0–100) → map sang **color roles**.
3) Xuất **theme light/dark** (tokens).
4) Kiểm **WCAG**: text nhỏ ≥ **4.5:1**, text lớn ≥ **3:1**, **UI non-text** (nút/biên) ≥ **3:1**.
5) Tạo **state layer** (hover/press/focus) bằng overlay cùng hue, tăng/giảm alpha.

### 3.2 Hướng dẫn cho Agent
- Tự động hóa sinh palette (script) hoặc dùng công cụ Material color utilities.
- Với components chứa dữ liệu (bảng, kết quả RAG), ưu tiên **surface/surfaceVariant** để nền dịu, **primary** dùng tiết kiệm cho CTA.
- Dark mode: **onSurface** luôn rõ ràng; dùng **inverseSurface** cho vùng nổi bật (snackbar, bottom sheet).

---

## 4) Chữ (Typography)
- Dùng **roles** để dẫn nhịp đọc:
  - `display` cho hero/tiêu đề lớn màn chính.
  - `headline` cho khu vực/khối nội dung.
  - `title` cho đề mục/nhãn nhóm.
  - `label` cho nút/chip/badge.
  - `body` cho mô tả, kết quả truy vấn, citation.
- Chọn **1–2 font** tối đa, bật **ligatures** & **tabular numbers** cho số liệu nếu có.
- Line-height thoáng (1.3–1.5) cho body, giảm ở title/label.

---

## 5) Hình khối (Shape)
- **Pill / rounded-large** cho: toolbar gộp, segmented button, chip filter.
- **Medium** corner cho: card, list item, search field.
- **Small** cho: table cell, menu, tooltip.

---

## 6) Elevation & Surface
- Nền **surface** phẳng (**level 0**) cho vùng đọc chính.
- **Card/list**: level 1–2; **App bar**: 0 → 2 khi scroll; **Popover/Dialog**: 3–4; **dragging**: 5.
- Trạng thái: kết hợp **elevation + state layer** (hover nhạt, pressed đậm, focus ring rõ).

---

## 7) Chuyển động (Motion)
- Dùng **Expressive motion scheme** (mượt, có độ đàn hồi hợp lý).
- **Nguyên tắc:** chỉ dùng motion khi có ý nghĩa (dẫn hướng, phản hồi).
- **Áp dụng:**
  - Kết quả RAG tải → **progress indicator** sóng/conic (expressive).
  - Lọc/Sort → **container transform** nhẹ + fade nội dung.
  - Drawer/Sheet → **slide** theo trục, không parallax quá mạnh.

---

## 8) Trạng thái & A11y
- **Focus:** hiện **focus ring** rõ (2px), dùng `:focus-visible`; **đừng** chỉ đổi màu nền.
- **Hover/Pressed/Selected/Disabled:** dùng **state layer** + thay đổi elevation/outline.
- **Contrast:**
  - Text nhỏ **≥ 4.5:1**, text lớn **≥ 3:1**.
  - **UI non-text** (biên nút, icon trạng thái) **≥ 3:1**.
- **Hit area** tối thiểu 44×44 px.
- **Keyboard nav** phải đi hết mọi control; thứ tự tab theo trực quan.

---

## 9) Layout, Grid, Density
- **8dp grid** cho layout/spacing chính; **4dp** cho chi tiết nhỏ (icon, line-height).
- **Window size classes** (web responsive): compact / medium / expanded / large / extra-large.
- **Density**: cung cấp 3 mức (spacious / comfortable / compact) cho bảng & danh sách; mặc định **comfortable**.

---

## 10) Iconography
- Dùng **Material Symbols** (variable font): 3 style (outlined/rounded/sharp), trục **fill/weight/grade/optical size** → tối ưu tải & độ nét.
- Kích thước phổ biến 20–24px trong control, 18px cho chip/label nhỏ.
- Trạng thái: icon `on-*` màu tương phản đủ; dùng **filled** cho emphasis nhẹ.

---

## 11) Component spec (áp cho PVCFC RAG)

### 11.1 Khung màn (App shell)
- **Top App Bar** (medium) + **Navigation rail** (>= md) hoặc **Nav bar** (mobile).
- **Primary actions** (Ask, Run, Deploy) ở **right cluster** của app bar; **secondary** (history, settings) ở overflow.
- **Theme switch** (light/dark/system) trong header.

### 11.2 Khu **RAG QA**
- **Query Input**: search field lớn (shape=large), hỗ trợ multiline; action chips (language, mode).
- **Context Chunks** selector: segmented buttons (pill).
- **Retrieval Config**: card nhóm (FAISS K, BM25 K, Re-rank topN).
- **Run** button: **filled** primary; **Stop**: tonal/error.
- **Result Panel**:
  - **Answer card**: surface variant; tiêu đề = `title.large`, nội dung `body.large`.
  - **Citations**: list với **chip** (doc/page), click mở **side sheet** hiển thị preview.
  - **Feedback** (thumbs): icon button tonal, tooltip có delay ngắn.

### 11.3 **Filters / Tools**
- **Side sheet** (modal) cho bộ lọc (doc type, date, vendor), có **filter chips**.
- **Snackbar** cho thông báo ngắn; **Dialog** cho thao tác nguy hiểm (xóa index).

### 11.4 **Data-heavy**
- **Table**: density switch (comfortable/compact), **sticky header**, **progress cells** khi loading.
- **Empty state**: icon + hướng dẫn ngắn + CTA upload/index.

---

## 12) Tokens đề xuất (ví dụ nhanh)
> **Gợi ý** – thay bằng màu thương hiệu khi chốt seed color.

```css
:root[data-theme="light"] {
  --sys-color-primary:          oklch(60% 0.12 150);
  --sys-color-on-primary:       oklch(99% 0.01 150);
  --sys-color-surface:          oklch(99% 0.01 110);
  --sys-color-on-surface:       oklch(20% 0.03 110);
  --sys-color-surface-variant:  oklch(95% 0.02 110);
  --sys-color-outline:          oklch(55% 0.02 110);
  /* ... */
}
:root[data-theme="dark"] {
  --sys-color-primary:          oklch(75% 0.12 150);
  --sys-color-on-primary:       oklch(12% 0.02 150);
  --sys-color-surface:          oklch(13% 0.02 110);
  --sys-color-on-surface:       oklch(92% 0.02 110);
  --sys-color-surface-variant:  oklch(25% 0.02 110);
  --sys-color-outline:          oklch(60% 0.02 110);
}
```

---

## 13) Implementation notes (Web)
- **Ưu tiên**: dùng **Material Web (@material/web)** (Web Components M3) hoặc framework phù hợp (Angular Material, MUI*) để tiết kiệm thời gian.
- **Streamlit**: nếu chưa tách frontend, có thể tiêm CSS + JS nhỏ (focus ring, tokens) nhưng nên tách sang SPA để đạt M3 đầy đủ (motion, state layers, elevation).
- **Icons**: dùng **Material Symbols** (self-hosted subset) để giảm tải.

> \* Lưu ý: thư viện có thể không “match 100%” spec; giữ tokens/spacing/contrast theo M3 để nhất quán.

---

## 14) Checklist bàn giao
- [ ] 2 theme (light/dark) từ cùng **seed** (tonal palettes).
- [ ] Bộ **tokens** (JSON/CSS vars): color, type, shape, elevation, spacing.
- [ ] **Components** chủ lực: App bar, Nav, Buttons, Chips, Text fields, Selects, Cards, Table, Dialog, Snackbar, Progress.
- [ ] **States** đầy đủ (hover, pressed, focus-visible, selected, disabled).
- [ ] **A11y**: contrast pass; keyboard nav; screen reader labels.
- [ ] **Motion**: expressive cho nav, sheet, progress; durations/easings thống nhất.
- [ ] **Docs**: Figma styles + token file + hướng dẫn dev (map tokens → CSS/TS).

---

## 15) Hướng dẫn PROMPT cho AI Agent

**Vai trò & mục tiêu**
> Bạn là UI/UX + Frontend Engineer. Hãy thiết kế và xuất mã cho một dashboard web theo **Material Design 3 – Expressive** cho ứng dụng **PVCFC RAG** (QA + cấu hình).

**Ràng buộc chung**
- Dùng **design tokens** (color/type/shape/elevation).
- Grid 8dp, **density**: comfortable (có toggle).
- **A11y** AA: contrast, focus-visible, keyboard nav.
- **Motion**: expressive; không lạm dụng.
- **Icons**: Material Symbols (subsetting).
- Cần **light & dark** parity.

**Yêu cầu đầu ra**
1) **Figma**: Styles + Components (Auto layout, variants, states).
2) **Code** (chọn 1 trong 3):
   - **Material Web** (`@material/web`) + Vite + TS.
   - **Angular Material** (v17+) + theme tokens.
   - **React + MUI** (tùy biến theme gần M3, focus ring rõ).
3) **Token file**: `tokens.json` + `tokens.css` (CSS vars).
4) **Accessibility tests**: báo cáo contrast + tab order.
5) **Lottie/Animated progress**: 1 motion expressive cho loading dài.

**Prompt mẫu**

> *“Thiết kế UI PVCFC RAG theo Material 3 – Expressive.*
> *Tạo 2 theme (light/dark) từ seed color #0E7B55. Sinh tonal palettes và ánh xạ vào roles (primary, secondary, surface, surfaceVariant, error, outline…).*
> *Thiết kế các màn: (1) App shell (App bar + Nav rail/Nav bar), (2) RAG QA (Query input + Context Chunks segmented + Config card: FAISS K/BM25 K/Re-rank topN + Run), (3) Results (Answer card + Citations list + Side sheet preview), (4) Filters Dialog/Sheet, (5) Table log (density toggle), (6) Snackbar & Dialog.*
> *Áp dụng expressive motion (transitions) và state layers cho hover/pressed, focus-visible 2px. Kiểm tra contrast AA. Xuất tokens (JSON/CSS), component code (Angular/React/Web Components) + hướng dẫn tích hợp.”*

---

## 16) Tài liệu (tham chiếu nhanh)
- **M3 & Expressive**: blog “Building with M3 Expressive”, tổng quan M3.
- **Color system**: tonal palettes, color roles, tokens; dynamic color (Android).
- **Elevation**: levels 0→+5, resting/interactive; tokens.
- **Shape**: corner radius scale (10 cấp).
- **Motion**: expressive vs standard; transition patterns.
- **Type**: 15 baseline + 15 emphasized; roles.
- **A11y contrast**: WCAG 2.1; M3 color-contrast.
- **Layout & density**: 8dp/4dp grid; window size classes; spacing & density.
- **Icons**: Material Symbols (variable axes).
- **Web libs**: Material Web (@material/web); MUI/Angular Material.

> (Ghi chú: hãy tuân thủ các con số/chuẩn ở tài liệu gốc; nếu thư viện chưa theo kịp, ưu tiên giữ **tokens/contrast/states** đúng chuẩn.)

---

*Hết.*
