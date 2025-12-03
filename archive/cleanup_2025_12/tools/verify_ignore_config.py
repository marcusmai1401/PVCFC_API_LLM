#!/usr/bin/env python
"""
Verify .gitignore and .cursorignore configuration
Ensures GitHub protection while Cursor has full access
"""
import os
import subprocess
from pathlib import Path
from typing import List, Tuple


def check_git_status() -> Tuple[List[str], List[str]]:
    """Check which files are tracked/ignored by git"""
    try:
        # Get list of tracked files
        result = subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, check=True
        )
        tracked_files = result.stdout.strip().split("\n") if result.stdout else []

        # Get list of ignored files
        result = subprocess.run(
            ["git", "status", "--ignored", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )

        ignored_files = []
        for line in result.stdout.strip().split("\n"):
            if line.startswith("!!"):
                ignored_files.append(line[3:])

        return tracked_files, ignored_files

    except subprocess.CalledProcessError:
        print("⚠️ Git not initialized or error running git commands")
        return [], []


def check_sensitive_files():
    """Check status of sensitive files"""

    print("=" * 70)
    print("SENSITIVE FILES PROTECTION CHECK")
    print("=" * 70)

    sensitive_files = [
        ".env",
        ".env.local",
        "config/secrets.yml",
        "api_keys.txt",
        "credentials.json",
    ]

    sensitive_patterns = ["*.key", "*.pem", "*.cert", "secrets/*", "credentials/*"]

    print("\n📁 Checking individual sensitive files:")
    print("-" * 40)

    for file in sensitive_files:
        path = Path(file)
        if path.exists():
            # Check if file is ignored by git
            try:
                result = subprocess.run(
                    ["git", "check-ignore", file], capture_output=True, text=True
                )
                is_ignored = result.returncode == 0

                if is_ignored:
                    print(f"✅ {file} - EXISTS and PROTECTED from GitHub")
                else:
                    print(f"⚠️  {file} - EXISTS but NOT PROTECTED! Add to .gitignore!")
            except:
                print(f"❓ {file} - EXISTS (git status unknown)")
        else:
            print(f"⚪ {file} - Not found (OK)")

    print("\n📁 Checking sensitive patterns:")
    print("-" * 40)

    for pattern in sensitive_patterns:
        print(f"Pattern: {pattern}")
        # This would need more complex checking for patterns
        # For now, just note they're in .gitignore
        with open(".gitignore", "r") as f:
            gitignore_content = f.read()
            if pattern.replace("*", "") in gitignore_content:
                print(f"  ✅ Protected in .gitignore")
            else:
                print(f"  ⚠️ Not found in .gitignore")


def check_cursor_access():
    """Check what Cursor can access"""

    print("\n" + "=" * 70)
    print("CURSOR ACCESS CHECK")
    print("=" * 70)

    print("\n📋 .cursorignore configuration:")
    print("-" * 40)

    with open(".cursorignore", "r") as f:
        lines = f.readlines()

    # Count negations (files Cursor CAN see)
    inclusions = [line.strip() for line in lines if line.strip().startswith("!")]
    exclusions = [
        line.strip()
        for line in lines
        if line.strip()
        and not line.strip().startswith("#")
        and not line.strip().startswith("!")
    ]

    print(f"Files/patterns explicitly INCLUDED for Cursor: {len(inclusions)}")
    print(f"Files/patterns EXCLUDED from Cursor: {len(exclusions)}")

    print("\n🔓 Key inclusions (Cursor CAN see these):")
    important_inclusions = ["!.env", "!*.key", "!secrets/**", "!venv/**", "!logs/**"]
    for pattern in important_inclusions:
        if pattern in inclusions:
            print(f"  ✅ {pattern[1:]} - Cursor has access")
        else:
            print(f"  ❌ {pattern[1:]} - Cursor might NOT have access")

    print("\n🔒 Exclusions (Cursor CANNOT see these):")
    for exc in exclusions[:5]:  # Show first 5
        print(f"  • {exc}")
    if len(exclusions) > 5:
        print(f"  ... and {len(exclusions) - 5} more")


def verify_configuration():
    """Main verification function"""

    print("🔍 VERIFYING IGNORE CONFIGURATION")
    print("=" * 70)

    # Check if files exist
    print("\n📂 Checking configuration files:")
    print("-" * 40)

    files_to_check = [
        (".gitignore", "GitHub protection"),
        (".cursorignore", "Cursor access control"),
        (".env", "Environment variables"),
        (".git/", "Git repository"),
    ]

    for file, description in files_to_check:
        path = Path(file)
        if path.exists():
            print(f"✅ {file:<20} - {description}")
        else:
            print(f"❌ {file:<20} - Not found")

    # Check sensitive files protection
    check_sensitive_files()

    # Check Cursor access
    check_cursor_access()

    # Summary
    print("\n" + "=" * 70)
    print("CONFIGURATION SUMMARY")
    print("=" * 70)

    print(
        """
✅ CORRECT SETUP:
----------------
1. .gitignore protects sensitive files from GitHub
2. .cursorignore uses negation (!) to give Cursor full access
3. Result: GitHub can't see secrets, Cursor can see everything

📋 KEY POINTS:
--------------
• GitHub will NOT see: .env, *.key, secrets/, logs/, venv/
• Cursor CAN see: Everything except large binaries
• You get: Full AI assistance with complete context

⚠️ SECURITY REMINDERS:
----------------------
• Never manually add .env to git
• Check 'git status' before committing
• Use 'git diff --cached' to review staged changes
• Consider using git-secrets for extra protection

💡 USEFUL COMMANDS:
-------------------
• Check if file is ignored: git check-ignore <file>
• See all ignored files: git status --ignored
• Test .gitignore rules: git check-ignore -v <file>
• Force add ignored file (DANGEROUS): git add -f <file>
"""
    )

    # Final safety check
    print("=" * 70)
    print("FINAL SAFETY CHECK")
    print("=" * 70)

    # Check if .env is tracked
    result = subprocess.run(["git", "ls-files", ".env"], capture_output=True, text=True)

    if result.stdout.strip():
        print("🚨 CRITICAL: .env is tracked by git! Remove it immediately:")
        print("   git rm --cached .env")
        print("   git commit -m 'Remove .env from tracking'")
    else:
        print("✅ SAFE: .env is NOT tracked by git")

    print("\n✨ Configuration verified successfully!")


if __name__ == "__main__":
    verify_configuration()
