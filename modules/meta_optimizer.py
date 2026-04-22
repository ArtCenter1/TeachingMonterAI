import json
import os
from typing import Dict, Any
from loguru import logger

class MetaOptimizer:
    def __init__(self, m8_log_file: str = "m8_feedback.json"):
        self.m8_log_file = m8_log_file
        
    def _get_average_cidpp_scores(self) -> Dict[str, float]:
        """Compute average CIDPP scores from the feedback log."""
        if not os.path.exists(self.m8_log_file):
            return {}
            
        try:
            with open(self.m8_log_file, "r") as f:
                logs = json.load(f)
        except Exception:
            return {}
            
        if not logs:
            return {}
            
        totals = {"clarity": 0.0, "integrity": 0.0, "depth": 0.0, "practicality": 0.0, "pertinence": 0.0}
        counts = {"clarity": 0, "integrity": 0, "depth": 0, "practicality": 0, "pertinence": 0}
        
        for entry in logs:
            # Try to get breakdown from selection_log where greedy_selected might not be present
            selection_logs = entry.get("selection_log", [])
            for s_log in selection_logs:
                breakdown = s_log.get("breakdown", {})
                for dim in totals.keys():
                    if dim in breakdown:
                        totals[dim] += breakdown[dim]
                        counts[dim] += 1
                        
        averages = {}
        for dim in totals.keys():
            if counts[dim] > 0:
                averages[dim] = totals[dim] / counts[dim]
                
        return averages

    def get_pipeline_optimizations(self) -> Dict[str, Any]:
        """Return dynamic overrides for the pipeline based on historical weaknesses."""
        averages = self._get_average_cidpp_scores()
        
        # Default baseline
        optimizations = {
            "m1_model_override": None,
            "m5_max_revisions": 1,
            "m4_model_override": None
        }
        
        if not averages:
            return optimizations
            
        # Find the weakest dimension
        weakest_dim = min(averages.items(), key=lambda x: x[1])
        weak_dim_name, weak_score = weakest_dim
        
        # Threshold: only intervene if the average is below a very high bar (e.g. 7.5 out of 10)
        # or if it's the absolute lowest by a margin, but let's just use it as the weak link.
        logger.info(f"[MetaOptimizer] Weakest CIDPP dimension: {weak_dim_name} ({weak_score:.2f})")
        
        if weak_dim_name == "integrity" and weak_score < 8.0:
            logger.info("[MetaOptimizer] Promoting M1 RAG to stronger model due to low integrity scores.")
            optimizations["m1_model_override"] = "anthropic/claude-3-opus-20240229"
            
        if weak_dim_name == "clarity" and weak_score < 8.0:
            logger.info("[MetaOptimizer] Increasing M5 critic revision loops due to low clarity scores.")
            optimizations["m5_max_revisions"] = 2
            
        if weak_dim_name == "depth" and weak_score < 8.0:
            logger.info("[MetaOptimizer] Promoting M4 Generator to stronger model due to low depth scores.")
            optimizations["m4_model_override"] = "anthropic/claude-3-opus-20240229"
            
        return optimizations
