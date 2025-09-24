#!/usr/bin/env python3
"""
Safe launcher for the Streamlit RAG Pipeline Demo.
This script ensures proper error handling and dependency checking.
"""

import os
import subprocess
import sys
from pathlib import Path


def check_dependencies():
    """Check if required packages are installed."""
    required = {
        "streamlit": "1.29.0",
        "pandas": "2.0.3",
        "plotly": "5.17.0",
        "numpy": "1.24.3",
    }

    missing = []
    version_mismatch = []

    for package, required_version in required.items():
        try:
            module = __import__(package)
            installed_version = getattr(module, "__version__", "unknown")

            # Basic version check
            if installed_version != "unknown" and installed_version != required_version:
                # Just warn, don't fail
                print(
                    f"⚠️  {package}: installed {installed_version}, recommended {required_version}"
                )
            else:
                print(f"✅ {package}: {installed_version}")

        except ImportError:
            missing.append(f"{package}=={required_version}")

    return missing


def install_dependencies(packages):
    """Install missing packages."""
    if not packages:
        return True

    print(f"\n📦 Installing missing packages: {', '.join(packages)}")

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade"] + packages
        )
        print("✅ Installation completed!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Installation failed: {e}")
        return False


def run_streamlit(use_stable=True):
    """Run the Streamlit application."""
    # Choose which app to run
    app_file = "app_stable.py" if use_stable else "app.py"
    app_path = Path(__file__).parent / app_file

    if not app_path.exists():
        print(f"❌ {app_file} not found!")
        return False

    print(f"\n🚀 Starting Streamlit with {app_file}...")
    print("📱 The app will open at: http://localhost:8501")
    print("⏹️  Press Ctrl+C to stop\n")
    print("-" * 50)

    env = os.environ.copy()
    # Set some environment variables for stability
    env["STREAMLIT_SERVER_MAX_UPLOAD_SIZE"] = "200"
    env["STREAMLIT_SERVER_MAX_MESSAGE_SIZE"] = "200"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(app_path),
                "--server.maxUploadSize",
                "200",
                "--server.maxMessageSize",
                "200",
                "--server.fileWatcherType",
                "none",  # Disable file watcher for stability
                "--browser.gatherUsageStats",
                "false",
            ],
            env=env,
            check=False,
        )
        return True
    except KeyboardInterrupt:
        print("\n\n👋 Streamlit stopped by user")
        return True
    except Exception as e:
        print(f"\n❌ Error running Streamlit: {e}")
        return False


def main():
    """Main entry point."""
    print("=" * 50)
    print("  🚀 RAG Pipeline Demo - Safe Launcher")
    print("=" * 50)

    # Check we're in the right directory
    if not Path("app_stable.py").exists() and not Path("app.py").exists():
        print("\n❌ Error: App files not found!")
        print("📁 Please run this script from the streamlit_app directory")
        sys.exit(1)

    # Check dependencies
    print("\n🔍 Checking dependencies...")
    missing = check_dependencies()

    if missing:
        print(f"\n📋 Missing packages: {', '.join(missing)}")
        response = input("\n📥 Install missing packages? (y/n): ").lower().strip()

        if response in ["y", "yes"]:
            if not install_dependencies(missing):
                print("\n❌ Failed to install dependencies")
                print("Try manually: pip install -r requirements.txt")
                sys.exit(1)
        else:
            print("\n⚠️  Running without all dependencies...")
            print("Some features may not work properly")

    # Ask which version to use
    print("\n📋 Select app version:")
    print("1. Stable version (recommended)")
    print("2. Full version (may have issues)")

    choice = input("\nEnter choice (1 or 2) [1]: ").strip() or "1"
    use_stable = choice == "1"

    # Run the app
    if not run_streamlit(use_stable):
        print("\n❌ Failed to start Streamlit")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
