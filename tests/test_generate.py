import requests
import json
import time

def test_generate():
    url = "http://127.0.0.1:8000/generate"
    payload = {
        "course_requirement": "Quantum Mechanics for Beginners",
        "student_persona": "A high school student curious about physics but with no prior knowledge of calculus."
    }
    
    print(f"Sending generation request to {url}...")
    try:
        response = requests.post(url, json=payload, timeout=600)  # Long timeout for generation
        if response.status_code == 200:
            print("Success!")
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_generate()
