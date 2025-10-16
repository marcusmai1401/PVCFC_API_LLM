# P&ID Retrieval Enhancement - Quick Test Script
# Tests the enhancement with sample queries

Write-Host "=" -ForegroundColor Cyan -NoNewline; Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host "P&ID RETRIEVAL ENHANCEMENT - QUICK TEST" -ForegroundColor Cyan
Write-Host "=" -ForegroundColor Cyan -NoNewline; Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host ""

# Test queries
$testQueries = @(
    "E04217",
    "áp suất của E04217",
    "thông tin P04201A",
    "nhiệt độ reactor R04201"
)

Write-Host "Testing with sample queries:" -ForegroundColor Yellow
foreach ($query in $testQueries) {
    Write-Host "  - $query"
}
Write-Host ""

# Create test script
$testScript = @"
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.hybrid_weaviate_opensearch_retriever import HybridWeaviateOpenSearchRetriever
from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer

# Test queries
queries = [
    "E04217",
    "áp suất của E04217",
    "thông tin P04201A",
    "nhiệt độ reactor R04201"
]

retriever = HybridWeaviateOpenSearchRetriever()
enhancer = PIDQueryEnhancer()

print("=" * 80)
print("TESTING P&ID QUERY ENHANCEMENT")
print("=" * 80)
print()

for i, query in enumerate(queries, 1):
    print(f"[{i}/{len(queries)}] Query: {query}")

    # Enhance query
    enhanced = enhancer.enhance(query)
    print(f"  Strategy: {enhanced['strategy']}")

    if enhanced['strategy'] == 'tag_focused':
        print(f"  Tags: {enhanced['tags']}")
        print(f"  Type: {enhanced['query_type']}")

    # Retrieve
    try:
        results = retriever.retrieve_enhanced(
            query=query,
            top_k=5,
            enable_pid_enhancement=True
        )

        print(f"  Results: {len(results)}")

        if results:
            top = results[0]
            print(f"  Top result: {top.text[:100]}...")
            print(f"  Score: {top.score:.4f}, Source: {top.source}")
    except Exception as e:
        print(f"  Error: {e}")

    print()

print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
"@

# Save test script
$testScript | Out-File -FilePath "tests\quick_pid_test.py" -Encoding UTF8

# Run test
Write-Host "Running tests..." -ForegroundColor Yellow
Write-Host ""

python tests\quick_pid_test.py

Write-Host ""
Write-Host "=" -ForegroundColor Green -NoNewline; Write-Host ("=" * 79) -ForegroundColor Green
Write-Host "QUICK TEST COMPLETE" -ForegroundColor Green
Write-Host "=" -ForegroundColor Green -NoNewline; Write-Host ("=" * 79) -ForegroundColor Green
Write-Host ""
Write-Host "For full evaluation, run:" -ForegroundColor Cyan
Write-Host "  python tests\eval_pid_retrieval.py" -ForegroundColor White
Write-Host ""
