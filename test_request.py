import requests
import json

url = "http://localhost:8000/generate"
payload = {
    "course_requirement": "Recursion in Computer Science",
    "student_persona": "An visual-heavy learner who needs clear diagrams and analogies to understand abstract code concepts.",
    "model_override": "models/gemini-1.5-flash"
}

headers = {
    "Content-Type": "application/json"
}

print(f"Sending request to {url}...")
try:
    # Increased timeout for refinement loop
    response = requests.post(url, json=payload, headers=headers, timeout=600)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Success! Response:")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
