from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_generate_video():
    # This test might take a few seconds due to the sleep in M7 stub
    payload = {
        "course_requirement": "Self-Attention Mechanism",
        "student_persona": "High schooler, no calculus"
    }
    response = client.post("/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "video_url" in data
    assert "generation_time_seconds" in data
    assert data["video_url"].startswith("http")
