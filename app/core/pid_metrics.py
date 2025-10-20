"""
P&ID Query Metrics Collection
Tracks P&ID search usage, fallback rates, and performance
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger


@dataclass
class PIDQueryMetrics:
    """Metrics for a single P&ID query"""

    timestamp: str
    query: str
    strategy: str
    validation_confidence: float
    tags_found: int
    fallback_triggered: bool
    fallback_reason: Optional[str]
    execution_time_ms: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "timestamp": self.timestamp,
            "query": self.query[:100],  # Truncate for privacy
            "strategy": self.strategy,
            "validation_confidence": round(self.validation_confidence, 3),
            "tags_found": self.tags_found,
            "fallback_triggered": self.fallback_triggered,
            "fallback_reason": self.fallback_reason,
            "execution_time_ms": round(self.execution_time_ms, 2),
        }


# In-memory metrics storage (last 1000 queries)
_metrics: List[PIDQueryMetrics] = []
_MAX_METRICS = 1000


def log_pid_query(metrics: PIDQueryMetrics):
    """
    Log P&ID query metrics

    Args:
        metrics: PIDQueryMetrics instance

    Side effects:
        - Adds to in-memory collection
        - Writes to logs/pid_queries.jsonl
    """
    global _metrics

    # Add to in-memory (with limit)
    _metrics.append(metrics)
    if len(_metrics) > _MAX_METRICS:
        _metrics = _metrics[-_MAX_METRICS:]  # Keep last 1000

    # Write to file for persistent analysis
    try:
        log_file = Path("logs/pid_queries.jsonl")
        log_file.parent.mkdir(exist_ok=True, parents=True)

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(metrics.to_dict(), ensure_ascii=False) + "\n")

    except Exception as e:
        logger.warning(f"Failed to write P&ID metrics to file: {e}")


def log_pid_decision(query: str, decision: str, reason: str, details: dict = None):
    """
    Log P&ID routing decisions for debugging

    Args:
        query: Original query (truncated for logs)
        decision: "use_pid", "use_semantic", "fallback"
        reason: Reason for decision
        details: Additional context (optional)

    Example:
        >>> log_pid_decision("5153", "use_pid", "Pure digits", {"confidence": 0.9})
        # Logs: [PID_ROUTING] use_pid: Pure digits
    """
    log_entry = {
        "query": query[:100],
        "decision": decision,
        "reason": reason,
        "details": details or {},
    }

    logger.info(f"[PID_ROUTING] {decision}: {reason}")
    logger.debug(f"[PID_ROUTING] Details: {log_entry}")


def get_pid_metrics_summary() -> Dict:
    """
    Get summary statistics of P&ID query metrics

    Returns:
        Dictionary with:
        - total_pid_queries: Total queries logged
        - by_strategy: Count by strategy type
        - fallback_rate: Percentage of fallbacks
        - avg_confidence: Average validation confidence
        - avg_execution_time_ms: Average execution time

    Example:
        >>> summary = get_pid_metrics_summary()
        >>> print(summary["fallback_rate"])
        0.05  # 5% fallback rate
    """
    if not _metrics:
        return {
            "total_pid_queries": 0,
            "by_strategy": {},
            "fallback_rate": 0.0,
            "avg_confidence": 0.0,
            "avg_execution_time_ms": 0.0,
        }

    total = len(_metrics)
    by_strategy = {}
    fallback_count = 0
    total_confidence = 0.0
    total_time = 0.0

    for m in _metrics:
        # Count by strategy
        by_strategy[m.strategy] = by_strategy.get(m.strategy, 0) + 1

        # Count fallbacks
        if m.fallback_triggered:
            fallback_count += 1

        # Sum for averages
        total_confidence += m.validation_confidence
        total_time += m.execution_time_ms

    return {
        "total_pid_queries": total,
        "by_strategy": by_strategy,
        "fallback_rate": round(fallback_count / total, 3) if total > 0 else 0.0,
        "avg_confidence": round(total_confidence / total, 3) if total > 0 else 0.0,
        "avg_execution_time_ms": round(total_time / total, 2) if total > 0 else 0.0,
        "recent_queries": [m.to_dict() for m in _metrics[-10:]],  # Last 10
    }


def get_pid_metrics_detailed() -> List[Dict]:
    """
    Get detailed metrics for all queries

    Returns:
        List of all metric dicts
    """
    return [m.to_dict() for m in _metrics]


def clear_pid_metrics():
    """Clear in-memory metrics (for testing)"""
    global _metrics
    _metrics = []
    logger.info("P&ID metrics cleared")


__all__ = [
    "PIDQueryMetrics",
    "log_pid_query",
    "log_pid_decision",
    "get_pid_metrics_summary",
    "get_pid_metrics_detailed",
    "clear_pid_metrics",
]
