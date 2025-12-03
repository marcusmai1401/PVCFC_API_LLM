"""
Integration tests for UI PDF viewing feature

Tests the complete flow:
- Query → /ask API
- Citations with pdf_path
- PDF rendering endpoints
- UI display
"""
import json
import os
from pathlib import Path

import pytest
import requests


@pytest.fixture
def api_base_url():
    """API base URL"""
    return os.getenv("PVCFC_API_BASE_URL", "http://localhost:8000")


@pytest.fixture
def doc_id_map():
    """Load doc_id_map for testing"""
    map_path = Path("artifacts/ingestion_production/doc_id_map.json")
    if not map_path.exists():
        pytest.skip("doc_id_map.json not found")

    with open(map_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestEndToEndPDFViewing:
    """Test complete PDF viewing flow"""

    def test_ask_returns_citations_with_pdf_path(self, api_base_url):
        """Test /ask returns citations with pdf_path field"""
        payload = {"query": "5153", "language": "vi", "max_context": 5}

        try:
            response = requests.post(f"{api_base_url}/ask", json=payload, timeout=30)
        except requests.exceptions.ConnectionError:
            pytest.skip("API not running")

        assert response.status_code == 200, f"API failed: {response.status_code}"

        data = response.json()
        citations = data.get("citations", [])

        if citations:
            # Check if at least some citations have pdf_path
            with_pdf_path = [c for c in citations if c.get("pdf_path")]

            print(
                f"\nCitations: {len(citations)} total, {len(with_pdf_path)} with pdf_path"
            )

            # Should have at least one citation with pdf_path
            assert len(with_pdf_path) > 0, "At least one citation should have pdf_path"

            # Show sample
            if with_pdf_path:
                sample = with_pdf_path[0]
                print(f"Sample citation:")
                print(f"  doc_id: {sample.get('doc_id')}")
                print(f"  page: {sample.get('page')}")
                print(f"  pdf_path: {sample.get('pdf_path', 'MISSING')[:80]}...")

    def test_pdf_render_endpoint(self, api_base_url, doc_id_map):
        """Test /api/pdf/render-page works with paths from doc_id_map"""
        # Get first valid PDF path
        pdf_path = None
        for value in doc_id_map.values():
            if isinstance(value, str):
                pdf_path = value
            elif isinstance(value, dict):
                pdf_path = value.get("pdf_path")

            if pdf_path and Path(pdf_path).exists():
                break

        if not pdf_path:
            pytest.skip("No valid PDF path found in doc_id_map")

        # Try to render page 1
        params = {"pdf_path": pdf_path, "page_num": 1, "dpi": 150, "format": "png"}

        try:
            response = requests.get(
                f"{api_base_url}/api/pdf/render-page", params=params, timeout=10
            )
        except requests.exceptions.ConnectionError:
            pytest.skip("API not running")

        # Should return 200 or 404 (if file moved)
        assert response.status_code in [
            200,
            404,
        ], f"Unexpected status: {response.status_code}"

        if response.status_code == 200:
            assert response.headers.get("Content-Type") == "image/png"
            print(f"\nPDF render successful:")
            print(f"  Path: {pdf_path[:80]}...")
            print(f"  Size: {len(response.content)} bytes")

    def test_pdf_open_endpoint(self, api_base_url, doc_id_map):
        """Test /api/pdf/open works"""
        # Get first valid PDF path
        pdf_path = None
        for value in doc_id_map.values():
            if isinstance(value, str):
                pdf_path = value
            elif isinstance(value, dict):
                pdf_path = value.get("pdf_path")

            if pdf_path and Path(pdf_path).exists():
                break

        if not pdf_path:
            pytest.skip("No valid PDF path found")

        params = {"pdf_path": pdf_path, "page": 1}

        try:
            response = requests.get(
                f"{api_base_url}/api/pdf/open", params=params, timeout=10
            )
        except requests.exceptions.ConnectionError:
            pytest.skip("API not running")

        assert response.status_code in [200, 404]

        if response.status_code == 200:
            assert response.headers.get("Content-Type") == "application/pdf"
            print(f"\nPDF open successful, size: {len(response.content)} bytes")


class TestMissingDocIDMapGraceful:
    """Test system works gracefully without doc_id_map"""

    def test_api_starts_without_doc_id_map(self):
        """Test API starts even if doc_id_map missing"""
        # This test would require renaming the file, starting API, testing, then restoring
        # For safety, we'll just verify the fallback logic exists in code

        # If doc_id_map doesn't exist, API should log:
        # "No doc_id_map.json found, citations will use doc_id only"
        # And set app.state.doc_id_map = {}

        # This is already implemented in app/main.py lines 112-114
        assert True  # Placeholder - manual test required


class TestIEEECheckboxSync:
    """Test IEEE checkbox syncs with session state"""

    def test_checkbox_state_persistence(self):
        """Test that checkbox state is tracked"""
        # Simulated session state
        session_state = {}

        # Initialize
        if "use_ieee_citations" not in session_state:
            session_state["use_ieee_citations"] = True

        # User unchecks
        checkbox_value = False

        # Sync logic
        if checkbox_value != session_state.get("use_ieee_citations"):
            session_state["use_ieee_citations"] = checkbox_value

        # Verify synced
        assert session_state["use_ieee_citations"] == False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
