#!/usr/bin/env python
"""
Monitor and manage API usage for Gemini/HyDE
Helps track free tier limits and optimize usage
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import yaml
from loguru import logger


class APIUsageMonitor:
    """Monitor API usage and enforce rate limits"""

    def __init__(self, config_path: str = "config/hyde_config.yaml"):
        """Initialize monitor with config"""
        self.config = self._load_config(config_path)
        self.usage_file = Path("logs/api_usage.json")
        self.usage_file.parent.mkdir(exist_ok=True)
        self.current_usage = self._load_usage()

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML"""
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def _load_usage(self) -> dict:
        """Load current usage stats"""
        if self.usage_file.exists():
            with open(self.usage_file, "r") as f:
                return json.load(f)
        return {
            "daily": {"date": str(datetime.now().date()), "requests": 0, "tokens": 0},
            "minute": {"timestamp": time.time(), "requests": 0, "tokens": 0},
            "total": {"requests": 0, "tokens": 0, "failures": 0},
        }

    def _save_usage(self):
        """Save usage stats to file"""
        with open(self.usage_file, "w") as f:
            json.dump(self.current_usage, f, indent=2)

    def can_make_request(self, estimated_tokens: int = 200) -> tuple[bool, str]:
        """
        Check if we can make a request within rate limits

        Returns:
            (can_request, reason_if_not)
        """
        tier = self.config["api"]["gemini"]["current_tier"]
        limits = self.config["api"]["gemini"]["rate_limit"][f"{tier}_tier"]

        # Check daily limit
        today = str(datetime.now().date())
        if self.current_usage["daily"]["date"] != today:
            # Reset daily counter
            self.current_usage["daily"] = {"date": today, "requests": 0, "tokens": 0}

        if self.current_usage["daily"]["requests"] >= limits["requests_per_day"]:
            return False, f"Daily limit reached ({limits['requests_per_day']} requests)"

        # Check minute limit
        current_minute = time.time() // 60
        last_minute = self.current_usage["minute"]["timestamp"] // 60

        if current_minute != last_minute:
            # Reset minute counter
            self.current_usage["minute"] = {
                "timestamp": time.time(),
                "requests": 0,
                "tokens": 0,
            }

        if self.current_usage["minute"]["requests"] >= limits["requests_per_minute"]:
            wait_time = 60 - (time.time() % 60)
            return False, f"Rate limit: wait {wait_time:.1f}s"

        # Check token limits
        if (
            self.current_usage["minute"]["tokens"] + estimated_tokens
            > limits["tokens_per_minute"]
        ):
            return False, "Token limit would be exceeded"

        return True, "OK"

    def record_request(self, tokens_used: int, success: bool = True):
        """Record API request"""
        self.current_usage["daily"]["requests"] += 1
        self.current_usage["daily"]["tokens"] += tokens_used
        self.current_usage["minute"]["requests"] += 1
        self.current_usage["minute"]["tokens"] += tokens_used
        self.current_usage["total"]["requests"] += 1
        self.current_usage["total"]["tokens"] += tokens_used

        if not success:
            self.current_usage["total"]["failures"] += 1

        self._save_usage()

    def get_usage_report(self) -> Dict:
        """Get current usage report"""
        tier = self.config["api"]["gemini"]["current_tier"]
        limits = self.config["api"]["gemini"]["rate_limit"][f"{tier}_tier"]

        daily_usage = self.current_usage["daily"]
        daily_percent = (daily_usage["requests"] / limits["requests_per_day"]) * 100

        return {
            "tier": tier,
            "daily": {
                "requests": f"{daily_usage['requests']}/{limits['requests_per_day']}",
                "percentage": f"{daily_percent:.1f}%",
                "tokens": daily_usage["tokens"],
            },
            "total": self.current_usage["total"],
            "recommendations": self._get_recommendations(daily_percent),
        }

    def _get_recommendations(self, daily_percent: float) -> list:
        """Get usage recommendations"""
        recommendations = []

        if daily_percent > 80:
            recommendations.append(
                "⚠️ Approaching daily limit - consider disabling HyDE"
            )

        if daily_percent > 50:
            recommendations.append("💡 Enable caching to reduce API calls")

        if (
            self.config["api"]["gemini"]["current_tier"] == "free"
            and daily_percent > 30
        ):
            recommendations.append("💰 Consider upgrading to paid tier for more quota")

        failure_rate = 0
        if self.current_usage["total"]["requests"] > 0:
            failure_rate = (
                self.current_usage["total"]["failures"]
                / self.current_usage["total"]["requests"]
            ) * 100

        if failure_rate > 20:
            recommendations.append("🔧 High failure rate - check API status")

        return recommendations


def print_usage_report():
    """Print current usage report"""
    monitor = APIUsageMonitor()
    report = monitor.get_usage_report()

    print("\n" + "=" * 50)
    print("API Usage Report")
    print("=" * 50)
    print(f"Tier: {report['tier'].upper()}")
    print(f"\nDaily Usage:")
    print(
        f"  Requests: {report['daily']['requests']} ({report['daily']['percentage']})"
    )
    print(f"  Tokens: {report['daily']['tokens']:,}")

    print(f"\nTotal Statistics:")
    print(f"  Total Requests: {report['total']['requests']:,}")
    print(f"  Total Tokens: {report['total']['tokens']:,}")
    print(f"  Failed Requests: {report['total']['failures']}")

    if report["recommendations"]:
        print(f"\nRecommendations:")
        for rec in report["recommendations"]:
            print(f"  {rec}")

    print("=" * 50)


def test_rate_limit():
    """Test if we can make a request"""
    monitor = APIUsageMonitor()
    can_request, reason = monitor.can_make_request()

    if can_request:
        print("✅ Can make request")
        # Simulate request
        monitor.record_request(tokens_used=150, success=True)
    else:
        print(f"❌ Cannot make request: {reason}")


def reset_daily_usage():
    """Reset daily usage counter (for testing)"""
    monitor = APIUsageMonitor()
    monitor.current_usage["daily"] = {
        "date": str(datetime.now().date()),
        "requests": 0,
        "tokens": 0,
    }
    monitor._save_usage()
    print("✅ Daily usage reset")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "report":
            print_usage_report()
        elif command == "test":
            test_rate_limit()
        elif command == "reset":
            reset_daily_usage()
        else:
            print("Usage: python monitor_api_usage.py [report|test|reset]")
    else:
        # Default: show report
        print_usage_report()
