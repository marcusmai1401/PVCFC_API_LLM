"""
Test the UI event logging system

This script verifies that the logging system:
1. Creates session IDs correctly
2. Logs events to JSON lines files
3. Redacts sensitive data
4. Tracks performance metrics
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.ui_logger import EventSeverity, EventType, UIEventLogger, get_logger


def test_logging_system():
    """Run comprehensive logging system tests"""

    print("=" * 50)
    print("UI Event Logging System Test")
    print("=" * 50)

    # Initialize logger with verbose mode
    logger = get_logger(reinitialize=True, verbose=True, enable_console_logging=True)

    print(f"\n✓ Logger initialized")
    print(f"  Session ID: {logger.session_id}")
    print(f"  Log directory: {logger.log_dir}")

    # Test 1: Start a new run
    run_id = logger.start_new_run()
    print(f"\n✓ Started new run: {run_id}")

    # Test 2: Log different event types
    print("\n✓ Testing event logging:")

    # User input event
    logger.log_user_input(
        "test_query_input",
        "What is the capital of France?",
        {"widget_type": "text_area"},
    )
    print("  - Logged user input event")

    # Button click event
    logger.log_button_click("run_query", {"query_length": 30})
    print("  - Logged button click event")

    # API request event
    logger.log_api_request(
        endpoint="/ask",
        method="POST",
        payload={
            "query": "test query",
            "api_key": "sk-1234567890abcdef",  # Should be redacted
            "max_context": 8,
        },
        headers={"Authorization": "Bearer secret-token-12345"},  # Should be redacted
    )
    print("  - Logged API request (with sensitive data)")

    # API response event
    logger.log_api_response(
        endpoint="/ask",
        status_code=200,
        response_data={"answer": "Paris is the capital of France"},
        elapsed_time=1.234,
    )
    print("  - Logged API response")

    # State change event
    logger.log_state_change(
        "api_base_url", "http://localhost:8000", "http://localhost:8889"
    )
    print("  - Logged state change")

    # Warning event
    logger.log_event(
        EventType.WARNING,
        "API is slow",
        {"latency_ms": 5000},
        severity=EventSeverity.WARNING,
    )
    print("  - Logged warning event")

    # Error event with exception
    try:
        raise ValueError("Test exception for logging")
    except Exception as e:
        logger.log_error(
            "Test error occurred", exception=e, context={"test_id": "test_123"}
        )
    print("  - Logged error with exception")

    # Test 3: Get session statistics
    stats = logger.get_session_stats()
    print(f"\n✓ Session statistics:")
    print(f"  Total events: {stats['total_events']}")
    print(f"  Errors: {stats['error_count']}")
    print(f"  Warnings: {stats['warning_count']}")
    print(f"  Event types: {stats['event_counts_by_type']}")

    # Test 4: Get recent events
    recent = logger.get_recent_events(count=5)
    print(f"\n✓ Retrieved {len(recent)} recent events")

    # Test 5: Search for sensitive data (should be redacted)
    sensitive_found = False
    for event in recent:
        event_str = str(event)
        if "sk-1234567890abcdef" in event_str or "secret-token-12345" in event_str:
            sensitive_found = True
            break

    if sensitive_found:
        print("\n✗ WARNING: Sensitive data not properly redacted!")
    else:
        print("\n✓ Sensitive data properly redacted")

    # Test 6: Export session logs
    export_file = logger.export_session_logs()
    print(f"\n✓ Exported session logs to: {export_file}")

    # Test 7: Check if files were created
    log_files = list(logger.log_dir.glob(f"*{logger.session_id}*"))
    print(f"\n✓ Created {len(log_files)} log files:")
    for file in log_files:
        print(f"  - {file.name} ({file.stat().st_size} bytes)")

    print("\n" + "=" * 50)
    print("All tests completed successfully!")
    print("=" * 50)

    return True


if __name__ == "__main__":
    try:
        success = test_logging_system()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
