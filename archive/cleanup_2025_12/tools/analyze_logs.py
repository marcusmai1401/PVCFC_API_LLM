#!/usr/bin/env python3
"""
Analyze logs and generate metrics report.
Extracts key metrics from request logs and generates a dashboard report.
"""
import argparse
import json

# Add project root to path
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)


class LogAnalyzer:
    """Analyze RAG pipeline logs."""

    def __init__(self, log_file: Path):
        """Initialize analyzer with log file."""
        self.log_file = log_file
        self.logs = []
        self.load_logs()

    def load_logs(self):
        """Load logs from JSONL file."""
        if not self.log_file.exists():
            print(f"Log file not found: {self.log_file}")
            return

        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    log = json.loads(line.strip())
                    self.logs.append(log)
                except json.JSONDecodeError:
                    continue

        print(f"Loaded {len(self.logs)} log entries")

    def filter_by_time(self, hours: int = 24) -> List[Dict]:
        """Filter logs by time window."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        filtered = []

        for log in self.logs:
            timestamp_str = log.get("timestamp", log.get("time", ""))
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(
                        timestamp_str.replace("Z", "+00:00")
                    )
                    if timestamp > cutoff:
                        filtered.append(log)
                except:
                    # If parsing fails, include the log anyway for testing
                    filtered.append(log)
            else:
                # No timestamp, include for testing
                filtered.append(log)

        return filtered

    def analyze_latency(self, logs: List[Dict]) -> Dict[str, Any]:
        """Analyze latency metrics."""
        latencies = []
        step_latencies = defaultdict(list)

        for log in logs:
            # Extract total latency
            if "latency_ms" in log:
                latencies.append(log["latency_ms"])

            # Extract timing breakdown
            timing = log.get("timing_breakdown", {})
            for step, duration in timing.items():
                step_latencies[step].append(duration)

        if not latencies:
            return {"error": "No latency data found"}

        # Calculate percentiles
        latencies.sort()

        def percentile(data, p):
            if not data:
                return 0
            k = (len(data) - 1) * p
            f = int(k)
            c = f + 1 if f < len(data) - 1 else f
            return data[f] if k == f else data[f] * (c - k) + data[c] * (k - f)

        # Calculate step breakdown
        step_stats = {}
        for step, durations in step_latencies.items():
            if durations:
                step_stats[step] = {
                    "mean": round(statistics.mean(durations), 2),
                    "median": round(statistics.median(durations), 2),
                    "p95": round(percentile(sorted(durations), 0.95), 2),
                    "count": len(durations),
                }

        return {
            "total": {
                "count": len(latencies),
                "mean": round(statistics.mean(latencies), 2),
                "median": round(statistics.median(latencies), 2),
                "p50": round(percentile(latencies, 0.5), 2),
                "p75": round(percentile(latencies, 0.75), 2),
                "p90": round(percentile(latencies, 0.9), 2),
                "p95": round(percentile(latencies, 0.95), 2),
                "p99": round(percentile(latencies, 0.99), 2),
                "min": round(min(latencies), 2),
                "max": round(max(latencies), 2),
            },
            "step_breakdown": step_stats,
        }

    def analyze_errors(self, logs: List[Dict]) -> Dict[str, Any]:
        """Analyze error metrics."""
        errors = []
        error_types = Counter()
        error_endpoints = Counter()

        for log in logs:
            if log.get("event_type") == "request_error" or log.get("error"):
                errors.append(log)
                error_types[log.get("error_type", "unknown")] += 1
                error_endpoints[log.get("endpoint", "unknown")] += 1

        total_requests = len(
            [
                l
                for l in logs
                if l.get("event_type") in ["request_complete", "request_error"]
            ]
        )
        error_rate = (len(errors) / total_requests * 100) if total_requests > 0 else 0

        return {
            "total_errors": len(errors),
            "error_rate": round(error_rate, 2),
            "by_type": dict(error_types.most_common(10)),
            "by_endpoint": dict(error_endpoints.most_common(10)),
        }

    def analyze_cache(self, logs: List[Dict]) -> Dict[str, Any]:
        """Analyze cache metrics."""
        cache_hits = 0
        cache_misses = 0

        for log in logs:
            message = log.get("message", "")
            if "cache hit" in message.lower():
                cache_hits += 1
            elif "cache miss" in message.lower():
                cache_misses += 1

        total_cache_ops = cache_hits + cache_misses
        hit_rate = (cache_hits / total_cache_ops * 100) if total_cache_ops > 0 else 0

        return {
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "hit_rate": round(hit_rate, 2),
            "total_operations": total_cache_ops,
        }

    def analyze_citations(self, logs: List[Dict]) -> Dict[str, Any]:
        """Analyze citation metrics."""
        citation_counts = []
        requests_with_citations = 0
        total_requests = 0

        for log in logs:
            if log.get("event_type") == "request_complete":
                total_requests += 1
                citations_count = log.get("citations_count", 0)
                citation_counts.append(citations_count)
                if citations_count > 0:
                    requests_with_citations += 1

        if not citation_counts:
            return {"error": "No citation data found"}

        citation_rate = (
            (requests_with_citations / total_requests * 100)
            if total_requests > 0
            else 0
        )

        return {
            "citation_rate": round(citation_rate, 2),
            "avg_citations_per_answer": round(statistics.mean(citation_counts), 2),
            "median_citations": statistics.median(citation_counts),
            "max_citations": max(citation_counts),
            "min_citations": min(citation_counts),
            "requests_with_citations": requests_with_citations,
            "total_requests": total_requests,
        }

    def analyze_endpoints(self, logs: List[Dict]) -> Dict[str, Any]:
        """Analyze metrics by endpoint."""
        endpoint_stats = defaultdict(
            lambda: {"count": 0, "errors": 0, "latencies": [], "citations": []}
        )

        for log in logs:
            endpoint = log.get("endpoint", "unknown")
            if endpoint == "unknown":
                continue

            stats = endpoint_stats[endpoint]

            if log.get("event_type") == "request_complete":
                stats["count"] += 1
                if "latency_ms" in log:
                    stats["latencies"].append(log["latency_ms"])
                if "citations_count" in log:
                    stats["citations"].append(log["citations_count"])
            elif log.get("event_type") == "request_error":
                stats["errors"] += 1

        # Calculate aggregates
        result = {}
        for endpoint, stats in endpoint_stats.items():
            result[endpoint] = {
                "count": stats["count"],
                "errors": stats["errors"],
                "error_rate": round(
                    (stats["errors"] / (stats["count"] + stats["errors"]) * 100)
                    if (stats["count"] + stats["errors"]) > 0
                    else 0,
                    2,
                ),
            }

            if stats["latencies"]:
                result[endpoint]["latency_p50"] = round(
                    statistics.median(stats["latencies"]), 2
                )
                result[endpoint]["latency_p95"] = (
                    round(statistics.quantiles(stats["latencies"], n=20)[18], 2)
                    if len(stats["latencies"]) > 1
                    else stats["latencies"][0]
                )

            if stats["citations"]:
                result[endpoint]["avg_citations"] = round(
                    statistics.mean(stats["citations"]), 2
                )

        return result

    def generate_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate comprehensive metrics report."""
        # Filter logs by time window
        filtered_logs = self.filter_by_time(hours)

        print(f"\nAnalyzing {len(filtered_logs)} logs from last {hours} hours...")

        report = {
            "summary": {
                "time_window_hours": hours,
                "total_logs": len(filtered_logs),
                "report_generated": datetime.utcnow().isoformat(),
            },
            "latency": self.analyze_latency(filtered_logs),
            "errors": self.analyze_errors(filtered_logs),
            "cache": self.analyze_cache(filtered_logs),
            "citations": self.analyze_citations(filtered_logs),
            "endpoints": self.analyze_endpoints(filtered_logs),
        }

        return report

    def print_report(self, report: Dict[str, Any]):
        """Print formatted report to console."""
        print("\n" + "=" * 80)
        print("RAG PIPELINE METRICS REPORT")
        print("=" * 80)

        # Summary
        print(f"\nTime Window: {report['summary']['time_window_hours']} hours")
        print(f"Total Logs: {report['summary']['total_logs']}")
        print(f"Generated: {report['summary']['report_generated']}")

        # Latency
        print("\n" + "-" * 40)
        print("LATENCY METRICS (ms)")
        print("-" * 40)
        if "error" not in report["latency"]:
            lat = report["latency"]["total"]
            print(f"Requests: {lat['count']}")
            print(f"Mean: {lat['mean']} | Median: {lat['median']}")
            print(
                f"P50: {lat['p50']} | P75: {lat['p75']} | P90: {lat['p90']} | P95: {lat['p95']} | P99: {lat['p99']}"
            )
            print(f"Min: {lat['min']} | Max: {lat['max']}")

            if report["latency"]["step_breakdown"]:
                print("\nStep Breakdown:")
                for step, stats in report["latency"]["step_breakdown"].items():
                    print(f"  {step}: mean={stats['mean']}ms, p95={stats['p95']}ms")
        else:
            print(report["latency"]["error"])

        # Errors
        print("\n" + "-" * 40)
        print("ERROR METRICS")
        print("-" * 40)
        err = report["errors"]
        print(f"Total Errors: {err['total_errors']}")
        print(f"Error Rate: {err['error_rate']}%")
        if err["by_type"]:
            print("By Type:")
            for error_type, count in list(err["by_type"].items())[:5]:
                print(f"  {error_type}: {count}")

        # Cache
        print("\n" + "-" * 40)
        print("CACHE METRICS")
        print("-" * 40)
        cache = report["cache"]
        print(f"Hit Rate: {cache['hit_rate']}%")
        print(f"Hits: {cache['cache_hits']} | Misses: {cache['cache_misses']}")

        # Citations
        print("\n" + "-" * 40)
        print("CITATION METRICS")
        print("-" * 40)
        if "error" not in report["citations"]:
            cit = report["citations"]
            print(f"Citation Rate: {cit['citation_rate']}%")
            print(f"Avg Citations/Answer: {cit['avg_citations_per_answer']}")
            print(
                f"Median: {cit['median_citations']} | Range: {cit['min_citations']}-{cit['max_citations']}"
            )
        else:
            print(report["citations"]["error"])

        # Endpoints
        print("\n" + "-" * 40)
        print("ENDPOINT METRICS")
        print("-" * 40)
        for endpoint, stats in report["endpoints"].items():
            print(f"\n{endpoint}:")
            print(
                f"  Requests: {stats['count']} | Errors: {stats['errors']} ({stats['error_rate']}%)"
            )
            if "latency_p50" in stats:
                print(
                    f"  Latency: p50={stats['latency_p50']}ms, p95={stats['latency_p95']}ms"
                )
            if "avg_citations" in stats:
                print(f"  Avg Citations: {stats['avg_citations']}")

        print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Analyze RAG pipeline logs")
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("logs/requests.jsonl"),
        help="Path to log file (default: logs/requests.jsonl)",
    )
    parser.add_argument(
        "--hours", type=int, default=24, help="Time window in hours (default: 24)"
    )
    parser.add_argument("--output", type=Path, help="Output file for JSON report")
    parser.add_argument(
        "--metrics-file",
        type=Path,
        default=Path("logs/metrics.jsonl"),
        help="Additional metrics log file",
    )

    args = parser.parse_args()

    # Analyze main request logs
    analyzer = LogAnalyzer(args.log_file)
    report = analyzer.generate_report(hours=args.hours)

    # Print report to console
    analyzer.print_report(report)

    # Save JSON report if requested
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to: {args.output}")

    # Also analyze metrics logs if available
    if args.metrics_file.exists():
        print(f"\n\nAnalyzing metrics logs from: {args.metrics_file}")
        metrics_analyzer = LogAnalyzer(args.metrics_file)
        metrics_report = metrics_analyzer.generate_report(hours=args.hours)

        # Save metrics report
        if args.output:
            metrics_output = args.output.with_suffix(".metrics.json")
            with open(metrics_output, "w", encoding="utf-8") as f:
                json.dump(metrics_report, f, indent=2)
            print(f"Metrics report saved to: {metrics_output}")


if __name__ == "__main__":
    main()
