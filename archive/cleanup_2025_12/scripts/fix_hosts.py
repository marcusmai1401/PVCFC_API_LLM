#!/usr/bin/env python3
"""
Fix host placeholders in project files
"""
import os
import re


def fix_file(filepath, old_pattern, new_value):
    """Replace pattern in file"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content
        # Replace the placeholder with correct value
        content = re.sub(old_pattern, new_value, content)

        if content != original_content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✓ Fixed: {filepath}")
            return True
        else:
            print(f"  No changes needed: {filepath}")
            return False
    except Exception as e:
        print(f"✗ Error fixing {filepath}: {e}")
        return False


def main():
    """Fix all host placeholders"""
    print("Fixing host placeholders in project files...")
    print("-" * 50)

    files_to_fix = [
        ("app/main.py", r"\*{9}", "127.0.0.1"),
        ("launchers/start_api.ps1", r"\*{9}", "127.0.0.1"),
        ("QUICKSTART.md", r"\*{9}", "127.0.0.1"),
    ]

    fixed_count = 0
    for filepath, pattern, replacement in files_to_fix:
        full_path = os.path.join(os.path.dirname(__file__), filepath)
        if os.path.exists(full_path):
            if fix_file(full_path, pattern, replacement):
                fixed_count += 1
        else:
            print(f"  File not found: {filepath}")

    print("-" * 50)
    print(f"Fixed {fixed_count} files")

    # Also check for 0.0.0.0 references
    print("\nChecking for 0.0.0.0 references...")
    files_to_check = [
        "app/main.py",
        "launchers/start_api.ps1",
        "Dockerfile",
        "Makefile",
    ]

    for filepath in files_to_check:
        full_path = os.path.join(os.path.dirname(__file__), filepath)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
                if "0.0.0.0" in content:
                    print(
                        f"⚠ Found 0.0.0.0 in {filepath} - consider changing to 127.0.0.1 for local dev"
                    )


if __name__ == "__main__":
    main()
