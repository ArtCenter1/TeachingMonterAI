import json
import os
import re
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from loguru import logger
from .utils import infer_subject


# ── Phase 3: Strategy Win-Rate Tracker ──────────────────────────────────────
class StrategyTracker:
    """Tracks which scaffolding strategy wins per (strategy × level × subject).

    This is the foundation of the PRD Phase 3 meta-policy.  Every pipeline run
    that completes the critic stage records which strategy scored highest.
    The data is persisted to a JSON file and queried by M4's ε-greedy selector.
    """

    def __init__(self, store_file: str = "strategy_stats.json"):
        self.store_file = store_file
        self._stats: Dict[str, Dict] = self._load()

    def _load(self) -> Dict[str, Dict]:
        if os.path.exists(self.store_file):
            try:
                with open(self.store_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save(self) -> None:
        with open(self.store_file, "w", encoding="utf-8") as f:
            json.dump(self._stats, f, indent=2, ensure_ascii=False)

    def _make_key(self, strategy: str, level: str, subject: str) -> str:
        """Create a composite key for the stats dict."""
        return f"{strategy}|{level}|{subject}"

    def total_run_count(self) -> int:
        """Return the total number of runs recorded across all strategies."""
        return sum(data["total"] for data in self._stats.values())

    def record_win(
        self,
        winning_strategy: str,
        all_strategies: List[str],
        level: str,
        subject: str,
    ) -> None:
        """Record the outcome of a Best-of-N selection.

        The winning strategy gets a 'win', all others get a 'loss'.
        This builds the win-rate table the ε-greedy selector reads.
        """
        for strategy in all_strategies:
            key = self._make_key(strategy, level, subject)
            if key not in self._stats:
                self._stats[key] = {
                    "strategy": strategy,
                    "level": level,
                    "subject": subject,
                    "wins": 0,
                    "losses": 0,
                    "elo_wins": 0,
                    "elo_losses": 0,
                    "total": 0,
                }
            self._stats[key]["total"] += 1
            if strategy == winning_strategy:
                self._stats[key]["wins"] += 1
            else:
                self._stats[key]["losses"] += 1
        self._save()
        logger.info(
            f"[StrategyTracker] Recorded win for '{winning_strategy}' "
            f"(level={level}, subject={subject})"
        )

    def record_elo_outcome(
        self, strategy: str, level: str, subject: str, won: bool
    ) -> None:
        """Record an Elo arena outcome for a strategy (from competition results)."""
        key = self._make_key(strategy, level, subject)
        if key not in self._stats:
            self._stats[key] = {
                "strategy": strategy,
                "level": level,
                "subject": subject,
                "wins": 0,
                "losses": 0,
                "elo_wins": 0,
                "elo_losses": 0,
                "total": 0,
            }
        if won:
            self._stats[key]["elo_wins"] += 1
        else:
            self._stats[key]["elo_losses"] += 1
        self._save()
        logger.info(
            f"[StrategyTracker] Elo {'win' if won else 'loss'} for '{strategy}' "
            f"(level={level}, subject={subject})"
        )

    def get_win_rates(self, level: str = None, subject: str = None) -> Dict[str, float]:
        """Return win rates per strategy, optionally filtered by level/subject.

        Returns: { "Intuition-First": 0.67, "Cognitive-Conflict": 0.45, ... }
        """
        # Aggregate across all matching keys
        agg: Dict[str, Dict[str, int]] = {}
        for key, data in self._stats.items():
            if level and data["level"] != level:
                continue
            if subject and data["subject"] != subject:
                continue
            s = data["strategy"]
            if s not in agg:
                agg[s] = {"wins": 0, "total": 0}
            agg[s]["wins"] += data["wins"]
            agg[s]["total"] += data["total"]

        return {
            s: round(d["wins"] / d["total"], 3) if d["total"] > 0 else 0.0
            for s, d in agg.items()
        }

    def get_full_stats(self) -> List[Dict]:
        """Return all tracked stats for the dashboard endpoint."""
        result = []
        for key, data in self._stats.items():
            win_rate = round(data["wins"] / data["total"], 3) if data["total"] > 0 else 0.0
            elo_total = data["elo_wins"] + data["elo_losses"]
            elo_rate = round(data["elo_wins"] / elo_total, 3) if elo_total > 0 else None
            result.append({
                **data,
                "win_rate": win_rate,
                "elo_win_rate": elo_rate,
            })
        return sorted(result, key=lambda x: x["win_rate"], reverse=True)


# ── Feedback Logger ─────────────────────────────────────────────────────────
class FeedbackLogger:
    def __init__(self, log_file: str = "m8_feedback.json"):
        self.log_file = log_file
        self.strategy_tracker = StrategyTracker()

    async def log_run(
        self,
        run_id: str,
        data: Dict[str, Any],
        selection_log: List[Dict[str, Any]] = None,
    ):
        """Log a generation run with optional selection/A/B data.

        Also auto-records strategy win in the StrategyTracker (Phase 3).
        """
        logs = []
        if os.path.exists(self.log_file):
            with open(self.log_file, "r", encoding="utf-8", errors="replace") as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    pass

        entry = {"run_id": run_id, "data": data, "selection_log": selection_log}
        logs.append(entry)

        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)

        # ── Phase 3: Auto-record strategy win ──────────────────────────────
        # Check for greedy_selected flag in selection_log. If any variant was
        # selected via a greedy choice, we skip multi-strategy win/loss
        # recording to avoid corrupting the denominator.
        is_greedy = any(s.get("greedy_selected", False) for s in selection_log)
        
        if selection_log and data.get("selected_strategy") and not is_greedy:
            winning = data["selected_strategy"]
            all_strategies = [s.get("strategy", "") for s in selection_log]
            # Extract level and subject from request data
            level = "high_school"  # default
            if "student_model" in data:
                level = data["student_model"].get("level", level)
            
            # Infer subject using shared utility
            req = ""
            if "request" in data:
                req = data["request"].get("course_requirement", "")
            subject = infer_subject(req)

            self.strategy_tracker.record_win(winning, all_strategies, level, subject)
        elif is_greedy:
            logger.info(f"[M8] Greedy selection detected for run {run_id}. Skipping multi-strategy win recording.")

    def add_ai_student_feedback(
        self,
        run_id: str,
        ai_student_scores: Dict[str, Any],
        critique_text: str,
        elo_outcome: str = None,
    ) -> bool:
        """Append AI student feedback to an existing run entry.

        If elo_outcome is provided ("win" or "loss"), also update the
        strategy tracker with the Elo result.
        """
        logs = []
        if os.path.exists(self.log_file):
            with open(self.log_file, "r", encoding="utf-8") as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    return False

        for entry in logs:
            if entry.get("run_id") == run_id:
                entry["data"]["ai_student_scores"] = ai_student_scores
                entry["data"]["critique_text"] = critique_text
                if elo_outcome:
                    entry["data"]["elo_outcome"] = elo_outcome

                # Phase 3: Record Elo outcome in strategy tracker
                if elo_outcome and entry.get("data", {}).get("selected_strategy"):
                    strategy = entry["data"]["selected_strategy"]
                    level = entry["data"].get("student_model", {}).get("level", "high_school")
                    # Re-infer subject using shared utility
                    req = entry["data"].get("request", {}).get("course_requirement", "")
                    subject = infer_subject(req)
                    self.strategy_tracker.record_elo_outcome(
                        strategy, level, subject, won=(elo_outcome == "win")
                    )

                with open(self.log_file, "w", encoding="utf-8") as f:
                    json.dump(logs, f, indent=2, ensure_ascii=False)
                return True

        return False  # Run ID not found

    def add_public_feedback(
        self,
        run_id: str,
        star_rating: int,
        comments: Optional[str] = None,
    ) -> bool:
        """Append public student feedback to an existing run entry.

        If the star_rating translates to a decisive outcome (>=4 is win, <=2 is loss),
        also update the strategy tracker with the Elo result.
        """
        logs = []
        if os.path.exists(self.log_file):
            with open(self.log_file, "r", encoding="utf-8") as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    return False

        for entry in logs:
            if entry.get("run_id") == run_id:
                if "public_feedback" not in entry["data"]:
                    entry["data"]["public_feedback"] = []
                entry["data"]["public_feedback"].append({
                    "star_rating": star_rating,
                    "comments": comments,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                # Phase 5: Record Elo outcome in strategy tracker based on real human feedback
                elo_outcome = "win" if star_rating >= 4 else ("loss" if star_rating <= 2 else None)
                if elo_outcome and entry.get("data", {}).get("selected_strategy"):
                    strategy = entry["data"]["selected_strategy"]
                    level = entry["data"].get("student_model", {}).get("level", "high_school")
                    req = entry["data"].get("request", {}).get("course_requirement", "")
                    subject = infer_subject(req)
                    self.strategy_tracker.record_elo_outcome(
                        strategy, level, subject, won=(elo_outcome == "win")
                    )

                with open(self.log_file, "w", encoding="utf-8") as f:
                    json.dump(logs, f, indent=2, ensure_ascii=False)
                return True

        return False  # Run ID not found

    def get_rlt_run_count(self) -> int:
        """Count how many runs have RLT scores recorded."""
        if not os.path.exists(self.log_file):
            return 0
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                logs = json.load(f)
                count = 0
                for entry in logs:
                    sel_log = entry.get("selection_log", [])
                    # If the first variant in selection_log has RLT metrics, count it
                    if sel_log and "rlt_comprehension_score" in sel_log[0]:
                        count += 1
                return count
        except (json.JSONDecodeError, IOError):
            return 0


# ── Error Logger ────────────────────────────────────────────────────────────
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

    def _mask_sensitive_data(self, text: str) -> str:
        """Redacts common API key patterns from text."""
        if not text:
            return text
        # Redact Google API keys (AIza...), OpenRouter/OpenAI (sk-...), etc.
        patterns = [
            (r"AIzaSy[A-Za-z0-9_-]{33}", "AIzaSy... [REDACTED]"),
            (r"sk-[a-zA-Z0-9]{20,}", "sk-... [REDACTED]"),
            (r"sk-or-v1-[a-zA-Z0-9]{32,}", "sk-or-... [REDACTED]"),
        ]
        masked = text
        for pattern, replacement in patterns:
            masked = re.sub(pattern, replacement, masked)
        return masked

    def _sanitize_request(self, data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Removes sensitive keys from request metadata."""
        if not data:
            return data
        sanitized = data.copy()
        sensitive_keys = ["google_api_key", "search_api_key", "openrouter_api_key", "xai_api_key", "api_key"]
        for key in sensitive_keys:
            if key in sanitized:
                sanitized[key] = "[REDACTED]"
        return sanitized

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
            with open(self.log_file, "r", encoding="utf-8") as f:
                try:
                    loaded = json.load(f)
                    # Guard: file may have been initialised as a {} dict — reset if so
                    if isinstance(loaded, list):
                        logs = loaded
                    else:
                        logger.warning(
                            f"[ErrorLogger] {self.log_file} contained non-list JSON "
                            "— resetting to empty log."
                        )
                except json.JSONDecodeError:
                    pass

        entry = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "failed_stage": failed_stage,
            "error_type": type(exc).__name__,
            "error_message": self._mask_sensitive_data(str(exc)),
            "traceback": self._mask_sensitive_data(traceback.format_exc()),
            "request": self._sanitize_request(request_data),
        }
        logs.append(entry)

        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)

