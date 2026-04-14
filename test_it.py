import requests
import json

data = {
    "course_requirement": "Quantum Entanglement",
    "target_grade_level": 10,
    "student_persona": "Needs analogies"
}
try:
    response = requests.post("http://localhost:8000/generate", json=data)
    print("STATUS", response.status_code)
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)
except Exception as e:
    print(e)
