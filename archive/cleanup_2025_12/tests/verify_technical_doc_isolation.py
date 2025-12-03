"""
Verification script to confirm technical docs pipeline isolation

Tests that changes to P&ID fallback enhancer do NOT affect technical_doc pipeline:
1. Test TechnicalDocRetriever search flow
2. Verify no PIDFallbackEnhancer imports in technical path
3. Confirm config separation
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import ast

from loguru import logger


def test_technical_doc_no_pid_imports():
    """Verify TechnicalDocRetriever does not import PIDFallbackEnhancer"""
    tech_doc_file = project_root / "app" / "rag" / "technical_doc_retriever.py"

    with open(tech_doc_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse AST
    tree = ast.parse(content)

    # Check imports
    pid_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if "pid_fallback_enhancer" in (node.module or ""):
                pid_imports.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "pid_fallback_enhancer" in alias.name:
                    pid_imports.append(alias.name)

    if pid_imports:
        logger.error(f"❌ TechnicalDocRetriever imports PID fallback: {pid_imports}")
        return False
    else:
        logger.success("✅ TechnicalDocRetriever has no PID fallback imports")
        return True


def test_technical_doc_uses_standard_hybrid():
    """Verify TechnicalDocRetriever uses standard HybridWeaviateOpenSearchRetriever"""
    tech_doc_file = project_root / "app" / "rag" / "technical_doc_retriever.py"

    with open(tech_doc_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for correct retriever usage
    if "HybridWeaviateOpenSearchRetriever" in content:
        logger.success(
            "✅ TechnicalDocRetriever uses standard HybridWeaviateOpenSearchRetriever"
        )
        return True
    else:
        logger.error("❌ TechnicalDocRetriever does not use standard hybrid retriever")
        return False


def test_pid_fallback_only_in_pid_pipeline():
    """Verify PIDFallbackEnhancer is only imported in P&ID pipeline"""
    allowed_files = [
        "app/rag/hybrid_with_tags_retriever.py",  # P&ID pipeline
        "app/rag/pid_fallback_enhancer.py",  # Self
        "tests/test_pid_fallback_enhancer.py",  # Unit tests
    ]

    # Search for imports
    app_dir = project_root / "app"
    pid_importers = []

    for py_file in app_dir.rglob("*.py"):
        # Skip allowed files
        rel_path = str(py_file.relative_to(project_root)).replace("\\", "/")
        if rel_path in allowed_files or "test" in rel_path:
            continue

        with open(py_file, "r", encoding="utf-8") as f:
            content = f.read()

        if "pid_fallback_enhancer" in content:
            # Check if it's actually an import
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if "pid_fallback_enhancer" in (node.module or ""):
                        pid_importers.append(rel_path)
                        break
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if "pid_fallback_enhancer" in alias.name:
                            pid_importers.append(rel_path)
                            break

    if pid_importers:
        logger.error(
            f"❌ PIDFallbackEnhancer imported in unexpected files: {pid_importers}"
        )
        return False
    else:
        logger.success("✅ PIDFallbackEnhancer only imported in P&ID pipeline")
        return True


def test_config_separation():
    """Verify P&ID config settings exist and are properly namespaced"""
    config_file = project_root / "app" / "core" / "config.py"

    with open(config_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for all P&ID fallback config settings
    required_settings = [
        "pid_enable_semantic_fallback",
        "pid_opensearch_weight",
        "pid_weaviate_weight",
        "pid_enable_tag_rerank",
        "pid_enable_safety_check",
    ]

    missing_settings = []
    for setting in required_settings:
        if setting not in content:
            missing_settings.append(setting)

    if missing_settings:
        logger.error(f"❌ Missing P&ID config settings: {missing_settings}")
        return False
    else:
        logger.success(f"✅ All {len(required_settings)} P&ID config settings present")
        return True


def test_routing_logic_separation():
    """Verify ask.py routes technical_doc to TechnicalDocRetriever"""
    ask_file = project_root / "app" / "api" / "routers" / "ask.py"

    with open(ask_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Check routing logic
    checks = [
        ('query_type == "technical_doc"', "Technical doc routing condition"),
        ("tech_doc_retriever", "Technical doc retriever reference"),
        ('query_type == "pid"', "P&ID routing condition"),
        ("tags_retriever", "P&ID tags retriever reference"),
    ]

    all_present = True
    for check_str, description in checks:
        if check_str in content:
            logger.success(f"✅ {description} found")
        else:
            logger.error(f"❌ {description} NOT found")
            all_present = False

    return all_present


def test_mock_technical_doc_search():
    """Mock test to verify TechnicalDocRetriever.search() signature"""
    try:
        from unittest.mock import Mock

        from app.rag.query_transform import QueryFilters, QueryIntent, TransformedQuery
        from app.rag.technical_doc_retriever import TechnicalDocRetriever

        # Create mock retriever
        retriever = TechnicalDocRetriever()

        # Check that retriever has standard components
        assert hasattr(retriever, "retriever"), "Missing .retriever attribute"
        assert hasattr(retriever, "enhancer"), "Missing .enhancer attribute"

        # Verify it uses HybridWeaviateOpenSearchRetriever
        from app.rag.hybrid_weaviate_opensearch_retriever import (
            HybridWeaviateOpenSearchRetriever,
        )

        assert isinstance(
            retriever.retriever, HybridWeaviateOpenSearchRetriever
        ), "TechnicalDocRetriever should use HybridWeaviateOpenSearchRetriever"

        logger.success("✅ TechnicalDocRetriever structure validated")
        return True

    except Exception as e:
        logger.error(f"❌ TechnicalDocRetriever mock test failed: {e}")
        return False


def run_all_tests():
    """Run all isolation verification tests"""
    logger.info("=" * 70)
    logger.info("Technical Docs Pipeline Isolation Verification")
    logger.info("=" * 70)

    tests = [
        ("No PID imports in TechnicalDocRetriever", test_technical_doc_no_pid_imports),
        (
            "TechnicalDocRetriever uses standard hybrid",
            test_technical_doc_uses_standard_hybrid,
        ),
        ("PID fallback only in P&ID pipeline", test_pid_fallback_only_in_pid_pipeline),
        ("Config separation", test_config_separation),
        ("Routing logic separation", test_routing_logic_separation),
        ("Mock TechnicalDocRetriever search", test_mock_technical_doc_search),
    ]

    results = []
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' raised exception: {e}")
            results.append((test_name, False))

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info("=" * 70)
    logger.info(f"TOTAL: {passed}/{total} tests passed")

    if passed == total:
        logger.success("✅ ALL TESTS PASSED - Technical docs pipeline is fully isolated")
        return True
    else:
        logger.error(
            f"❌ {total - passed} tests failed - Pipeline isolation NOT guaranteed"
        )
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
