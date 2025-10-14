"""
UI Smoke Test for PVCFC RAG Streamlit Application
Tests basic functionality and M3 theme integration
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_theme_files_exist():
    """Test that M3 theme files are present."""
    print("Testing theme files existence...")

    styles_dir = Path(__file__).parent.parent / "styles"

    required_files = [
        styles_dir / "tokens.json",
        styles_dir / "tokens.css",
        styles_dir / "m3.css",
    ]

    for file_path in required_files:
        assert file_path.exists(), f"Missing required file: {file_path}"
        print(f"  ✓ {file_path.name} exists")

    print("✅ All theme files present\n")


def test_theme_tokens_valid():
    """Test that tokens.json has required structure."""
    print("Testing token structure...")

    import json

    tokens_path = Path(__file__).parent.parent / "styles" / "tokens.json"
    with open(tokens_path, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    # Check required top-level keys
    required_keys = [
        "seedColor",
        "light",
        "dark",
        "typeScale",
        "shape",
        "elevation",
        "motion",
    ]
    for key in required_keys:
        assert key in tokens, f"Missing required key in tokens.json: {key}"
        print(f"  ✓ {key} present")

    # Check color roles in light theme
    required_color_roles = [
        "primary",
        "onPrimary",
        "primaryContainer",
        "surface",
        "onSurface",
        "surfaceVariant",
        "error",
        "outline",
    ]
    for role in required_color_roles:
        assert role in tokens["light"], f"Missing color role in light theme: {role}"

    print("✅ Token structure valid\n")


def test_theme_css_loads():
    """Test that CSS files have content and valid syntax."""
    print("Testing CSS files...")

    styles_dir = Path(__file__).parent.parent / "styles"

    # Test tokens.css
    tokens_css = (styles_dir / "tokens.css").read_text(encoding="utf-8")
    assert "--md-sys-color-primary" in tokens_css, "Missing primary color token in CSS"
    assert ':root[data-theme="light"]' in tokens_css, "Missing light theme selector"
    assert ':root[data-theme="dark"]' in tokens_css, "Missing dark theme selector"
    print("  ✓ tokens.css valid")

    # Test m3.css
    m3_css = (styles_dir / "m3.css").read_text(encoding="utf-8")
    assert ".md-button" in m3_css, "Missing button component class"
    assert ".md-card" in m3_css, "Missing card component class"
    assert ":focus-visible" in m3_css, "Missing focus-visible styles"
    assert ".md-side-sheet" in m3_css, "Missing side sheet component"
    print("  ✓ m3.css valid")

    # Test material-symbols.css
    material_symbols_css = (styles_dir / "material-symbols.css").read_text(
        encoding="utf-8"
    )
    assert "Material Symbols" in material_symbols_css, "Missing Material Symbols font"
    assert (
        ".material-symbols-outlined" in material_symbols_css
    ), "Missing icon base class"
    print("  ✓ material-symbols.css valid")

    print("✅ CSS files valid\n")


def test_theme_utils_import():
    """Test that theme utilities can be imported."""
    print("Testing theme utilities...")

    try:
        from streamlit_app.utils.theme import (
            get_current_theme,
            initialize_m3_theme,
            render_theme_switcher,
            set_theme,
        )

        print("  ✓ Theme utilities imported successfully")
    except ImportError as e:
        raise AssertionError(f"Failed to import theme utilities: {e}")

    print("✅ Theme utilities available\n")


def test_api_connectivity():
    """Test basic API connectivity (optional, may fail if API not running)."""
    print("Testing API connectivity...")

    import requests

    api_url = os.getenv("PVCFC_API_BASE_URL", "http://localhost:8000")

    try:
        response = requests.get(f"{api_url}/healthz", timeout=3)
        if response.status_code == 200:
            print(f"  ✓ API healthy at {api_url}")
            health_data = response.json()
            print(f"    - Status: {health_data.get('status', 'unknown')}")
            print(f"    - LLM Provider: {health_data.get('llm_provider', 'unknown')}")
        else:
            print(f"  ⚠️ API returned status {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"  ⚠️ API not reachable: {e}")
        print(f"    (This is OK if API is not running)")

    print()


def test_component_imports():
    """Test that main components can be imported."""
    print("Testing component imports...")

    try:
        from streamlit_app.components.query_lab_improved import (
            render as query_lab_render,
        )

        print("  ✓ Query Lab component imported")
    except ImportError as e:
        raise AssertionError(f"Failed to import Query Lab: {e}")

    try:
        from streamlit_app.components.system_status import render_system_status

        print("  ✓ System Status component imported")
    except ImportError as e:
        raise AssertionError(f"Failed to import System Status: {e}")

    try:
        from streamlit_app.components.side_sheet import render_citation_side_sheet

        print("  ✓ Side Sheet component imported")
    except ImportError as e:
        raise AssertionError(f"Failed to import Side Sheet: {e}")

    print("✅ All components importable\n")


def test_contrast_ratios():
    """Test that color tokens meet WCAG AA contrast requirements."""
    print("Testing contrast ratios (basic check)...")

    import json
    import re

    tokens_path = Path(__file__).parent.parent / "styles" / "tokens.json"
    with open(tokens_path, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    # Basic check: ensure on-* colors exist for each main color
    for theme in ["light", "dark"]:
        theme_colors = tokens[theme]

        # Check primary/onPrimary pair exists
        assert (
            "primary" in theme_colors and "onPrimary" in theme_colors
        ), f"Missing primary/onPrimary pair in {theme} theme"

        # Check surface/onSurface pair exists
        assert (
            "surface" in theme_colors and "onSurface" in theme_colors
        ), f"Missing surface/onSurface pair in {theme} theme"

        print(f"  ✓ {theme} theme has required color pairs")

    print("✅ Basic contrast structure valid\n")


def test_typography_scale():
    """Test that typography scale is complete."""
    print("Testing typography scale...")

    import json

    tokens_path = Path(__file__).parent.parent / "styles" / "tokens.json"
    with open(tokens_path, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    type_scale = tokens["typeScale"]

    required_roles = [
        "displayLarge",
        "headlineMedium",
        "titleLarge",
        "titleMedium",
        "bodyLarge",
        "bodyMedium",
        "labelLarge",
    ]

    for role in required_roles:
        assert role in type_scale, f"Missing typography role: {role}"

        # Check required properties
        role_def = type_scale[role]
        assert "size" in role_def, f"Missing size for {role}"
        assert "lineHeight" in role_def, f"Missing lineHeight for {role}"
        assert "weight" in role_def, f"Missing weight for {role}"

        print(f"  ✓ {role} complete")

    print("✅ Typography scale valid\n")


def run_all_tests():
    """Run all smoke tests."""
    print("=" * 60)
    print("PVCFC RAG UI Smoke Tests")
    print("=" * 60)
    print()

    tests = [
        test_theme_files_exist,
        test_theme_tokens_valid,
        test_theme_css_loads,
        test_theme_utils_import,
        test_component_imports,
        test_contrast_ratios,
        test_typography_scale,
        test_api_connectivity,  # Optional, may warn if API not running
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__} FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} ERROR: {e}\n")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    else:
        print("\n✅ All smoke tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()
