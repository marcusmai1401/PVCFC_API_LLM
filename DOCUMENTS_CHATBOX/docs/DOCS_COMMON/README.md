# PVCFC RAG API — Documentation Index

Tài liệu được tổ chức theo phase và chủ đề. Đây là mục lục tổng hợp giúp định hướng nhanh.

## Phase 0 — Foundation
- Quickstart, Dev/Test/Smoke, Docker, Config cơ bản: xem `CHANGLOG_README/README_Phase0.md`

## Phase 1 — Document Processing & Indexing
- Tổng kết Phase 1: `CHANGLOG_README/phase1_final_report.md`
- Implementation summary: `docs/phase1_implementation_summary.md`
- Development notes: `docs/phase1_development_notes.md`
- Verification summary: `docs/phase1_verification_summary.md`
- Developer readme (development-time): `docs/phase1_readme.md`

## Phase 2 — RAG API (Hybrid Retrieval + Rerank + Generation)
- Final report (changelog): `CHANGLOG_README/Phase2_Final_Report.md`
- Implementation summary: `docs/phase2_implementation_summary.md`
- Implementation roadmap: `docs/phase2_implementation_roadmap.md`
- Query transformation (HyDE) sprint notes: `docs/sprint1_1_query_transformation.md`

## Provider & LLM Config
- Provider flexibility & hướng dẫn cấu hình nhiều nhà cung cấp: `docs/provider_flexibility_guide.md`
- LLM tiers (light/heavy) và cách chọn model: `docs/llm_config_tiers.md`

## Quality & Process
- Pre-commit fix guide: `docs/pre_commit_fix_guide.md`
- Bug fixes summary: `docs/bug_fixes_summary.md`

## Developer Handbook
- Gộp hướng dẫn chi tiết cho Phase 1 + 2: `docs/Developer_Handbook.md`

## Khuyến nghị sắp xếp & đặt tên (đã áp dụng)
- Mỗi phase chỉ 1 changelog chính trong `CHANGLOG_README/` (đã chuẩn hóa).
- Tất cả tài liệu “how-to/guide” để ở `docs/`.
- Tài liệu “phase summary/final report” nên đặt ở `CHANGLOG_README/` để thống nhất.

## Gợi ý cải tiến tiếp
- Thêm mục “Change diff highlights” vào mỗi file changelog phase.
- Gom các note tản mạn trong Phase 1 vào 1 “developer handbook” rút gọn.
- Thêm `docs/OPERATIONS.md` (runbook, alerts, metrics dashboards) khi Phase 3/4.
