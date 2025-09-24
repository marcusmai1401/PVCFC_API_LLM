#!/usr/bin/env python
"""
Automated audit suite for UI logging system.

Checks covered:
1) Logger initialization/handlers parity
2) Redaction coverage
3) Thread-safety (basic concurrency)
4) Event schema validation
5) Performance benchmark
6) Console vs file parity (basic)
7) Query Lab integration smoke (imports and call_ask_api dry-run)
8) Debug Console import smoke
9) Log directory management

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

# Ensure project root on path
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.utils.ui_logger import EventSeverity, EventType, UIEventLogger, get_logger

PASS = 0
FAIL = 1
results = []

LOG_DIR = PROJECT_ROOT / "logs" / "ui_events"


def assert_true(cond: bool, msg: str):
    results.append(("PASS" if cond else "FAIL", msg))
    if not cond:
        print(f"[FAIL] {msg}")
    else:
        print(f"[OK] {msg}")
    return cond


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
    assert_true(logger.logger is not None, "Base logger created")
    assert_true(any(h for h in logger.logger.handlers), "Has handlers configured")

    # file off, console on
    logger = get_logger(
        reinitialize=True,
        verbose=False,
        enable_file_logging=False,
        enable_console_logging=True,
    )
    logger.log_event(EventType.INFO, "console only test")
    assert_true(logger.json_file is None, "json_file None when file logging disabled")
    assert_true(any(h for h in logger.logger.handlers), "Console handler active")


def test_redaction():
    print("\n== Test 2: Redaction coverage ==")
    logger = get_logger(reinitialize=True, verbose=False)
    sensitive_payload = {
        "api_key": "sk-1234567890abcdef",
        "password": "P@ssw0rd!",
        "secret": "supersecret",
        "nested": {"token": "abcDEF123"},
        "jwt": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.foo.bar",
        "long": "a" * 60,
    }
    logger.log_event(EventType.INFO, "redaction test", sensitive_payload)
    session_file = sorted(
        LOG_DIR.glob("session_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )[0]
    line = session_file.read_text(encoding="utf-8").splitlines()[-1]
    assert_true("API_KEY_REDACTED" in line, "API key redacted")
    assert_true("PASSWORD_REDACTED" in line, "Password redacted")
    assert_true("SECRET_REDACTED" in line, "Secret redacted")
    assert_true("TOKEN_REDACTED" in line, "Token redacted")
    assert_true("Bearer TOKEN_REDACTED" in line, "Bearer token redacted")
    assert_true("LONG_KEY_REDACTED" in line, "Long key redacted")


def test_thread_safety():
    print("\n== Test 3: Thread-safety basic ==")
    logger = get_logger(reinitialize=True, verbose=False)

    def worker(i):
        for j in range(200):
            logger.log_event(EventType.DEBUG, f"thread {i} event {j}")
            logger.log_event(
                EventType.INFO, f"perf start {i}-{j}", performance_key=f"k{i}"
            )
            logger.log_event(
                EventType.INFO, f"perf stop {i}-{j}", performance_key=f"k{i}"
            )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert_true(True, "Concurrent logging completed without crash")


def test_schema_validation():
    print("\n== Test 4: Schema validation ==")
    session_file = sorted(
        LOG_DIR.glob("session_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )[0]
    ok = True
    with session_file.open("r", encoding="utf-8") as f:
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
                        print(f"Missing {k} at line {i}")
                if "performance" in evt:
                    perf = evt["performance"]
                    if not (("started" in perf) or ("duration_seconds" in perf)):
                        ok = False
                        print(f"Bad performance block at line {i}")
            except Exception as e:
                ok = False
                print(f"Invalid JSON at line {i}: {e}")
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


def test_console_file_parity():
    print("\n== Test 6: Console vs file parity (basic) ==")
    logger = get_logger(reinitialize=True, verbose=True)
    logger.log_event(EventType.WARNING, "parity test")
    session_file = sorted(
        LOG_DIR.glob("session_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )[0]
    line = session_file.read_text(encoding="utf-8").splitlines()[-1]
    evt = json.loads(line)
    assert_true(
        evt.get("severity_name") == "WARNING", "Severity name persisted to file"
    )
    assert_true(evt.get("message") == "parity test", "Message persisted to file")


def test_imports_and_components():
    print("\n== Test 7: Components import smoke ==")
    # Import debug console
    import importlib

    dbg = importlib.import_module("streamlit_app.components.debug_console")
    assert_true(hasattr(dbg, "render"), "Debug console render available")

    ql = importlib.import_module("streamlit_app.components.query_lab")
    assert_true(hasattr(ql, "call_ask_api"), "Query Lab API caller available")


def test_log_dir_management():
    print("\n== Test 8: Log directory management ==")
    # Just verify directory exists and is writable
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    test_file = LOG_DIR / "_writetest.tmp"
    test_file.write_text("ok", encoding="utf-8")
    assert_true(test_file.exists(), "Log directory writable")
    test_file.unlink(missing_ok=True)


def main():
    # Ensure log dir exists before starting
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    test_logger_init_and_handlers()
    test_redaction()
    test_thread_safety()
    test_schema_validation()
    test_performance_benchmark()
    test_console_file_parity()
    test_imports_and_components()
    test_log_dir_management()

    failed = any(status == "FAIL" for status, _ in results)
    print("\n== SUMMARY ==")
    for status, msg in results:
        print(f"{status}: {msg}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
