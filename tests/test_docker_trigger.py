import httpx
import json
import time

def trigger_test():
    url = "http://localhost:8000/generate"
    payload = {
        "course_requirement": "Intro to Advanced Debugging",
        "student_persona": "The Antigravity AI Agent",
        "run_id": "v010_test_run"
    }
    
    print(f"Sending request to {url}...")
    try:
        # We increase the timeout as the pipeline can take a while to start/error
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload)
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    trigger_test()
