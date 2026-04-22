import urllib.request
import json
import time

subjects = [
    ("Physics", "Newton's Laws"),
    ("Biology", "Cell Division Mitosis Meiosis"),
    ("CS", "Data Structures Basics"),
    ("Mathematics", "Derivatives Intro")
]

def run_test(course_req):
    print(f"--- Running E2E test for: {course_req} ---")
    req = urllib.request.Request(
        'http://localhost:8000/generate',
        data=json.dumps({"course_requirement": course_req, "student_persona": "High school student"}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    try:
        res = urllib.request.urlopen(req)
        for line in res:
            line_decoded = line.decode().strip()
            if line_decoded:
                print(line_decoded)
    except Exception as e:
        print(f"Error for {course_req}: {e}")

for _, topic in subjects:
    run_test(topic)
    time.sleep(2)
