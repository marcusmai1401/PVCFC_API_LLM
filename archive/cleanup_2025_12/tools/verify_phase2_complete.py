#!/usr/bin/env python3
"""
Comprehensive verification script for Phase 2 completion
"""

import importlib
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple


class Status(Enum):
    PASS = "✅"
    FAIL = "❌"
    WARN = "⚠️"
    INFO = "ℹ️"


@dataclass
class CheckResult:
    name: str
    status: Status
    message: str
    details: List[str] = None


def check_directory_structure() -> List[CheckResult]:
    """Check if all required directories exist"""
    results = []

    required_dirs = [
        "app/rag",
        "app/routers",
        "app/ingestion",
        "app/utils",
        "artifacts/bm25",
        "artifacts/faiss",
        "artifacts/chunks",
        "tools",
        "tests",
    ]

    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            results.append(
                CheckResult(
                    name=f"Directory: {dir_path}", status=Status.PASS, message="Exists"
                )
            )
        else:
            results.append(
                CheckResult(
                    name=f"Directory: {dir_path}", status=Status.FAIL, message="Missing"
                )
            )

    return results


def check_core_modules() -> List[CheckResult]:
    """Check if core RAG modules exist and can be imported"""
    results = []

    modules = [
        ("app.rag.retriever", "HybridRetriever"),
        ("app.rag.generator", "ResponseGenerator"),
        ("app.rag.embedder", "TextEmbedder"),
        ("app.rag.hyde", "HyDEGenerator"),
        ("app.rag.cove", "ChainOfVerification"),
        ("app.rag.schemas", "AskRequest"),
        ("app.ingestion.pdf_processor", "PDFProcessor"),
        ("app.ingestion.text_chunker", "SemanticChunker"),
    ]

    for module_path, class_name in modules:
        try:
            module = importlib.import_module(module_path)
            if hasattr(module, class_name):
                results.append(
                    CheckResult(
                        name=f"{module_path}.{class_name}",
                        status=Status.PASS,
                        message="Importable",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name=f"{module_path}.{class_name}",
                        status=Status.FAIL,
                        message=f"Class {class_name} not found",
                    )
                )
        except ImportError as e:
            results.append(
                CheckResult(
                    name=f"{module_path}.{class_name}",
                    status=Status.FAIL,
                    message=f"Import error: {str(e)}",
                )
            )

    return results


def check_api_routers() -> List[CheckResult]:
    """Check if API routers exist and are properly configured"""
    results = []

    routers = [
        ("app.routers.ask", "router"),
        ("app.routers.locate", "router"),
        ("app.routers.report", "router"),
    ]

    for module_path, router_name in routers:
        try:
            module = importlib.import_module(module_path)
            if hasattr(module, router_name):
                results.append(
                    CheckResult(
                        name=f"{module_path}.{router_name}",
                        status=Status.PASS,
                        message="Router found",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name=f"{module_path}.{router_name}",
                        status=Status.FAIL,
                        message="Router not found",
                    )
                )
        except ImportError as e:
            results.append(
                CheckResult(
                    name=f"{module_path}.{router_name}",
                    status=Status.FAIL,
                    message=f"Import error: {str(e)}",
                )
            )

    return results


def check_dependencies_module() -> List[CheckResult]:
    """Check dependencies module"""
    results = []

    try:
        from app.dependencies import (
            check_dependencies_health,
            get_cove,
            get_embedder,
            get_generator,
            get_retriever,
            initialize_indices,
        )

        results.append(
            CheckResult(
                name="app.dependencies",
                status=Status.PASS,
                message="All dependency functions available",
            )
        )
    except ImportError as e:
        results.append(
            CheckResult(
                name="app.dependencies",
                status=Status.FAIL,
                message=f"Import error: {str(e)}",
            )
        )

    return results


def check_utilities() -> List[CheckResult]:
    """Check utility modules"""
    results = []

    utilities = [
        ("app.utils.text_utils", ["clean_text", "normalize_text"]),
        ("app.utils.file_utils", ["ensure_directory", "load_json"]),
        ("app.utils.metrics", ["track_request_metrics", "get_metrics_summary"]),
        ("app.utils.tracing", ["trace_request", "get_trace_summary"]),
    ]

    for module_path, functions in utilities:
        try:
            module = importlib.import_module(module_path)
            missing = [f for f in functions if not hasattr(module, f)]

            if not missing:
                results.append(
                    CheckResult(
                        name=module_path,
                        status=Status.PASS,
                        message="All functions available",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name=module_path,
                        status=Status.WARN,
                        message=f"Missing functions: {missing}",
                    )
                )
        except ImportError as e:
            results.append(
                CheckResult(
                    name=module_path,
                    status=Status.FAIL,
                    message=f"Import error: {str(e)}",
                )
            )

    return results


def check_index_artifacts() -> List[CheckResult]:
    """Check if index artifacts exist"""
    results = []

    artifacts = [
        ("artifacts/bm25/index.pkl", "BM25 index"),
        ("artifacts/faiss/index.bin", "FAISS index"),
        ("artifacts/chunks", "Chunks directory"),
    ]

    for path, name in artifacts:
        if os.path.exists(path):
            if os.path.isfile(path):
                size = os.path.getsize(path) / 1024  # KB
                results.append(
                    CheckResult(
                        name=name, status=Status.PASS, message=f"Exists ({size:.1f} KB)"
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name=name, status=Status.PASS, message="Directory exists"
                    )
                )
        else:
            results.append(
                CheckResult(
                    name=name, status=Status.WARN, message="Not found (build required)"
                )
            )

    return results


def check_tests() -> List[CheckResult]:
    """Check if tests exist"""
    results = []

    test_files = [
        "tools/test_pdf_processor.py",
        "tools/test_chunker.py",
        "tools/test_bm25_index.py",
        "tools/test_faiss_index.py",
    ]

    for test_file in test_files:
        if os.path.exists(test_file):
            results.append(
                CheckResult(
                    name=f"Test: {os.path.basename(test_file)}",
                    status=Status.PASS,
                    message="Exists",
                )
            )
        else:
            results.append(
                CheckResult(
                    name=f"Test: {os.path.basename(test_file)}",
                    status=Status.WARN,
                    message="Missing",
                )
            )

    return results


def check_main_app() -> List[CheckResult]:
    """Check main app configuration"""
    results = []

    try:
        # Check if main.py includes new routers
        with open("app/main.py", "r") as f:
            content = f.read()

        checks = [
            ("ask.router" in content, "Ask router mounted"),
            ("locate.router" in content, "Locate router mounted"),
            ("report.router" in content, "Report router mounted"),
            ("initialize_indices" in content, "Index initialization"),
            ("cleanup_dependencies" in content, "Cleanup on shutdown"),
        ]

        for check, desc in checks:
            if check:
                results.append(
                    CheckResult(name=desc, status=Status.PASS, message="Configured")
                )
            else:
                results.append(
                    CheckResult(name=desc, status=Status.FAIL, message="Not configured")
                )

    except Exception as e:
        results.append(
            CheckResult(
                name="app/main.py",
                status=Status.FAIL,
                message=f"Error checking: {str(e)}",
            )
        )

    return results


def print_results(category: str, results: List[CheckResult]):
    """Print results in a formatted way"""
    print(f"\n{'='*60}")
    print(f"  {category}")
    print(f"{'='*60}")

    for result in results:
        print(f"{result.status.value} {result.name}: {result.message}")
        if result.details:
            for detail in result.details:
                print(f"    - {detail}")


def main():
    """Run all checks"""
    print("\n" + "=" * 60)
    print("  PHASE 2 COMPREHENSIVE VERIFICATION")
    print("=" * 60)

    all_results = []

    # Run all checks
    categories = [
        ("Directory Structure", check_directory_structure()),
        ("Core RAG Modules", check_core_modules()),
        ("API Routers", check_api_routers()),
        ("Dependencies Module", check_dependencies_module()),
        ("Utility Modules", check_utilities()),
        ("Index Artifacts", check_index_artifacts()),
        ("Test Files", check_tests()),
        ("Main App Configuration", check_main_app()),
    ]

    for category, results in categories:
        print_results(category, results)
        all_results.extend(results)

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)

    pass_count = sum(1 for r in all_results if r.status == Status.PASS)
    fail_count = sum(1 for r in all_results if r.status == Status.FAIL)
    warn_count = sum(1 for r in all_results if r.status == Status.WARN)

    total = len(all_results)
    pass_rate = (pass_count / total * 100) if total > 0 else 0

    print(f"Total checks: {total}")
    print(f"✅ Passed: {pass_count} ({pass_rate:.1f}%)")
    print(f"❌ Failed: {fail_count}")
    print(f"⚠️ Warnings: {warn_count}")

    if fail_count == 0:
        print("\n🎉 PHASE 2 IS COMPLETE! All core components are in place.")
        if warn_count > 0:
            print(
                "⚠️ Some warnings exist (mostly missing test files or unbuilt indices)"
            )
            print("   These can be addressed as needed.")
    else:
        print(f"\n❌ PHASE 2 INCOMPLETE: {fail_count} critical issues found.")
        print("   Please fix the failed checks before proceeding.")
        return 1

    return 0


if __name__ == "__main__":
    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    sys.exit(main())
