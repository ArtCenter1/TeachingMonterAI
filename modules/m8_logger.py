import json
import os
from typing import Any, Dict

class FeedbackLogger:
    def __init__(self, log_file: str = "m8_feedback.json"):
        self.log_file = log_file

    async def log_run(self, run_id: str, data: Dict[str, Any]):
        # Simple JSON logging for MVP
        logs = []
        if os.path.exists(self.log_file):
            with open(self.log_file, "r") as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    pass
        
        logs.append({"run_id": run_id, "data": data})
        
        with open(self.log_file, "w") as f:
            json.dump(logs, f, indent=2)
