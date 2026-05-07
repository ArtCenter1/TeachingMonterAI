import json
from modules.m8_logger import FeedbackLogger
import os

def main():
    logger = FeedbackLogger("m8_feedback.json")
    
    # Target run
    run_id = "e9a7cda9-c6f5-44d5-9cd6-4730644ae9b2"
    print(f"Targeting run: {run_id}")
    
    # Actual scores from teaching.monster contest portal
    scores = {
        "accuracy": 1.9,
        "logic": 3.1,
        "adaptability": 1.1,
        "engagement": 1.0
    }
    
    critique = "Factual error at 03:58: 'Y2 minus X1' instead of 'Y2 minus Y1'. Poor visual presentation: Irrelevant AI-generated imagery and nonsensical text. The AI student found the math formula for vector components incorrect."
    
    # Elo Outcome
    elo_outcome = "loss"
    
    success = logger.add_ai_student_feedback(
        run_id=run_id,
        ai_student_scores=scores,
        critique_text=critique,
        elo_outcome=elo_outcome
    )
    
    print(f"Feedback injection success: {success}")

if __name__ == "__main__":
    main()
