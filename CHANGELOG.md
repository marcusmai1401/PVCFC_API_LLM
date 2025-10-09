# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **IEEE-Style Citation Feature** (2025-10-09)
  - Automatic conversion of `[Doc X, p.Y]` citations to IEEE-style `[n]` format
  - Interactive References section with numbered bibliography
  - Clickable PDF page links that open documents at exact pages
  - New `/api/pdf/open` endpoint for direct PDF viewing in browser
  - PDF fallback to image rendering with visual indicators (⚠️ icon)
  - Configurable toggle to switch between IEEE and traditional citation formats
  - Backend doc_number_map metadata export for citation mapping
  - Comprehensive unit test suite (9 tests, 100% pass rate)
  - Complete documentation in `docs/IEEE_CITATION_FEATURE.md`

### Changed
- Updated `app/rag/generator.py` to export document mapping metadata
- Enhanced `streamlit_app/components/query_lab_improved.py` with citation conversion logic
- Modified Query Lab UI to display 7 tabs instead of 8 (removed duplicate Citations tab)
- Improved citation display with file names extracted from PDF paths

### Fixed
- Citation deduplication when same document is referenced multiple times
- Page number aggregation for documents cited across multiple pages
- Graceful handling of missing PDF files with automatic fallback

## [Previous Versions]

_(Add previous version history here as needed)_

---

## Release Notes

### IEEE Citation Feature v1.0.0 (2025-10-09)

This major feature enhances the RAG system's citation handling with IEEE-style formatting and interactive PDF navigation.

**Key Benefits:**
- 📚 Professional IEEE-style citation format
- 🔗 One-click navigation to cited PDF pages
- ⚙️ Flexible configuration via UI toggle
- 🛡️ Robust error handling and fallbacks
- ✅ Full test coverage

**Breaking Changes:** None (fully backward compatible)

**Migration:** No migration needed. Feature is opt-in via UI toggle.

**Documentation:** See [docs/IEEE_CITATION_FEATURE.md](docs/IEEE_CITATION_FEATURE.md)

**Testing:** Run `python tests/unit/test_ieee_citation_formatter.py`
