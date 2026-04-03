import json
import os
from typing import Any, Dict, List

class FeedbackLogger:
    def __init__(self, log_file: str = "m8_feedback.json"):
        self.log_file = log_file

    async def log_run(self, run_id: str, data: Dict[str, Any], selection_log: List[Dict[str, Any]] = None):
        """Log a generation run with optional selection/A/B data."""
        logs = []
        if os.path.exists(self.log_file):
            with open(self.log_file, "r") as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    pass
        
        entry = {
            "run_id": run_id, 
            "data": data,
            "selection_log": selection_log
        }
        logs.append(entry)
        
        with open(self.log_file, "w") as f:
            json.dump(logs, f, indent=2)
