"""
UI Event Logger Module

Provides comprehensive event logging for the Streamlit UI with support for:
- Session and run IDs for correlation
- JSON lines file logging
- Terminal output with color coding
- Sensitive data redaction
- Event categorization and severity levels
"""

import hashlib
import json
import logging
import os
import re
import sys
import threading
import uuid
from collections import deque
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class EventType(Enum):
    """Event types for categorization"""

    USER_INPUT = "user_input"
    BUTTON_CLICK = "button_click"
    STATE_CHANGE = "state_change"
    API_REQUEST = "api_request"
    API_RESPONSE = "api_response"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"
    PERFORMANCE = "performance"
    SYSTEM = "system"


class EventSeverity(Enum):
    """Event severity levels"""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class UIEventLogger:
    """Comprehensive UI event logger with multiple output targets"""

    def __init__(
        self,
        log_dir: str = "logs/ui_events",
        enable_file_logging: bool = True,
        enable_console_logging: bool = True,
        max_memory_events: int = 1000,
        redact_sensitive: bool = True,
        verbose: bool = False,
    ):
        """
        Initialize the UI event logger

        Args:
            log_dir: Directory for log files
            enable_file_logging: Whether to write to JSON lines files
            enable_console_logging: Whether to output to console
            max_memory_events: Maximum events to keep in memory for UI display
            redact_sensitive: Whether to redact sensitive information
            verbose: Enable verbose logging
        """
        self.log_dir = Path(log_dir)
        self.enable_file_logging = enable_file_logging
        self.enable_console_logging = enable_console_logging
        self.max_memory_events = max_memory_events
        self.redact_sensitive = redact_sensitive
        self.verbose = verbose

        # Session management
        self.session_id = self._generate_session_id()
        self.run_id = None
        self.run_counter = 0

        # Memory buffer for recent events (thread-safe)
        self.recent_events = deque(maxlen=max_memory_events)
        self.events_lock = threading.Lock()
        self.file_lock = threading.Lock()

        # Setup logging infrastructure
        self._setup_logging()

        # Sensitive data patterns
        self.sensitive_patterns = [
            (r"(sk-[a-zA-Z0-9]+)", "API_KEY_REDACTED"),
            (r"Bearer\s+([a-zA-Z0-9\-\_\.]+)", "Bearer TOKEN_REDACTED"),
            (r'api[_-]?key["\']?\s*[:=]\s*["\']?([^"\'\s]+)', "API_KEY_REDACTED"),
            (r'token["\']?\s*[:=]\s*["\']?([^"\'\s]+)', "TOKEN_REDACTED"),
            (r'password["\']?\s*[:=]\s*["\']?([^"\'\s]+)', "PASSWORD_REDACTED"),
            (r'secret["\']?\s*[:=]\s*["\']?([^"\'\s]+)', "SECRET_REDACTED"),
            (r"([a-zA-Z0-9]{40,})", "LONG_KEY_REDACTED"),
        ]

        # Sensitive key names mapping for dict redaction (case-insensitive)
        self.sensitive_key_map = {
            "api_key": "API_KEY_REDACTED",
            "apikey": "API_KEY_REDACTED",
            "api-key": "API_KEY_REDACTED",
            "authorization": "TOKEN_REDACTED",
            "token": "TOKEN_REDACTED",
            "password": "PASSWORD_REDACTED",
            "secret": "SECRET_REDACTED",
            "key": "KEY_REDACTED",
        }

        # Performance metrics
        self.performance_metrics = {}
        self.performance_lock = threading.Lock()

        # Log initial session start
        self.log_event(
            EventType.SYSTEM,
            "Session started",
            {"session_id": self.session_id},
            severity=EventSeverity.INFO,
        )

    def _generate_session_id(self) -> str:
        """Generate a unique session ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"{timestamp}_{unique_id}"

    def _setup_logging(self):
        """Setup logging infrastructure"""
        # Always create base logger
        self.logger = logging.getLogger(f"UILogger_{self.session_id}")
        self.logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        self.logger.propagate = False  # Avoid duplicate logs to root logger

        # Remove existing handlers if reinitializing
        if self.logger.handlers:
            for h in list(self.logger.handlers):
                self.logger.removeHandler(h)
                try:
                    h.close()
                except Exception:
                    pass

        # Console handler (optional)
        if self.enable_console_logging:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG if self.verbose else logging.INFO)
            formatter = ColoredFormatter(
                "%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        # File handlers (optional)
        if self.enable_file_logging:
            # Create log directory if it doesn't exist
            self.log_dir.mkdir(parents=True, exist_ok=True)

            # JSON lines file for current session
            self.json_file = self.log_dir / f"session_{self.session_id}.jsonl"

            # Text log file handler
            file_handler = logging.FileHandler(
                self.log_dir / f"session_{self.session_id}.log", encoding="utf-8"
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        else:
            # If file logging disabled, ensure json_file attribute exists to avoid attribute errors
            self.json_file = None

    def start_new_run(self) -> str:
        """Start a new run within the session"""
        self.run_counter += 1
        self.run_id = f"run_{self.run_counter}_{uuid.uuid4().hex[:6]}"

        self.log_event(
            EventType.SYSTEM,
            "New run started",
            {"run_id": self.run_id, "run_number": self.run_counter},
            severity=EventSeverity.INFO,
        )

        return self.run_id

    def _redact_sensitive_data(self, data: Any) -> Any:
        """Redact sensitive information from data"""
        if not self.redact_sensitive:
            return data

        if isinstance(data, str):
            redacted = data
            for pattern, replacement in self.sensitive_patterns:
                redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
            return redacted
        elif isinstance(data, dict):
            redacted_dict = {}
            for k, v in data.items():
                try:
                    key_lower = str(k).lower()
                except Exception:
                    key_lower = str(k)
                if key_lower in getattr(self, "sensitive_key_map", {}):
                    # Special handling for Authorization: preserve scheme if present
                    if (
                        key_lower == "authorization"
                        and isinstance(v, str)
                        and re.match(r"\s*Bearer\s+", v, flags=re.IGNORECASE)
                    ):
                        redacted_dict[k] = "Bearer TOKEN_REDACTED"
                    else:
                        redacted_dict[k] = self.sensitive_key_map[key_lower]
                else:
                    redacted_dict[k] = self._redact_sensitive_data(v)
            return redacted_dict
        elif isinstance(data, list):
            return [self._redact_sensitive_data(item) for item in data]
        else:
            return data

    def log_event(
        self,
        event_type: EventType,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        severity: Optional[EventSeverity] = None,
        performance_key: Optional[str] = None,
    ):
        """
        Log a UI event

        Args:
            event_type: Type of event
            message: Event message
            data: Additional event data
            severity: Event severity level
            performance_key: Key for performance tracking
        """
        # Default severity based on event type if not provided
        if severity is None:
            severity = self._default_severity_for_event_type(event_type)

        # Create event record
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "run_id": self.run_id,
            "event_type": event_type.value,
            "severity": severity.value,
            "severity_name": severity.name,
            "message": message,
            "data": self._redact_sensitive_data(data) if data else {},
        }

        # Add performance timing if applicable
        if performance_key:
            with self.performance_lock:
                if performance_key in self.performance_metrics:
                    start_ts = self.performance_metrics[performance_key]
                    duration = datetime.now() - start_ts
                    event["performance"] = {
                        "key": performance_key,
                        "duration_seconds": duration.total_seconds(),
                    }
                    del self.performance_metrics[performance_key]
                else:
                    self.performance_metrics[performance_key] = datetime.now()
                    event["performance"] = {"key": performance_key, "started": True}

        # Add to memory buffer (thread-safe)
        with self.events_lock:
            self.recent_events.append(event)

        # Write to JSON lines file
        if self.enable_file_logging:
            try:
                with self.file_lock:
                    with open(self.json_file, "a", encoding="utf-8") as f:
                        json.dump(event, f, ensure_ascii=False)
                        f.write("\n")
                        f.flush()
            except Exception as e:
                print(f"Error writing to log file: {e}")

        # Log to console/traditional logger
        if self.enable_console_logging and self.logger:
            log_level = self._severity_to_log_level(severity)
            self.logger.log(
                log_level,
                f"[{event_type.value.upper()}] {message}",
                extra={"data": data} if self.verbose and data else {},
            )

    def _severity_to_log_level(self, severity: EventSeverity) -> int:
        """Convert EventSeverity to logging level"""
        mapping = {
            EventSeverity.DEBUG: logging.DEBUG,
            EventSeverity.INFO: logging.INFO,
            EventSeverity.WARNING: logging.WARNING,
            EventSeverity.ERROR: logging.ERROR,
            EventSeverity.CRITICAL: logging.CRITICAL,
        }
        return mapping.get(severity, logging.INFO)

    def _default_severity_for_event_type(self, event_type: EventType) -> EventSeverity:
        """Default severity derived from event type when not explicitly provided"""
        mapping = {
            EventType.ERROR: EventSeverity.ERROR,
            EventType.WARNING: EventSeverity.WARNING,
            EventType.DEBUG: EventSeverity.DEBUG,
        }
        return mapping.get(event_type, EventSeverity.INFO)

    def log_user_input(
        self, input_field: str, value: Any, metadata: Optional[Dict] = None
    ):
        """Log user input event"""
        data = {
            "field": input_field,
            "value": str(value)[:500],  # Truncate very long inputs
            "value_type": type(value).__name__,
        }
        if metadata:
            data.update(metadata)

        self.log_event(
            EventType.USER_INPUT,
            f"User input in {input_field}",
            data,
            severity=EventSeverity.INFO,
        )

    def log_button_click(self, button_name: str, metadata: Optional[Dict] = None):
        """Log button click event"""
        data = {"button": button_name}
        if metadata:
            data.update(metadata)

        self.log_event(
            EventType.BUTTON_CLICK,
            f"Button clicked: {button_name}",
            data,
            severity=EventSeverity.INFO,
        )

    def log_api_request(
        self, endpoint: str, method: str, payload: Dict, headers: Optional[Dict] = None
    ):
        """Log API request"""
        data = {
            "endpoint": endpoint,
            "method": method,
            "payload": payload,
            "headers": self._redact_sensitive_data(headers) if headers else {},
        }

        self.log_event(
            EventType.API_REQUEST,
            f"API request to {method} {endpoint}",
            data,
            severity=EventSeverity.INFO,
            performance_key=f"api_request_{endpoint}",
        )

    def log_api_response(
        self,
        endpoint: str,
        status_code: int,
        response_data: Any,
        elapsed_time: Optional[float] = None,
    ):
        """Log API response"""
        data = {
            "endpoint": endpoint,
            "status_code": status_code,
            "response": response_data
            if isinstance(response_data, (dict, list))
            else str(response_data)[:1000],
            "success": 200 <= status_code < 300,
        }

        if elapsed_time:
            data["elapsed_time_seconds"] = elapsed_time

        severity = EventSeverity.INFO if data["success"] else EventSeverity.WARNING

        self.log_event(
            EventType.API_RESPONSE,
            f"API response from {endpoint}: {status_code}",
            data,
            severity=severity,
            performance_key=f"api_request_{endpoint}",
        )

    def log_error(
        self,
        error_message: str,
        exception: Optional[Exception] = None,
        context: Optional[Dict] = None,
    ):
        """Log error event"""
        data = {"error_message": error_message, "context": context or {}}

        if exception:
            data["exception"] = {
                "type": type(exception).__name__,
                "message": str(exception),
                "traceback": self._get_traceback_string(exception),
            }

        self.log_event(
            EventType.ERROR, error_message, data, severity=EventSeverity.ERROR
        )

    def _get_traceback_string(self, exception: Exception) -> str:
        """Get traceback as string"""
        import traceback

        return "".join(
            traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        )

    def log_state_change(self, state_key: str, old_value: Any, new_value: Any):
        """Log state change event"""
        data = {
            "state_key": state_key,
            "old_value": str(old_value)[:500],
            "new_value": str(new_value)[:500],
            "changed": old_value != new_value,
        }

        self.log_event(
            EventType.STATE_CHANGE,
            f"State changed: {state_key}",
            data,
            severity=EventSeverity.DEBUG if self.verbose else EventSeverity.INFO,
        )

    def get_recent_events(
        self, count: Optional[int] = None, event_type: Optional[EventType] = None
    ) -> List[Dict]:
        """Get recent events from memory buffer"""
        with self.events_lock:
            events = list(self.recent_events)

        # Filter by event type if specified
        if event_type:
            events = [e for e in events if e.get("event_type") == event_type.value]

        # Limit count if specified
        if count:
            events = events[-count:]

        return events

    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        with self.events_lock:
            events = list(self.recent_events)

        stats = {
            "session_id": self.session_id,
            "current_run_id": self.run_id,
            "total_runs": self.run_counter,
            "total_events": len(events),
            "event_counts_by_type": {},
            "error_count": 0,
            "warning_count": 0,
        }

        for event in events:
            event_type = event.get("event_type", "unknown")
            stats["event_counts_by_type"][event_type] = (
                stats["event_counts_by_type"].get(event_type, 0) + 1
            )

            severity = event.get("severity_name", "")
            if severity == "ERROR" or severity == "CRITICAL":
                stats["error_count"] += 1
            elif severity == "WARNING":
                stats["warning_count"] += 1

        return stats

    def export_session_logs(self, output_file: Optional[str] = None) -> str:
        """Export session logs to a file"""
        if not output_file:
            output_file = (
                self.log_dir
                / f"export_{self.session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
        else:
            output_file = Path(output_file)

        with self.events_lock:
            events = list(self.recent_events)

        export_data = {
            "session_id": self.session_id,
            "export_timestamp": datetime.now().isoformat(),
            "total_events": len(events),
            "stats": self.get_session_stats(),
            "events": events,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        self.log_event(
            EventType.SYSTEM,
            f"Session logs exported to {output_file}",
            {"file": str(output_file)},
            severity=EventSeverity.INFO,
        )

        return str(output_file)


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output"""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        original_levelname = record.levelname
        try:
            if original_levelname in self.COLORS:
                colored = f"{self.COLORS[original_levelname]}{original_levelname}{self.COLORS['RESET']}"
                record.levelname = colored
            return super().format(record)
        finally:
            # Restore to avoid leaking ANSI into other handlers
            record.levelname = original_levelname


# Global logger instance (singleton pattern)
_logger_instance: Optional[UIEventLogger] = None


def get_logger(reinitialize: bool = False, **kwargs) -> UIEventLogger:
    """
    Get or create the global logger instance

    Args:
        reinitialize: Force reinitialize the logger
        **kwargs: Arguments to pass to UIEventLogger constructor

    Returns:
        UIEventLogger instance
    """
    global _logger_instance

    if _logger_instance is None or reinitialize:
        _logger_instance = UIEventLogger(**kwargs)

    return _logger_instance


def log_streamlit_widget(
    widget_type: str,
    widget_key: str,
    value: Any,
    logger: Optional[UIEventLogger] = None,
):
    """
    Helper function to log Streamlit widget interactions

    Args:
        widget_type: Type of Streamlit widget (e.g., 'text_input', 'button')
        widget_key: Key/label of the widget
        value: Current value or action
        logger: Logger instance (uses global if not provided)
    """
    if logger is None:
        logger = get_logger()

    if widget_type == "button" and value:
        logger.log_button_click(widget_key)
    else:
        logger.log_user_input(
            f"{widget_type}:{widget_key}", value, {"widget_type": widget_type}
        )
