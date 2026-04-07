import json
import os
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


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


class ErrorLogger:
    """Persists pipeline errors to a structured JSON log for easier debugging.
    
    Each entry captures:
      - run_id         : the UUID of the failed run
      - timestamp      : ISO-8601 UTC timestamp
      - failed_stage   : which pipeline stage raised the exception (e.g. "m4_generator")
      - error_type     : exception class name (e.g. "ValidationError", "TimeoutError")
      - error_message  : str(exception)
      - traceback      : full formatted traceback
      - request        : the original GenerationRequest (for reproducing the failure)
    """

    def __init__(self, log_file: str = "m8_errors.json"):
        self.log_file = log_file

    def log_error(
        self,
        run_id: str,
        exc: Exception,
        request_data: Optional[Dict[str, Any]] = None,
        failed_stage: str = "unknown",
    ) -> None:
        """Append one error entry.  Synchronous so it works inside except blocks."""
        logs = []
        if os.path.exists(self.log_file):
            with open(self.log_file, "r") as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    pass

        entry = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "failed_stage": failed_stage,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": traceback.format_exc(),
            "request": request_data,
        }
        logs.append(entry)

        with open(self.log_file, "w") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
