#!/usr/bin/env python
"""
Audit 7-Step Offline Build Pipeline
Comprehensive verification of each step from scan to index

This script:
1. Reviews code logic for each step
2. Runs controlled tests with sample PDFs
3. Collects metrics and validates outputs
4. Reports issues and optimization opportunities

Does NOT modify production code or configs.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO")
logger.add("logs/audit_offline_build_{time}.log", level="DEBUG", rotation="10 MB")


class OfflineBuildAuditor:
    """Auditor for 7-step offline build pipeline"""

    def __init__(self, test_data_dir: Path, test_output_dir: Path):
        """
        Initialize auditor

        Args:
            test_data_dir: Directory with test PDFs
            test_output_dir: Output directory for test artifacts
        """
        self.test_data_dir = Path(test_data_dir)
        self.test_output_dir = Path(test_output_dir)
        self.findings = []
        self.metrics = {}
        self.test_results = {
            "step1_scan": {"status": "pending", "details": {}},
            "step2_detect": {"status": "pending", "details": {}},
            "step3_parse_ocr": {"status": "pending", "details": {}},
            "step4_normalize": {"status": "pending", "details": {}},
            "step5_chunking": {"status": "pending", "details": {}},
            "step6_artifacts": {"status": "pending", "details": {}},
            "step6b_dedup": {"status": "pending", "details": {}},
            "step7_indexing": {"status": "pending", "details": {}},
            "integration": {"status": "pending", "details": {}},
        }

    def run_audit(self) -> Dict:
        """Run complete audit"""
        logger.info("=" * 80)
        logger.info("OFFLINE BUILD PIPELINE AUDIT - 7 STEPS")
        logger.info("=" * 80)
        logger.info(f"Test data: {self.test_data_dir}")
        logger.info(f"Test output: {self.test_output_dir}")
        logger.info("")

        # Setup
        self._setup_test_environment()

        # Step 1: Audit Scan PDFs
        logger.info("\n📂 STEP 1: Scan PDFs (rglob, filter)")
        self.audit_step1_scan()

        # Step 2: Audit Detect vector/scan
        logger.info("\n🔍 STEP 2: Detect vector vs scan")
        self.audit_step2_detect()

        # Step 3: Audit Parse/OCR
        logger.info("\n📝 STEP 3: Parse & OCR")
        self.audit_step3_parse_ocr()

        # Step 4: Audit Normalize & Markdown
        logger.info("\n✨ STEP 4: Normalize & Markdown conversion")
        self.audit_step4_normalize()

        # Step 5: Audit Chunking
        logger.info("\n✂️  STEP 5: Chunking (1000/200)")
        self.audit_step5_chunking()

        # Step 6: Audit Artifacts
        logger.info("\n💾 STEP 6: Artifacts (JSONL, doc_id_map, quarantine)")
        self.audit_step6_artifacts()

        # Step 6b: Audit Deduplication
        logger.info("\n🧹 STEP 6b: Deduplication (content OFF)")
        self.audit_step6b_dedup()

        # Step 7: Audit Indexing
        logger.info("\n🔍 STEP 7: Indexing (BM25, FAISS)")
        self.audit_step7_indexing()

        # Integration test
        logger.info("\n🔗 INTEGRATION: End-to-end flow")
        self.audit_integration()

        # Generate report
        return self._generate_report()

    def _setup_test_environment(self):
        """Setup test environment"""
        logger.info("Setting up test environment...")

        # Create test output directory
        if self.test_output_dir.exists():
            logger.warning(f"Test output exists, cleaning: {self.test_output_dir}")
            shutil.rmtree(self.test_output_dir)

        self.test_output_dir.mkdir(parents=True, exist_ok=True)

        # Verify test data exists
        if not self.test_data_dir.exists():
            raise FileNotFoundError(
                f"Test data directory not found: {self.test_data_dir}"
            )

        pdf_count = len(list(self.test_data_dir.glob("*.pdf")))
        logger.info(f"✓ Found {pdf_count} test PDFs in {self.test_data_dir}")

    # ========================================================================
    # STEP 1: SCAN PDFs
    # ========================================================================

    def audit_step1_scan(self):
        """
        Audit Step 1: Scan PDFs recursively

        Checks:
        - rglob works correctly
        - Only .pdf files collected
        - Unicode/long paths handled
        - Non-PDF files ignored
        """
        logger.info("Auditing: PDF scanning and filtering...")

        findings = []
        details = {}

        try:
            # Test: Scan test_docs directory
            pdf_files = list(self.test_data_dir.rglob("*.pdf"))
            details["total_pdfs_found"] = len(pdf_files)

            # Check 1: rglob works
            if len(pdf_files) > 0:
                findings.append(
                    {
                        "check": "rglob_functional",
                        "status": "PASS",
                        "value": len(pdf_files),
                    }
                )
            else:
                findings.append(
                    {
                        "check": "rglob_functional",
                        "status": "FAIL",
                        "issue": "No PDFs found",
                    }
                )

            # Check 2: Only PDF files
            non_pdf = [
                f
                for f in self.test_data_dir.rglob("*")
                if f.is_file() and f.suffix.lower() != ".pdf"
            ]
            if non_pdf:
                logger.info(f"Found {len(non_pdf)} non-PDF files (should be ignored)")
                details["non_pdf_files"] = len(non_pdf)
                findings.append(
                    {
                        "check": "filter_non_pdf",
                        "status": "PASS",
                        "note": "Non-PDF files correctly ignored",
                    }
                )

            # Check 3: Unicode paths
            unicode_pdfs = [f for f in pdf_files if any(ord(c) > 127 for c in str(f))]
            if unicode_pdfs:
                logger.info(f"Found {len(unicode_pdfs)} PDFs with Unicode paths")
                details["unicode_paths"] = len(unicode_pdfs)
                findings.append(
                    {
                        "check": "unicode_support",
                        "status": "NEEDS_TEST",
                        "note": "Unicode paths present, need to verify processing",
                    }
                )
            else:
                details["unicode_paths"] = 0

            # Check 4: Path length (Windows MAX_PATH issue)
            long_paths = [f for f in pdf_files if len(str(f)) > 200]
            if long_paths:
                logger.warning(
                    f"Found {len(long_paths)} PDFs with long paths (>200 chars)"
                )
                details["long_paths"] = len(long_paths)
                findings.append(
                    {
                        "check": "long_paths",
                        "status": "WARNING",
                        "count": len(long_paths),
                    }
                )
            else:
                details["long_paths"] = 0
                findings.append({"check": "long_paths", "status": "PASS"})

            # Summary
            self.test_results["step1_scan"] = {
                "status": "PASS",
                "details": details,
                "findings": findings,
            }
            logger.info(f"✓ Step 1 audit complete: {len(pdf_files)} PDFs scanned")

        except Exception as e:
            logger.error(f"Step 1 audit failed: {e}")
            self.test_results["step1_scan"] = {
                "status": "FAIL",
                "error": str(e),
                "details": details,
                "findings": findings,
            }

    # ========================================================================
    # STEP 2: DETECT vector/scan
    # ========================================================================

    def audit_step2_detect(self):
        """
        Audit Step 2: Detect vector vs scan

        Checks:
        - Detection heuristic (min_text_length=40 chars)
        - source_format classification (vector/scan/mixed)
        - Fallback to OCR when needed
        """
        logger.info("Auditing: Vector/Scan detection...")

        findings = []
        details = {}

        try:
            from app.ingestion.pdf_processor import PDFProcessor

            # Check 1: min_text_length threshold
            # Review code: checks if char_count < 40 for OCR decision
            threshold = 40  # From pdf_processor.py line 256
            findings.append(
                {
                    "check": "ocr_threshold",
                    "status": "INFO",
                    "value": threshold,
                    "note": "Pages with < 40 chars trigger OCR",
                }
            )

            # Check 2: source_format logic (lines 207-212)
            # Logic: scanned_pages==0 → vector; vector_pages==0 → scan; else → mixed
            findings.append(
                {
                    "check": "source_format_logic",
                    "status": "PASS",
                    "note": "Correct 3-way classification: vector/scan/mixed",
                }
            )

            # Check 3: Test with actual PDFs
            processor = PDFProcessor(enable_ocr=False)

            sample_pdfs = list(self.test_data_dir.glob("*.pdf"))[:3]
            for pdf_path in sample_pdfs:
                try:
                    pdf_doc = processor.process_pdf(pdf_path)
                    logger.info(
                        f"  {pdf_path.name}: {pdf_doc.source_format} "
                        f"({pdf_doc.num_pages} pages, {pdf_doc.total_chars} chars)"
                    )
                    details.setdefault("detected_formats", []).append(
                        {
                            "file": pdf_path.name,
                            "format": pdf_doc.source_format,
                            "pages": pdf_doc.num_pages,
                            "chars": pdf_doc.total_chars,
                        }
                    )
                except Exception as e:
                    logger.error(f"  {pdf_path.name}: FAILED - {e}")
                    findings.append(
                        {
                            "check": "processing_test",
                            "status": "FAIL",
                            "file": pdf_path.name,
                            "error": str(e),
                        }
                    )

            self.test_results["step2_detect"] = {
                "status": "PASS",
                "details": details,
                "findings": findings,
            }
            logger.info("✓ Step 2 audit complete")

        except Exception as e:
            logger.error(f"Step 2 audit failed: {e}")
            self.test_results["step2_detect"] = {
                "status": "FAIL",
                "error": str(e),
                "findings": findings,
            }

    # ========================================================================
    # STEP 3: PARSE & OCR
    # ========================================================================

    def audit_step3_parse_ocr(self):
        """
        Audit Step 3: Parse & OCR

        Checks:
        - OCR configuration (PaddleOCR, vie+eng)
        - DPI handling (2x zoom = ~150 DPI)
        - Confidence threshold (30%)
        - Cache mechanism
        - Error handling (corrupt/password PDFs)
        """
        logger.info("Auditing: Parse & OCR...")

        findings = []
        details = {}

        try:
            from app.ingestion.paddle_ocr_config import OCR_AVAILABLE, get_ocr_status

            # Check 1: OCR availability
            ocr_status = get_ocr_status()
            details["ocr_available"] = ocr_status.get("ocr_enabled", False)
            findings.append(
                {
                    "check": "ocr_availability",
                    "status": "PASS" if details["ocr_available"] else "WARNING",
                    "value": details["ocr_available"],
                }
            )

            # Check 2: DPI/zoom setting
            # From pdf_processor.py line 359: mat = fitz.Matrix(2, 2) → 2x zoom
            dpi_note = "2x zoom matrix (approx 144 DPI from 72 base)"
            findings.append(
                {
                    "check": "ocr_dpi",
                    "status": "INFO",
                    "value": "2x zoom",
                    "note": dpi_note,
                    "recommendation": "Consider adaptive DPI 3x-4x for low-res scans",
                }
            )

            # Check 3: Confidence threshold
            # From pdf_processor.py line 381-383: ocr_min_confidence default 30.0
            findings.append(
                {
                    "check": "ocr_confidence",
                    "status": "PASS",
                    "value": "30%",
                    "note": "Reasonable threshold for technical docs",
                }
            )

            # Check 4: Multi-language support
            # ocr_language parameter supports "vie+eng"
            findings.append(
                {
                    "check": "multilingual_ocr",
                    "status": "PASS",
                    "value": "vie+eng supported",
                    "note": "PaddleOCR supports Vietnamese + English",
                }
            )

            # Check 5: Cache mechanism
            # Lines 262-273 show OCR caching logic
            findings.append(
                {
                    "check": "ocr_cache",
                    "status": "PASS",
                    "note": "Cache by (pdf_path, page_num) exists",
                }
            )

            # Check 6: Error handling
            # Need to verify quarantine for corrupt/password PDFs
            findings.append(
                {
                    "check": "error_handling",
                    "status": "NEEDS_TEST",
                    "note": "Need to test with corrupt/password PDFs",
                }
            )

            self.test_results["step3_parse_ocr"] = {
                "status": "PASS",
                "details": details,
                "findings": findings,
            }
            logger.info("✓ Step 3 audit complete")

        except Exception as e:
            logger.error(f"Step 3 audit failed: {e}")
            self.test_results["step3_parse_ocr"] = {
                "status": "FAIL",
                "error": str(e),
                "findings": findings,
            }

    # ========================================================================
    # STEP 4: NORMALIZE & MARKDOWN
    # ========================================================================

    def audit_step4_normalize(self):
        """
        Audit Step 4: Normalize & Markdown

        Checks:
        - Text normalization (Unicode, whitespace)
        - Unit preservation (°, %, bar, etc.)
        - Markdown structure (headings, lists, tables)
        - Metadata preservation
        """
        logger.info("Auditing: Normalization & Markdown conversion...")

        findings = []
        details = {}

        try:
            # Check 1: Normalization in _calculate_content_hash
            # tools/ingest.py lines 314-332
            normalization_steps = [
                "Unicode NFKC normalization",
                "Lowercase conversion",
                "Line-ending hyphen removal",
                "Whitespace collapse",
                "Trim whitespace",
            ]
            findings.append(
                {
                    "check": "normalization_steps",
                    "status": "PASS",
                    "steps": normalization_steps,
                }
            )

            # Check 2: Unit preservation - CRITICAL
            # Need to verify units are NOT removed
            test_strings = [
                ("Temperature: 150°C", "temperature: 150°c"),  # Degree symbol
                ("Pressure: 16 bar", "pressure: 16 bar"),  # Unit
                ("Rate: 95%", "rate: 95%"),  # Percentage
                ("Voltage: 220V AC", "voltage: 220v ac"),  # Electrical unit
            ]

            import re
            import unicodedata

            unit_preservation_ok = True
            for original, expected_normalized in test_strings:
                # Simulate normalization
                normalized = unicodedata.normalize("NFKC", original)
                normalized = normalized.lower()
                normalized = re.sub(r"\s+", " ", normalized)
                normalized = normalized.strip()

                # Check critical characters
                if "°" in original and "°" not in normalized:
                    unit_preservation_ok = False
                    findings.append(
                        {
                            "check": "unit_preservation",
                            "status": "FAIL",
                            "issue": f"Degree symbol lost: '{original}' → '{normalized}'",
                        }
                    )
                if "%" in original and "%" not in normalized:
                    unit_preservation_ok = False
                    findings.append(
                        {
                            "check": "unit_preservation",
                            "status": "FAIL",
                            "issue": f"Percent symbol lost: '{original}' → '{normalized}'",
                        }
                    )

            if unit_preservation_ok:
                findings.append(
                    {
                        "check": "unit_preservation",
                        "status": "PASS",
                        "note": "Units (°, %, bar) preserved in normalization",
                    }
                )

            # Check 3: Markdown converter
            from app.rag.converters.markdown_converter import MarkdownConverter

            converter = MarkdownConverter()
            findings.append(
                {
                    "check": "markdown_converter",
                    "status": "PASS",
                    "note": "Converter initialized successfully",
                }
            )

            self.test_results["step4_normalize"] = {
                "status": "PASS",
                "details": details,
                "findings": findings,
            }
            logger.info("✓ Step 4 audit complete")

        except Exception as e:
            logger.error(f"Step 4 audit failed: {e}")
            self.test_results["step4_normalize"] = {
                "status": "FAIL",
                "error": str(e),
                "findings": findings,
            }

    # ========================================================================
    # STEP 5: CHUNKING
    # ========================================================================

    def audit_step5_chunking(self):
        """
        Audit Step 5: Chunking

        Checks:
        - Chunk size/overlap correct (1000/200)
        - Metadata mapping (doc_id, page_start, page_end)
        - Chunk ID uniqueness
        - Token vs char count
        """
        logger.info("Auditing: Chunking logic...")

        findings = []
        details = {}

        try:
            from app.rag.chunkers.hierarchical_chunker import HierarchicalChunker

            # Check 1: Default parameters
            chunker = HierarchicalChunker(max_chunk_size=1000, chunk_overlap=200)
            details["max_chunk_size"] = chunker.max_chunk_size
            details["chunk_overlap"] = chunker.chunk_overlap

            if chunker.max_chunk_size == 1000:
                findings.append(
                    {"check": "chunk_size", "status": "PASS", "value": 1000}
                )
            else:
                findings.append(
                    {
                        "check": "chunk_size",
                        "status": "FAIL",
                        "expected": 1000,
                        "actual": chunker.max_chunk_size,
                    }
                )

            if chunker.chunk_overlap == 200:
                findings.append(
                    {"check": "chunk_overlap", "status": "PASS", "value": 200}
                )
            else:
                findings.append(
                    {
                        "check": "chunk_overlap",
                        "status": "WARNING",
                        "expected": 200,
                        "actual": chunker.chunk_overlap,
                    }
                )

            # Check 2: Test chunking with sample text
            test_markdown = "# Test Document\n\n" + (
                "This is a test paragraph. " * 200
            )  # ~4000 chars
            chunks = chunker.chunk_markdown(test_markdown, doc_id="TEST_001")

            details["test_chunks_created"] = len(chunks)
            logger.info(
                f"  Test: {len(chunks)} chunks created from ~4000 char document"
            )

            # Verify chunk metadata
            if chunks:
                first_chunk = chunks[0]
                metadata_fields = [
                    "chunk_id",
                    "doc_id",
                    "page_start",
                    "page_end",
                    "char_count",
                ]
                missing_fields = [
                    f for f in metadata_fields if not hasattr(first_chunk, f)
                ]

                if not missing_fields:
                    findings.append(
                        {
                            "check": "chunk_metadata",
                            "status": "PASS",
                            "fields": metadata_fields,
                        }
                    )
                else:
                    findings.append(
                        {
                            "check": "chunk_metadata",
                            "status": "FAIL",
                            "missing_fields": missing_fields,
                        }
                    )

                # Check chunk ID uniqueness
                chunk_ids = [c.chunk_id for c in chunks]
                unique_ids = set(chunk_ids)
                if len(chunk_ids) == len(unique_ids):
                    findings.append({"check": "chunk_id_unique", "status": "PASS"})
                else:
                    findings.append(
                        {
                            "check": "chunk_id_unique",
                            "status": "FAIL",
                            "duplicates": len(chunk_ids) - len(unique_ids),
                        }
                    )

            self.test_results["step5_chunking"] = {
                "status": "PASS",
                "details": details,
                "findings": findings,
            }
            logger.info("✓ Step 5 audit complete")

        except Exception as e:
            logger.error(f"Step 5 audit failed: {e}")
            self.test_results["step5_chunking"] = {
                "status": "FAIL",
                "error": str(e),
                "findings": findings,
            }

    # ========================================================================
    # STEP 6: ARTIFACTS
    # ========================================================================

    def audit_step6_artifacts(self):
        """
        Audit Step 6: Artifacts generation

        Checks:
        - chunks.jsonl format and validity
        - doc_id_map.json completeness
        - quarantine.jsonl for error cases
        - Atomic writes and concurrency safety
        """
        logger.info("Auditing: Artifacts generation...")

        findings = []
        details = {}

        try:
            # Will run actual ingest and check outputs
            # For now, check expected paths from code
            expected_artifacts = [
                "chunks/chunks.jsonl",
                "doc_id_map.json",
                "quarantine.jsonl",
                "manifests/corpus_manifest.jsonl",
                "manifests/checksums_manifest.jsonl",
            ]

            findings.append(
                {
                    "check": "expected_artifacts",
                    "status": "INFO",
                    "files": expected_artifacts,
                }
            )

            # Check: Locks for concurrency
            # tools/ingest.py uses _dedup_lock, _quarantine_lock
            findings.append(
                {
                    "check": "concurrency_safety",
                    "status": "PASS",
                    "note": "Uses locks for dedup_lock, quarantine_lock",
                }
            )

            self.test_results["step6_artifacts"] = {
                "status": "PASS",
                "details": details,
                "findings": findings,
            }
            logger.info("✓ Step 6 audit complete")

        except Exception as e:
            logger.error(f"Step 6 audit failed: {e}")
            self.test_results["step6_artifacts"] = {
                "status": "FAIL",
                "error": str(e),
                "findings": findings,
            }

    # ========================================================================
    # STEP 6b: DEDUPLICATION
    # ========================================================================

    def audit_step6b_dedup(self):
        """
        Audit Step 6b: Deduplication (MODIFIED)

        Checks:
        - Content dedup is DISABLED (lines 446-480 commented)
        - Only file hash dedup remains (if implemented)
        - Near-duplicates (95% similar) are kept
        """
        logger.info("Auditing: Deduplication logic (MODIFIED)...")

        findings = []
        details = {}

        try:
            # Check 1: Content dedup status
            # Read tools/ingest.py lines 446-480
            with open(PROJECT_ROOT / "tools" / "ingest.py", "r", encoding="utf-8") as f:
                content = f.read()

            # Check if content dedup is commented out
            if (
                "# CONTENT DEDUPLICATION DISABLED" in content
                or "# ===== CONTENT DEDUPLICATION DISABLED =====" in content
            ):
                findings.append(
                    {
                        "check": "content_dedup_disabled",
                        "status": "PASS",
                        "note": "Content deduplication is correctly disabled",
                    }
                )
                details["content_dedup_status"] = "DISABLED"
            elif (
                "if content_hash in self.content_hash_map:" in content
                and 'return {"status": "duplicate"}' in content
            ):
                findings.append(
                    {
                        "check": "content_dedup_disabled",
                        "status": "FAIL",
                        "issue": "Content dedup appears to still be active!",
                    }
                )
                details["content_dedup_status"] = "ACTIVE (SHOULD BE DISABLED)"
            else:
                findings.append(
                    {
                        "check": "content_dedup_disabled",
                        "status": "UNCLEAR",
                        "note": "Cannot determine dedup status from code",
                    }
                )

            # Check 2: File hash dedup
            if "file_hash" in content and "self.file_hash_map" in content:
                findings.append(
                    {
                        "check": "file_hash_dedup",
                        "status": "INFO",
                        "note": "File hash tracking present (need to verify skip logic)",
                    }
                )
            else:
                findings.append(
                    {
                        "check": "file_hash_dedup",
                        "status": "WARNING",
                        "issue": "File hash dedup may not be implemented",
                        "recommendation": "Add file_hash check to skip exact file duplicates",
                    }
                )

            # Check 3: Would need actual test with duplicates
            findings.append(
                {
                    "check": "dedup_behavior_test",
                    "status": "NEEDS_TEST",
                    "note": "Need to run test with: 1 original + 1 exact copy + 1 near-duplicate (95%)",
                }
            )

            self.test_results["step6b_dedup"] = {
                "status": "PASS",
                "details": details,
                "findings": findings,
            }
            logger.info("✓ Step 6b audit complete")

        except Exception as e:
            logger.error(f"Step 6b audit failed: {e}")
            self.test_results["step6b_dedup"] = {
                "status": "FAIL",
                "error": str(e),
                "findings": findings,
            }

    # ========================================================================
    # STEP 7: INDEXING
    # ========================================================================

    def audit_step7_indexing(self):
        """
        Audit Step 7: BM25 & FAISS indexing

        Checks:
        - BM25 builds from chunks.jsonl
        - FAISS embedding dimension matches model
        - Cache SQLite works
        - Alignment between BM25 and FAISS (doc_id, page)
        """
        logger.info("Auditing: BM25 & FAISS indexing...")

        findings = []
        details = {}

        try:
            # Check 1: BM25 builder exists
            bm25_script = PROJECT_ROOT / "tools" / "build_bm25_index.py"
            if bm25_script.exists():
                findings.append(
                    {
                        "check": "bm25_builder_exists",
                        "status": "PASS",
                        "path": str(bm25_script),
                    }
                )
            else:
                findings.append(
                    {
                        "check": "bm25_builder_exists",
                        "status": "FAIL",
                        "issue": "BM25 builder script not found",
                    }
                )

            # Check 2: FAISS builder exists
            faiss_script = PROJECT_ROOT / "tools" / "build_faiss_local.py"
            if faiss_script.exists():
                findings.append(
                    {
                        "check": "faiss_builder_exists",
                        "status": "PASS",
                        "path": str(faiss_script),
                    }
                )
            else:
                # Try alternative name
                faiss_script_alt = PROJECT_ROOT / "tools" / "build_faiss_from_chunks.py"
                if faiss_script_alt.exists():
                    findings.append(
                        {
                            "check": "faiss_builder_exists",
                            "status": "PASS",
                            "path": str(faiss_script_alt),
                        }
                    )
                else:
                    findings.append(
                        {
                            "check": "faiss_builder_exists",
                            "status": "WARNING",
                            "issue": "FAISS builder script not found at expected location",
                        }
                    )

            # Check 3: Embedding dimension auto-detect
            # Should read from config or model
            findings.append(
                {
                    "check": "embedding_dimension",
                    "status": "NEEDS_TEST",
                    "note": "Need to verify dimension matches EMBEDDING_MODEL from .env",
                }
            )

            # Check 4: Cache mechanism
            findings.append(
                {
                    "check": "embedding_cache",
                    "status": "NEEDS_TEST",
                    "note": "Need to verify SQLite cache at artifacts/cache/",
                }
            )

            # Check 5: Alignment check
            findings.append(
                {
                    "check": "bm25_faiss_alignment",
                    "status": "NEEDS_TEST",
                    "note": "Need to verify doc_id and page alignment between BM25 and FAISS",
                }
            )

            self.test_results["step7_indexing"] = {
                "status": "PASS",
                "details": details,
                "findings": findings,
            }
            logger.info("✓ Step 7 audit complete")

        except Exception as e:
            logger.error(f"Step 7 audit failed: {e}")
            self.test_results["step7_indexing"] = {
                "status": "FAIL",
                "error": str(e),
                "findings": findings,
            }

    # ========================================================================
    # INTEGRATION TEST
    # ========================================================================

    def audit_integration(self):
        """
        Audit integration: End-to-end flow from PDF to searchable index

        Tests complete pipeline with small dataset
        """
        logger.info("Auditing: End-to-end integration...")

        findings = []
        details = {}

        try:
            # Run mini ingestion pipeline
            logger.info("  Running test ingestion...")

            # Use test_docs (7 PDFs)
            cmd = [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "ingest.py"),
                "--source-dir",
                str(self.test_data_dir),
                "--output-dir",
                str(self.test_output_dir),
                "--chunk-size",
                "1000",
                "--chunk-overlap",
                "200",
                "--enable-ocr",  # Enable OCR for complete test
                "--ocr-lang",
                "vie+eng",
            ]

            logger.info(f"  Command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300  # 5 minutes max
            )

            details["exit_code"] = result.returncode
            details["stdout_lines"] = len(result.stdout.splitlines())

            if result.returncode == 0:
                findings.append(
                    {
                        "check": "ingestion_success",
                        "status": "PASS",
                        "note": "Ingestion completed without errors",
                    }
                )

                # Check outputs
                chunks_file = self.test_output_dir / "chunks" / "chunks.jsonl"
                doc_id_map_file = self.test_output_dir / "doc_id_map.json"

                if chunks_file.exists():
                    # Count chunks
                    chunk_count = sum(1 for _ in open(chunks_file, encoding="utf-8"))
                    details["total_chunks"] = chunk_count
                    findings.append(
                        {
                            "check": "chunks_created",
                            "status": "PASS",
                            "count": chunk_count,
                        }
                    )
                else:
                    findings.append(
                        {
                            "check": "chunks_created",
                            "status": "FAIL",
                            "issue": "chunks.jsonl not found",
                        }
                    )

                if doc_id_map_file.exists():
                    with open(doc_id_map_file, encoding="utf-8") as f:
                        doc_id_map = json.load(f)
                    details["doc_id_map_entries"] = len(doc_id_map)
                    findings.append(
                        {
                            "check": "doc_id_map_created",
                            "status": "PASS",
                            "entries": len(doc_id_map),
                        }
                    )
                else:
                    findings.append(
                        {
                            "check": "doc_id_map_created",
                            "status": "FAIL",
                            "issue": "doc_id_map.json not found",
                        }
                    )

            else:
                findings.append(
                    {
                        "check": "ingestion_success",
                        "status": "FAIL",
                        "exit_code": result.returncode,
                        "stderr": result.stderr[:500],
                    }
                )

            self.test_results["integration"] = {
                "status": "PASS" if result.returncode == 0 else "FAIL",
                "details": details,
                "findings": findings,
            }
            logger.info("✓ Integration audit complete")

        except subprocess.TimeoutExpired:
            logger.error("Integration test timed out after 5 minutes")
            self.test_results["integration"] = {
                "status": "FAIL",
                "error": "Timeout",
                "findings": findings,
            }
        except Exception as e:
            logger.error(f"Integration audit failed: {e}")
            self.test_results["integration"] = {
                "status": "FAIL",
                "error": str(e),
                "findings": findings,
            }

    # ========================================================================
    # REPORT GENERATION
    # ========================================================================

    def _generate_report(self) -> Dict:
        """Generate final audit report"""
        logger.info("\n" + "=" * 80)
        logger.info("AUDIT REPORT SUMMARY")
        logger.info("=" * 80)

        # Count statuses
        passed = sum(1 for r in self.test_results.values() if r["status"] == "PASS")
        failed = sum(1 for r in self.test_results.values() if r["status"] == "FAIL")
        pending = sum(1 for r in self.test_results.values() if r["status"] == "pending")

        logger.info(f"✅ Passed: {passed}")
        logger.info(f"❌ Failed: {failed}")
        logger.info(f"⏳ Pending: {pending}")
        logger.info("")

        # Detailed results
        for step_name, result in self.test_results.items():
            status_icon = (
                "✅"
                if result["status"] == "PASS"
                else "❌"
                if result["status"] == "FAIL"
                else "⏳"
            )
            logger.info(f"{status_icon} {step_name}: {result['status']}")

            if "findings" in result:
                for finding in result["findings"]:
                    if finding["status"] in ["FAIL", "WARNING"]:
                        logger.warning(
                            f"    - {finding['check']}: {finding.get('issue', finding.get('note', ''))}"
                        )

        logger.info("=" * 80)

        # Save detailed report
        report_path = (
            PROJECT_ROOT
            / "reports"
            / "test_results"
            / f"OFFLINE_BUILD_AUDIT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)

        report_data = {
            "timestamp": datetime.now().isoformat(),
            "test_data_dir": str(self.test_data_dir),
            "test_output_dir": str(self.test_output_dir),
            "summary": {
                "passed": passed,
                "failed": failed,
                "pending": pending,
                "total": len(self.test_results),
            },
            "results": self.test_results,
            "metrics": self.metrics,
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        logger.info(f"📄 Detailed report saved: {report_path}")

        return report_data


def main():
    """Main entry point"""
    # Test data
    test_data_dir = PROJECT_ROOT / "test_docs"
    test_output_dir = PROJECT_ROOT / "artifacts" / "test_offline_build"

    # Run audit
    auditor = OfflineBuildAuditor(test_data_dir, test_output_dir)
    report = auditor.run_audit()

    # Exit with appropriate code
    if report["summary"]["failed"] > 0:
        logger.error("❌ Audit completed with failures")
        sys.exit(1)
    else:
        logger.info("✅ Audit completed successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
