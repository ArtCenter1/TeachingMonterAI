import requests
import json

url = "http://localhost:8000/generate"
data = {
    "course_requirement": "Conservation of Linear Momentum",
    "student_persona": "High school physics student"
}

print("Triggering local generation...")
try:
    r = requests.post(url, json=data, stream=True)
    for line in r.iter_lines():
        if line:
            line_text = line.decode('utf-8')
            if line_text.strip():
                print("Received chunk:", line_text[:100], "..." if len(line_text) > 100 else "")
except Exception as e:
    print("Error:", e)
