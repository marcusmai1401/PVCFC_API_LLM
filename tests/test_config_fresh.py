import sys
from pathlib import Path

from dotenv import load_dotenv

# Force reload .env
load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

print("=" * 80)
print("TESTING CAD TAG EXTRACTION - FRESH CONFIG")
print("=" * 80)
print()

# Force reimport config
import importlib

if "app.config" in sys.modules:
    del sys.modules["app.config"]
if "app.config.pipeline_config" in sys.modules:
    del sys.modules["app.config.pipeline_config"]

from app.config import get_config

config = get_config()
print(f"ENABLE_PID_TAGS: {config.ENABLE_PID_TAGS}")
print(f"GATE_MODE: {config.GATE_MODE}")
print(f"GATE_THRESHOLD: {config.GATE_THRESHOLD}")
print(f"TAGS_INDEX_NAME: {config.TAGS_INDEX_NAME}")
print()

if config.ENABLE_PID_TAGS:
    print("? Feature is ENABLED")
else:
    print("? Feature is still DISABLED")
