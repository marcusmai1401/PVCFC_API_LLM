#!/usr/bin/env python3
"""Debug script to test Vietnamese query handling"""

import json
import sys

import requests
from rich import print as rprint


def test_vietnamese_query():
    """Test Vietnamese query with detailed debugging"""

    # API endpoint
    base_url = "http://localhost:8000"

    # Check if API is running
    try:
        health_response = requests.get(f"{base_url}/healthz")
        if health_response.status_code != 200:
            rprint("[red]❌ API is not healthy[/red]")
            return
    except requests.exceptions.ConnectionError:
        rprint("[red]❌ Cannot connect to API at http://localhost:8000[/red]")
        return

    rprint("[green]✓ API is running[/green]")

    # Test query in Vietnamese
    query_vi = "Áp suất vận hành của KT06101 là bao nhiêu?"

    # Prepare request
    request_data = {
        "query": query_vi,
        "language": "vi",
        "max_context": 5,
        "temperature": 0.3,
        "hyde": True,
        "filters": None,
        "execution_mode": "light_only",
    }

    rprint("\n[cyan]Sending Vietnamese query:[/cyan]")
    rprint(f"Query: {query_vi}")
    rprint(f"Request data: {json.dumps(request_data, indent=2, ensure_ascii=False)}")

    # Send request
    response = requests.post(f"{base_url}/ask", json=request_data)

    if response.status_code != 200:
        rprint(f"[red]❌ API returned error: {response.status_code}[/red]")
        rprint(response.text)
        return

    # Parse response
    result = response.json()

    rprint("\n[cyan]Response received:[/cyan]")
    rprint(f"Status: {result.get('status', 'unknown')}")
    rprint(f"Answer length: {len(result.get('answer', ''))}")
    rprint(f"Citations count: {len(result.get('citations', []))}")
    rprint(f"Context used count: {len(result.get('context_used', []))}")
    rprint(f"Confidence: {result.get('confidence', 0)}")

    # Show answer
    rprint("\n[cyan]Answer:[/cyan]")
    rprint(result.get("answer", "No answer"))

    # Show citations
    if result.get("citations"):
        rprint("\n[cyan]Citations:[/cyan]")
        for i, citation in enumerate(result["citations"], 1):
            rprint(
                f"  {i}. Doc: {citation.get('doc_id', 'unknown')}, Page: {citation.get('page', 'N/A')}"
            )
    else:
        rprint("\n[yellow]⚠️ No citations found[/yellow]")

    # Show context used
    if result.get("context_used"):
        rprint(f"\n[cyan]Context chunks used: {len(result['context_used'])}[/cyan]")
        for i, ctx_id in enumerate(result["context_used"][:3], 1):
            rprint(f"  {i}. {ctx_id}")

    # Show warnings
    if result.get("warnings"):
        rprint("\n[yellow]Warnings:[/yellow]")
        for warning in result["warnings"]:
            rprint(f"  - {warning}")

    # Now test the same query in English
    rprint("\n" + "=" * 60)
    query_en = "What is the operating pressure of KT06101?"

    request_data_en = {
        "query": query_en,
        "language": "en",
        "max_context": 5,
        "temperature": 0.3,
        "hyde": True,
        "filters": None,
        "execution_mode": "light_only",
    }

    rprint("\n[cyan]Sending English query for comparison:[/cyan]")
    rprint(f"Query: {query_en}")

    response_en = requests.post(f"{base_url}/ask", json=request_data_en)

    if response_en.status_code == 200:
        result_en = response_en.json()
        rprint(f"Answer length: {len(result_en.get('answer', ''))}")
        rprint(f"Citations count: {len(result_en.get('citations', []))}")
        rprint(f"Context used count: {len(result_en.get('context_used', []))}")

        if result_en.get("citations"):
            rprint("\n[cyan]Citations (English query):[/cyan]")
            for i, citation in enumerate(result_en["citations"], 1):
                rprint(
                    f"  {i}. Doc: {citation.get('doc_id', 'unknown')}, Page: {citation.get('page', 'N/A')}"
                )


if __name__ == "__main__":
    test_vietnamese_query()
