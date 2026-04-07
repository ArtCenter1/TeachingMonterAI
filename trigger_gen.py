import urllib.request
import json

url = "http://localhost:8000/generate"
payload = {
    "topic": "Photosynthesis",
    "persona": "friendly_monster"
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    print(f"Sending request to {url}...")
    with urllib.request.urlopen(req, timeout=300) as response:
        status = response.getcode()
        body = response.read().decode("utf-8")
        print(f"Status Code: {status}")
        print(f"Response: {body}")
except Exception as e:
    print(f"Error: {e}")
