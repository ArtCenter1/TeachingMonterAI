import urllib.request
import json
import concurrent.futures
import time

SUBJECTS = [
    {"course_requirement": "Cell Division Mitosis Meiosis", "student_persona": "High school student"},
    {"course_requirement": "Quantum Mechanics Basics", "student_persona": "High school student"},
    {"course_requirement": "Dynamic Programming", "student_persona": "Undergraduate student"},
    {"course_requirement": "Differential Equations", "student_persona": "Undergraduate student"}
]

def make_request(subject):
    print(f"Starting request for {subject['course_requirement']}...")
    req = urllib.request.Request(
        'http://localhost:8000/generate',
        data=json.dumps(subject).encode(),
        headers={'Content-Type': 'application/json'}
    )
    start_time = time.time()
    try:
        res = urllib.request.urlopen(req, timeout=1200) # 20 minute timeout
        for line in res:
            decoded = line.decode().strip()
            if decoded:
                print(f"[{subject['course_requirement'][:15]}] {decoded}")
        duration = time.time() - start_time
        print(f"SUCCESS: {subject['course_requirement']} completed in {duration:.2f}s")
        return True
    except Exception as e:
        duration = time.time() - start_time
        print(f"ERROR: {subject['course_requirement']} failed after {duration:.2f}s: {e}")
        return False

if __name__ == "__main__":
    print(f"Starting concurrent tests for {len(SUBJECTS)} subjects...")
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(make_request, SUBJECTS))
        
    total_time = time.time() - start_time
    success_count = sum(results)
    
    print("\n--- Test Results ---")
    print(f"Total Time: {total_time:.2f}s")
    print(f"Successful: {success_count}/{len(SUBJECTS)}")
    
    if success_count == len(SUBJECTS):
        print("All 4 subjects processed successfully! Pipeline is robust.")
    else:
        print("Some tests failed. Check logs for details.")
