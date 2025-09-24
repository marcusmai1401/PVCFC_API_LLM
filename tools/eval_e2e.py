#!/usr/bin/env python3
"""
Wrapper to run E2E-only batch evaluation.
"""
import subprocess
import sys


def main():
    args = (
        [
            sys.executable,
            "tools/run_evaluation.py",
        ]
        + sys.argv[1:]
        + ["--no-retrieval"]
    )

    # Default output dir to artifacts/eval if not provided
    if "--output-dir" not in " ".join(sys.argv):
        args += ["--output-dir", "artifacts/eval"]

    subprocess.run(args, check=True)


if __name__ == "__main__":
    main()
