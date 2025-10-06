================================================================================
  VISION CITATION FIXES - QUICK TEST GUIDE
================================================================================

📍 STEP-BY-STEP EXECUTION
────────────────────────────────────────────────────────────────────────────

1️⃣ Pre-Check
   □ Server running? → curl http://localhost:8000/health
   □ Config OK? → Select-String "VISION_PAGE_SELECTOR_ENABLED" .env

2️⃣ Run Test
   □ cd C:\Users\Admin\Desktop\Code - API_LLM_PVCFC
   □ python test_vision_citation_fixes.py

3️⃣ Collect Logs
   □ Test report: test_vision_fixes_report_TIMESTAMP.txt (auto-created)
   □ Server logs: Copy [DIAGNOSTIC] lines từ server console/log file

4️⃣ Send Results
   □ Paste test report vào chat
   □ Paste server diagnostic logs
   □ Note any errors/warnings

────────────────────────────────────────────────────────────────────────────

⚡ QUICK COMMANDS (Copy-Paste)
────────────────────────────────────────────────────────────────────────────

# Check server
curl http://localhost:8000/health

# Run test
cd C:\Users\Admin\Desktop\Code - API_LLM_PVCFC
python test_vision_citation_fixes.py

# Extract diagnostic logs (PowerShell)
Select-String "\[DIAGNOSTIC\]" logs\server.log -Context 1,1 | Out-File "diagnostic_extract.txt"

────────────────────────────────────────────────────────────────────────────

✅ SUCCESS INDICATORS
────────────────────────────────────────────────────────────────────────────

Console shows:
  ✓ Passed: 8/8 (hoặc 7/8)
  ✓ All tests have "Vision usage: True"
  ✓ P&ID tests show page ranges < 15
  ✓ No timeout errors

Server logs contain:
  ✓ "Vision strategy: ALWAYS ON (smart_vision_strategy disabled)"
  ✓ "[DIAGNOSTIC] P&ID override: center XX -> YY"
  ✓ "Enriched X/Y results with pdf_path"

────────────────────────────────────────────────────────────────────────────

⚠️ COMMON ISSUES
────────────────────────────────────────────────────────────────────────────

Problem: "Connection refused"
Fix: Start server first

Problem: "Timeout"
Fix: Check server not stuck, verify Vision can access PDFs

Problem: "Vision usage: False"
Fix: Check VISION_PAGE_SELECTOR_ENABLED=true in config

Problem: "ModuleNotFoundError: requests"
Fix: pip install requests

────────────────────────────────────────────────────────────────────────────

📊 WHAT TO SHARE
────────────────────────────────────────────────────────────────────────────

Priority 1 (Required):
  [✓] Test report file (test_vision_fixes_report_TIMESTAMP.txt)
  [✓] Server [DIAGNOSTIC] logs during test

Priority 2 (If failed):
  [ ] Full console output
  [ ] Server error logs
  [ ] Config (.env) relevant lines

────────────────────────────────────────────────────────────────────────────

🎯 EXPECTED DURATION
────────────────────────────────────────────────────────────────────────────

Normal: 20-40 seconds (8 tests, ~3-5s each)
With cache: 10-20 seconds
Timeout if: >120s per test (needs investigation)

────────────────────────────────────────────────────────────────────────────

💬 EXAMPLE RESULT MESSAGE
────────────────────────────────────────────────────────────────────────────

Tôi đã chạy xong test:

Results: 8/8 PASSED ✅
Duration: 32 seconds

Fix 1 (Vision Always ON): 3/3 ✅
Fix 2 (P&ID Pages): 2/2 ✅
Fix 3 (Rerank Safety): 2/2 ✅
Fix 4 (Metadata): 1/1 ✅

Key observations:
- Vision used in all tests
- P&ID pages rendered: 8-12 (good!)
- All tests have 3+ results
- No errors

[Attached: test_vision_fixes_report_20251004_103045.txt]
[Diagnostic logs: (paste key lines below)]

────────────────────────────────────────────────────────────────────────────

Need help? Read full guide: TEST_INSTRUCTIONS.md
================================================================================
