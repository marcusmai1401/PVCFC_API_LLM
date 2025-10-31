# Phân Tích Prefixes Thiếu Trong Whitelist

## Vấn Đề

Ground truth queries yêu cầu 5 tags KHÔNG tồn tại trong index vì prefix không có trong whitelist:

| Query | Tag | Prefix | Expected Page | Trong Whitelist? |
|-------|-----|--------|---------------|------------------|
| 1 | 04 PSV 3926 | **PSV** | 41 | ❌ NO |
| 2 | 04 TI 5058 | **TI** | 58 | ❌ NO |
| 3 | 04 TXI 2077 | **TXI** | 17 | ❌ NO |
| 4 | 04 ZI 4502 | **ZI** | 100 | ❌ NO |
| 5 | 06 FIC 1134 | **FIC** | 103 | ✅ YES (line 40) |

## Prefixes Hiện Tại Trong Index (207 tags)

Extracted prefixes: FT, IS, LT, PAL, PALL, PI, PSU, PT, PU, TT, ZSL

**Prefixes trong whitelist (config/tag_grammar.yaml):**
- Pressure: PAL, PAHH, PALL, PSAH, PSAL, PT, PI, PIC, PXI, PSU, PXT, PDAHH, PDALL
- Flow: **FIC**, FT, FSL, FFSAL
- Level: LIC, LT, LSH, LSHH, LSAH
- Temperature: **TIC**, TT, TSH, TSHH, TAH, TAHH
- Others: HIC, IS, PU, MU, HE, VL, ZSL

## Prefixes Cần Thêm (theo ISA 5.1 Standard)

### 1. PSV - Pressure Safety Valve
- **Function**: Safety relief valve
- **Common usage**: Overpressure protection
- **Example**: 04 PSV 3926

### 2. TI - Temperature Indicator
- **Function**: Local temperature display
- **Common usage**: Visual temperature monitoring
- **Example**: 04 TI 5058
- **Note**: TIC đã có, TI thiếu

### 3. TXI - Temperature Transmitter Indicator
- **Function**: Temperature transmitter with local indicator
- **Common usage**: Remote temperature monitoring with local display
- **Example**: 04 TXI 2077
- **Note**: X = transmit function modifier

### 4. ZI - Position Indicator
- **Function**: Position/status indicator
- **Common usage**: Valve position, damper position
- **Example**: 04 ZI 4502
- **Note**: ZSL đã có (Position Switch Low), ZI thiếu

### 5. Additional Common Prefixes (Recommended)

Based on ISA 5.1 and common P&ID practice:

**Pressure:**
- PSV - Pressure Safety Valve
- PSH - Pressure Switch High
- PSL - Pressure Switch Low
- PSHH - Pressure Switch High-High
- PSLL - Pressure Switch Low-Low
- PDI - Pressure Differential Indicator
- PDIC - Pressure Differential Indicator Controller

**Temperature:**
- TI - Temperature Indicator
- TXI - Temperature Transmitter Indicator
- TSL - Temperature Switch Low
- TSLL - Temperature Switch Low-Low
- TAL - Temperature Alarm Low
- TALL - Temperature Alarm Low-Low

**Flow:**
- FI - Flow Indicator
- FXI - Flow Transmitter Indicator
- FSH - Flow Switch High
- FSHH - Flow Switch High-High
- FAL - Flow Alarm Low
- FAH - Flow Alarm High

**Level:**
- LI - Level Indicator
- LXI - Level Transmitter Indicator
- LSL - Level Switch Low
- LSLL - Level Switch Low-Low
- LAL - Level Alarm Low
- LAH - Level Alarm High

**Position/Status:**
- ZI - Position Indicator
- ZT - Position Transmitter
- ZSH - Position Switch High
- ZIC - Position Indicator Controller
- ZE - Position Element

**Analytical:**
- AI - Analyzer Indicator
- AIC - Analyzer Indicator Controller
- AT - Analyzer Transmitter

**Speed:**
- SI - Speed Indicator
- SIC - Speed Indicator Controller
- ST - Speed Transmitter

**Vibration:**
- VI - Vibration Indicator
- VT - Vibration Transmitter

## Hành Động Khuyến Nghị

### Option A: Minimal Fix (Chỉ thêm 4 prefix thiếu)
```yaml
# Add to config/tag_grammar.yaml prefix_whitelist:
- PSV      # Pressure safety valve
- TI       # Temperature indicator
- TXI      # Temperature transmitter indicator
- ZI       # Position indicator
```

**Pros:**
- Nhanh, chỉ thêm đủ để pass test
- Risk thấp

**Cons:**
- Vẫn thiếu nhiều prefixes khác có thể cần sau

### Option B: Comprehensive Update (Thêm full ISA 5.1 prefixes)
Thêm 30+ prefixes phổ biến từ ISA 5.1

**Pros:**
- Đầy đủ, cover hầu hết P&ID industrial
- Future-proof

**Cons:**
- Cần test kỹ hơn
- Có thể extract noise nếu có false positives

### Option C: Adaptive Whitelist
Keep minimal + enable learning_mode để log unknown prefixes

**Pros:**
- Học từ data thực tế
- Không miss genuine tags

**Cons:**
- Cần 2-phase: extract, review logs, update, re-extract

## Khuyến Nghị

**Start với Option A** (minimal) để pass test ngay, sau đó expand dần khi cần.

## Steps để Fix

1. Thêm 4 prefixes vào `config/tag_grammar.yaml`
2. Re-run ingestion cho Ammonia PDF: `python tools/ingest.py --source-dir "D:\Data_Raw" --output-dir "artifacts\ingestion_production" --enable-pid-tags --enable-ocr`
3. Re-index tags: `python scripts/opensearch/bulk_upsert_tags.py`
4. Run test lại: `python test_pid_accuracy_5queries.py`

Expected: 5/5 PASS (hoặc tối thiểu 4/5)
