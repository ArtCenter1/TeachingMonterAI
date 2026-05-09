"""
Teaching Monster AI — Score Calibration Script (Phase 4/5)
Calibrates AI Student internal rubrics against human star ratings to detect scoring drift.
"""

import os
import json
import numpy as np
from typing import List, Dict, Any
from loguru import logger

# Configuration
LOG_FILE = "m8_feedback.json"
OUTPUT_REPORT = "artifacts/calibration_report.md"

def calculate_calibration():
    if not os.path.exists(LOG_FILE):
        logger.error(f"Log file {LOG_FILE} not found.")
        return

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        try:
            logs = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse {LOG_FILE}")
            return

    data_points = []
    
    for entry in logs:
        run_data = entry.get("data", {})
        ai_scores = run_data.get("ai_student_scores", {})
        public_feedback = run_data.get("public_feedback", [])
        
        if not ai_scores or not public_feedback:
            continue
            
        # Get the average public rating for this run
        public_ratings = [fb.get("star_rating", 0) for fb in public_feedback]
        avg_public = sum(public_ratings) / len(public_ratings)
        
        # Normalize AI scores (usually 1-10) to 1-5 scale for comparison
        # Rubric: clarity, integrity, depth, practicality, pertinence, adaptability, engagement
        internal_avg = sum(ai_scores.values()) / len(ai_scores) / 2.0
        
        data_points.append({
            "run_id": entry.get("run_id"),
            "internal_score": internal_avg,
            "human_score": avg_public,
            "error": internal_avg - avg_public
        })

    if not data_points:
        logger.warning("No matched score pairs found (requires both AI critique and Human feedback).")
        return

    # Statistical Analysis
    internal_scores = [d["internal_score"] for d in data_points]
    human_scores = [d["human_score"] for d in data_points]
    errors = [d["error"] for d in data_points]
    
    mse = np.mean(np.square(errors))
    mae = np.mean(np.abs(errors))
    correlation = np.corrcoef(internal_scores, human_scores)[0, 1] if len(data_points) > 1 else 1.0

    # Generate Markdown Report
    report = f"""# 📊 Score Calibration Report
**Generated at**: {np.datetime64('now')}
**Data Points**: {len(data_points)}

## Summary Metrics
| Metric | Value |
| :--- | :--- |
| **Mean Absolute Error (MAE)** | {mae:.3f} |
| **Mean Squared Error (MSE)** | {mse:.3f} |
| **Pearson Correlation (r)** | {correlation:.3f} |

## Observations
"""
    if correlation < 0.5:
        report += "> [!CAUTION]\n> **Critical Drift**: Low correlation between AI rubrics and Human satisfaction. Recalibration of CIDPP dimensions required.\n"
    elif mae > 1.0:
        report += "> [!WARNING]\n> **Scaling Offset**: AI student is consistently scoring {('higher' if np.mean(errors) > 0 else 'lower')} than humans.\n"
    else:
        report += "> [!NOTE]\n> **Alignment OK**: AI student scores are tracking well with human feedback.\n"

    report += "\n## Run Details\n| Run ID | AI Score (Norm) | Human Score | Delta |\n| :--- | :--- | :--- | :--- |\n"
    for d in data_points:
        report += f"| {d['run_id'][:8]}... | {d['internal_score']:.2f} | {d['human_score']:.1f} | {d['error']:+.2f} |\n"

    os.makedirs("artifacts", exist_ok=True)
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write(report)
        
    logger.success(f"Calibration report saved to {OUTPUT_REPORT}")

if __name__ == "__main__":
    calculate_calibration()
