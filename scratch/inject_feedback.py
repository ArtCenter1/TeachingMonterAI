import json
from modules.m8_logger import FeedbackLogger
import os

def main():
    logger = FeedbackLogger("m8_feedback.json")
    
    # Find the latest run
    with open("m8_feedback.json", "r") as f:
        logs = json.load(f)
    
    latest_run = logs[-1]["run_id"]
    print(f"Found latest run: {latest_run}")
    
    # Inject the feedback we got from the browser subagent
    scores = {
        "accuracy": 4.4,
        "logic": 4.5,
        "adaptability": 3.4,
        "engagement": 2.7
    }
    
    critique = "The report notes that the video provides a high-quality conceptual overview aligned with AP/IB standards, using effective analogies like 'train vs. car.' However, it points out that the AI-generated background imagery contains 'nonsensical artifacts' and suggests replacing them with standard physics schematics and real mathematical notation."
    
    # Let's decide elo_outcome: accuracy and logic are high, but engagement is low. 
    # Average is (4.4+4.5+3.4+2.7)/4 = 3.75. Not a strict win, but logic is good.
    # Let's consider it a "win" for strategy purposes, or maybe "loss" since engagement was < 3. 
    # We'll put "loss" to trigger strategy evolution on the images.
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
