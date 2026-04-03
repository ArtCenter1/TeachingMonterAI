import requests
import json

url = "http://localhost:8000/generate"
payload = {
    "course_requirement": "Conservation of Momentum",
    "student_persona": "10th grade student with high curiosity but struggles with math formulas",
    "model_override": "google/gemini-2.0-flash-exp:free"
}

headers = {
    "Content-Type": "application/json"
}

print(f"Sending request to {url}...")
try:
    response = requests.post(url, json=payload, headers=headers, timeout=300)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Success! Response:")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
