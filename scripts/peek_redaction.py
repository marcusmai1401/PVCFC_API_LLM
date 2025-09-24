import json
from pathlib import Path

p = max(Path("logs/ui_events").glob("session_*.jsonl"), key=lambda p: p.stat().st_mtime)
with p.open("r", encoding="utf-8") as f:
    for line in f:
        try:
            evt = json.loads(line)
        except Exception:
            continue
        if evt.get("message") == "redaction test":
            print(json.dumps(evt, ensure_ascii=False, indent=2))
            break
