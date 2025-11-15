import os
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(".env")
print(f"Env file exists: {env_path.exists()}")
print(f'BEFORE load_dotenv: {os.environ.get("ENABLE_PID_TAGS", "not_set")}')

load_dotenv(env_path)

print(f'AFTER load_dotenv: {os.environ.get("ENABLE_PID_TAGS", "not_set")}')
print(f'GATE_THRESHOLD: {os.environ.get("GATE_THRESHOLD", "not_set")}')
