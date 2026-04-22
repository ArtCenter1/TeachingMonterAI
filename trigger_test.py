import urllib.request
import json
import sys

req = urllib.request.Request(
    'http://localhost:8000/generate',
    data=json.dumps({"course_requirement": "Quantum Mechanics Basics", "student_persona": "High school student"}).encode(),
    headers={'Content-Type': 'application/json'}
)
try:
    res = urllib.request.urlopen(req)
    for line in res:
        print(line.decode().strip())
except Exception as e:
    print(f"Error: {e}")
