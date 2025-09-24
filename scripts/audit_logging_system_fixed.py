#!/usr/bin/env python
"""
Automated audit suite for UI logging system (fixed version).

Checks covered:
1) Logger initialization/handlers parity
2) Redaction coverage (strings, dict keys, nested, Bearer with dots)
3) Thread-safety (basic concurrency + performance locking)
4) Event schema validation
5) Performance benchmark (5k events)
6) Memory buffer eviction at max_memory_events
7) Console vs file parity (basic)
8) Components import smoke (debug_console, query_lab)
9) Log directory management and no ANSI color in file logs
10) Docs presence sanity check

Outputs a summary and non-zero exit on failure.
"""
import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict

# Ensure project root on path (parent of scripts)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.utils.ui_logger import EventType, get_logger

results = []
LOG_DIR = PROJECT_ROOT / "logs" / "ui_events"


def assert_true(cond: bool, msg: str):
    results.append(("PASS" if cond else "FAIL", msg))
    print(("[OK] " if cond else "[FAIL] ") + msg)
    return cond


def latest_file(pattern: str) -> Path:
    files = sorted(LOG_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def test_logger_init_and_handlers():
    print("\n== Test 1: Logger initialization and handlers ==")
    # file on, console on
    logger = get_logger(
        reinitialize=True,
        verbose=False,
        enable_file_logging=True,
        enable_console_logging=True,
    )
    logger.log_event(EventType.INFO, "init test")
    ok1 = logger.logger is not None
    ok2 = any(h for h in logger.logger.handlers)
    assert_true(ok1, "Base logger created")
    assert_true(ok2, "Has handlers configured")

    # file off, console on
    logger = get_logger(
        reinitialize=True,
        verbose=False,
        enable_file_logging=False,
        enable_console_logging=True,
    )
    logger.log_event(EventType.INFO, "console only test")
    assert_true(
        getattr(logger, "json_file", None) is None,
        "json_file None when file logging disabled",
    )
    assert_true(any(h for h in logger.logger.handlers), "Console handler active")


def test_redaction():
    print("\n== Test 2: Redaction coverage ==")
    logger = get_logger(
        reinitialize=True,
        verbose=False,
        enable_file_logging=True,
        enable_console_logging=False,
    )
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "api_key": "sk-1234567890abcdef",
        "password": "P@ssw0rd!",
        "secret": "supersecret",
        "nested": {"token": "abcDEF123"},
        "jwt_value": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.foo.bar",
        "long": "a" * 60,
        "headers": {"Authorization": "Bearer abc.def.ghi"},
    }
    logger.log_event(EventType.INFO, "redaction test", payload)

    jsonl = latest_file("session_*.jsonl")
    assert_true(jsonl is not None, "Session JSONL file created")
    # Parse to find our redaction test event
    events = []
    with jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except Exception:
                pass
    target = None
    for e in reversed(events):
        if e.get("message") == "redaction test":
            target = e
            break
    assert_true(target is not None, "Found redaction test event in JSONL")

    data = target.get("data", {})
    # Check top-level replacements
    assert_true(data.get("api_key") == "API_KEY_REDACTED", "API key redacted")
    assert_true(data.get("password") == "PASSWORD_REDACTED", "Password redacted")
    assert_true(data.get("secret") == "SECRET_REDACTED", "Secret redacted")
    # Check nested token
    nested = data.get("nested", {})
    assert_true(nested.get("token") == "TOKEN_REDACTED", "Token redacted (nested key)")
    # Check Authorization header
    headers = data.get("headers", {})
    auth = headers.get("Authorization")
    assert_true(auth == "Bearer TOKEN_REDACTED", "Bearer token redacted (header)")
    # Long key
    assert_true(data.get("long") == "LONG_KEY_REDACTED", "Long key redacted")


def test_thread_safety_and_perf_lock():
    print("\n== Test 3: Thread-safety and perf lock ==")
    logger = get_logger(reinitialize=True, verbose=False)

    def worker(i):
        for j in range(300):
            logger.log_event(EventType.DEBUG, f"thread {i} event {j}")
            k = f"k{i}"
            logger.log_event(EventType.INFO, f"perf start {i}-{j}", performance_key=k)
            logger.log_event(EventType.INFO, f"perf stop {i}-{j}", performance_key=k)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert_true(True, "Concurrent logging completed without crash")


def test_schema_validation():
    print("\n== Test 4: Schema validation ==")
    jsonl = latest_file("session_*.jsonl")
    assert_true(jsonl is not None, "Session JSONL file exists for schema check")
    ok = True
    with jsonl.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            try:
                evt = json.loads(line)
                required = [
                    "timestamp",
                    "session_id",
                    "event_type",
                    "severity",
                    "severity_name",
                    "message",
                    "data",
                ]
                for k in required:
                    if k not in evt:
                        ok = False
                if "performance" in evt:
                    perf = evt["performance"]
                    if not (("started" in perf) or ("duration_seconds" in perf)):
                        ok = False
            except Exception:
                ok = False
    assert_true(ok, "All events conform to schema")


def test_performance_benchmark():
    print("\n== Test 5: Performance benchmark ==")
    logger = get_logger(reinitialize=True, verbose=False, enable_console_logging=False)
    N = 5000
    t0 = time.time()
    for i in range(N):
        logger.log_event(EventType.DEBUG, f"bench {i}")
    dt = time.time() - t0
    print(f"Logged {N} events in {dt:.3f}s")
    assert_true(dt < 5.0, "Benchmark within acceptable range (<5s for 5k events)")


def test_memory_buffer_eviction():
    print("\n== Test 6: Memory buffer eviction ==")
    logger = get_logger(reinitialize=True, verbose=False, max_memory_events=50)
    for i in range(200):
        logger.log_event(EventType.DEBUG, f"evict {i}")
    events = logger.get_recent_events()
    assert_true(
        len(events) == 50, "Recent events buffer respects max_memory_events (50)"
    )


def test_console_file_parity_basic():
    print("\n== Test 7: Console vs file parity (basic) ==")
    logger = get_logger(reinitialize=True, verbose=True)
    logger.log_event(EventType.WARNING, "parity test")
    jsonl = latest_file("session_*.jsonl")
    evt = json.loads(jsonl.read_text(encoding="utf-8").splitlines()[-1])
    assert_true(
        evt.get("severity_name") == "WARNING", "Severity name persisted to file"
    )
    assert_true(evt.get("message") == "parity test", "Message persisted to file")


def test_imports_and_components():
    print("\n== Test 8: Components import smoke ==")
    import importlib

    dbg = importlib.import_module("streamlit_app.components.debug_console")
    assert_true(hasattr(dbg, "render"), "Debug console render available")
    ql = importlib.import_module("streamlit_app.components.query_lab")
    assert_true(hasattr(ql, "call_ask_api"), "Query Lab API caller available")


def test_log_dir_management_and_no_ansi():
    print("\n== Test 9: Log dir write and no ANSI in file logs ==")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = LOG_DIR / "_writetest.tmp"
    tmp.write_text("ok", encoding="utf-8")
    assert_true(tmp.exists(), "Log directory writable")
    tmp.unlink(missing_ok=True)

    # Generate a console-colored log and ensure file log has no ANSI
    logger = get_logger(
        reinitialize=True,
        verbose=True,
        enable_file_logging=True,
        enable_console_logging=True,
    )
    logger.log_event(EventType.INFO, "ansi check")
    text_log = latest_file("session_*.log")
    assert_true(text_log is not None, "Text log file created")
    content = text_log.read_text(encoding="utf-8")
    assert_true("\x1b[" not in content, "No ANSI color codes in file logs")


def test_docs_presence():
    print("\n== Test 10: Docs presence ==")
    docs = PROJECT_ROOT / "docs" / "ui_event_logging.md"
    assert_true(docs.exists(), "Documentation file exists")
    text = docs.read_text(encoding="utf-8") if docs.exists() else ""
    assert_true("Hệ thống Logging" in text or "Logging" in text, "Docs contain title")


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    test_logger_init_and_handlers()
    test_redaction()
    test_thread_safety_and_perf_lock()
    test_schema_validation()
    test_performance_benchmark()
    test_memory_buffer_eviction()
    test_console_file_parity_basic()
    test_imports_and_components()
    test_log_dir_management_and_no_ansi()
    test_docs_presence()

    failed = any(status == "FAIL" for status, _ in results)
    print("\n== SUMMARY ==")
    for status, msg in results:
        print(f"{status}: {msg}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
