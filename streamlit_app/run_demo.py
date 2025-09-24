#!/usr/bin/env python3
"""
🚀 RAG Pipeline Demo Launcher

This script helps you start the Streamlit demo with proper setup and error handling.
"""

import os
import subprocess
import sys
from pathlib import Path


def check_requirements():
    """Check if required packages are installed."""
    required_packages = ["streamlit", "pandas", "plotly", "numpy"]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    return missing_packages


def install_requirements():
    """Install requirements from requirements.txt."""
    requirements_file = Path(__file__).parent / "requirements.txt"

    if not requirements_file.exists():
        print("❌ requirements.txt file not found!")
        return False

    try:
        print("📦 Installing required packages...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
        )
        print("✅ Installation completed!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Installation failed: {e}")
        return False


def run_streamlit():
    """Run the Streamlit application."""
    app_file = Path(__file__).parent / "app.py"

    if not app_file.exists():
        print("❌ app.py file not found!")
        return False

    try:
        print("🚀 Starting Streamlit demo...")
        print("📱 The app will open in your browser at: http://localhost:8501")
        print("⏹️  Press Ctrl+C to stop the application")
        print("-" * 50)

        subprocess.check_call([sys.executable, "-m", "streamlit", "run", str(app_file)])
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start Streamlit: {e}")
        return False
    except KeyboardInterrupt:
        print("\n👋 Demo stopped by user")
        return True


def main():
    """Main launcher function."""
    print("🚀 RAG Pipeline Demo Launcher")
    print("=" * 40)

    # Check if we're in the right directory
    if not Path("app.py").exists():
        print("❌ Please run this script from the streamlit_app directory!")
        print("💡 Try: cd streamlit_app && python run_demo.py")
        sys.exit(1)

    # Check requirements
    print("🔍 Checking requirements...")
    missing = check_requirements()

    if missing:
        print(f"📋 Missing packages: {', '.join(missing)}")

        response = (
            input("📥 Would you like to install them now? (y/n): ").lower().strip()
        )

        if response in ["y", "yes"]:
            if not install_requirements():
                print("❌ Installation failed. Please install manually using:")
                print("   pip install -r requirements.txt")
                sys.exit(1)
        else:
            print("📝 Please install requirements manually:")
            print("   pip install -r requirements.txt")
            sys.exit(1)
    else:
        print("✅ All requirements satisfied!")

    # Run the demo
    if not run_streamlit():
        sys.exit(1)


if __name__ == "__main__":
    main()
