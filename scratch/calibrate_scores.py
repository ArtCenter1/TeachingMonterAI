import json
import os
import statistics
from loguru import logger

def calibrate(log_file="m8_feedback.json"):
    if not os.path.exists(log_file):
        logger.error(f"Log file {log_file} not found.")
        return

    with open(log_file, "r", encoding="utf-8") as f:
        try:
            logs = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse {log_file}")
            return

    scores_by_strategy = {}

    for entry in logs:
        data = entry.get("data", {})
        strategy = data.get("selected_strategy")
        if not strategy:
            continue
        
        # Get AI student scores
        ai_scores = data.get("ai_student_scores", {})
        if not ai_scores:
            continue
            
        # Get public feedback
        public_feedback = data.get("public_feedback", [])
        avg_public = sum(f.get("star_rating", 0) for f in public_feedback) / len(public_feedback) if public_feedback else None
        
        if strategy not in scores_by_strategy:
            scores_by_strategy[strategy] = {
                "clarity": [], "integrity": [], "depth": [], 
                "practicality": [], "pertinence": [],
                "adaptability": [], "engagement": [],
                "public_rating": []
            }
            
        for metric in ["clarity", "integrity", "depth", "practicality", "pertinence", "adaptability", "engagement"]:
            if metric in ai_scores:
                scores_by_strategy[strategy][metric].append(ai_scores[metric])
        
        if avg_public is not None:
            scores_by_strategy[strategy]["public_rating"].append(avg_public)

    print("\n=== PEDAGOGICAL SCORE CALIBRATION REPORT ===\n")
    
    for strategy, metrics in scores_by_strategy.items():
        print(f"Strategy: {strategy}")
        print("-" * (len(strategy) + 10))
        
        for metric, vals in metrics.items():
            if not vals:
                continue
            avg = statistics.mean(vals)
            std = statistics.stdev(vals) if len(vals) > 1 else 0
            print(f"  {metric:15}: {avg:.2f} (±{std:.2f})")
        
        print()

    # Recommendation Logic
    print("RECOMMENDATIONS:")
    for strategy, metrics in scores_by_strategy.items():
        engagement = metrics.get("engagement", [])
        if engagement and statistics.mean(engagement) < 6:
            print(f"  - [WARNING] '{strategy}' has low engagement scores. Consider injecting more hook-driven prompts in M4.")
        
        adaptability = metrics.get("adaptability", [])
        if adaptability and statistics.mean(adaptability) < 6:
            print(f"  - [WARNING] '{strategy}' has low adaptability scores. Persona constraints in M4 may be too weak.")

if __name__ == "__main__":
    calibrate()
