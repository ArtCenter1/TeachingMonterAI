import json
from modules.m8_logger import FeedbackLogger
import os

def main():
    logger = FeedbackLogger("m8_feedback.json")
    
    with open("m8_feedback.json", "r") as f:
        logs = json.load(f)
    
    latest_run = logs[-1]["run_id"]
    print(f"Found latest run: {latest_run}")
    
    scores = {
        "accuracy": 4.4,
        "logic": 4.5,
        "adaptability": 3.4,
        "engagement": 2.7
    }
    
    critique = "The report notes that the video provides a high-quality conceptual overview aligned with AP/IB standards, using effective analogies like 'train vs. car.' However, it points out that the AI-generated background imagery contains 'nonsensical artifacts' and suggests replacing them with standard physics schematics and real mathematical notation."
    
    elo_outcome = "loss"
    
    success = logger.add_ai_student_feedback(
        run_id=latest_run,
        ai_student_scores=scores,
        critique_text=critique,
        elo_outcome=elo_outcome
    )
    
    print(f"Feedback injection success: {success}")

if __name__ == "__main__":
    main()
