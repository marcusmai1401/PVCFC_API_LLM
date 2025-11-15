import json

import requests

url = "http://localhost:8000/ask"
payload = {
    "query": "FIC-310 nằm ở trang nào trong P&ID?",
    "query_type": "pid",
    "max_context": 5,
    "hyde": False,
    "language": "vi",
}

print("Sending request to:", url)
print("Payload:", json.dumps(payload, indent=2))

response = requests.post(url, json=payload)
print(f"\nStatus: {response.status_code}")
print(f"Response:\n{response.text}")
