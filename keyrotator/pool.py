import os
import time
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger

class KeyState(str, Enum):
    HEALTHY      = "HEALTHY"
    RATE_LIMITED = "RATE_LIMITED"   # 429 — auto-recovers after quarantine_sec
    SPENT        = "SPENT"          # 402 — manual revive only
    DEAD         = "DEAD"           # 403 / unknown auth — manual revive only

@dataclass
class KeyEntry:
    index: int                       # 0-based position in pool
    key: str                         # full key value
    alias: str                       # display name e.g. "Key #1 (AIzaSy...9wk)"
    state: KeyState = KeyState.HEALTHY
    quarantine_until: Optional[float] = None  # unix timestamp; None = permanent block
    total_success: int = 0
    total_fail: int = 0
    last_error_code: Optional[int] = None
    last_error_msg: str = ""
    # track timestamps of last successful calls (sliding window)
    success_times: list[float] = field(default_factory=list)

def _make_alias(index: int, key: str) -> str:
    # Shows first 8 and last 4 chars: "AIzaSyAB...9wk"
    if len(key) <= 12:
        return f"Key #{index + 1} ({key})"
    return f"Key #{index + 1} ({key[:8]}...{key[-4:]})"

class KeyPool:
    def __init__(
        self,
        provider: str,          # "gemini" or "openrouter" — used in logs and JSON
        keys: list[str],        # list of raw key strings (deduplicated, empty strings removed)
        rate_limit_quarantine_sec: int = 60,    # 429 quarantine duration
        spend_cap_quarantine_sec: int = 0,      # 402/403: 0 = permanent (manual revive only)
    ):
        self.provider = provider
        self.rate_limit_quarantine_sec = rate_limit_quarantine_sec
        self.spend_cap_quarantine_sec = spend_cap_quarantine_sec
        self._lock = threading.Lock()
        self.history = []  # List of dicts: {"timestamp", "alias", "event", "status", "msg"}

        # Deduplicate and filter empty strings
        seen = set()
        clean_keys = []
        for k in keys:
            k = k.strip()
            if k and k not in seen:
                seen.add(k)
                clean_keys.append(k)

        self._entries: list[KeyEntry] = [
            KeyEntry(index=i, key=k, alias=_make_alias(i, k))
            for i, k in enumerate(clean_keys)
        ]
        self._cursor: int = 0   # round-robin pointer

        logger.info(f"[keyrotator] {provider} pool initialized with {len(self._entries)} keys")

    def get_key(self) -> Optional[KeyEntry]:
        """
        Returns the next HEALTHY KeyEntry using round-robin, or None if all are blocked.
        Automatically un-quarantines RATE_LIMITED keys whose timer has expired.
        """
        with self._lock:
            now = time.time()
            total = len(self._entries)
            if total == 0:
                return None

            # Try all entries starting from cursor, wrapping around
            for _ in range(total):
                entry = self._entries[self._cursor]
                self._cursor = (self._cursor + 1) % total

                # Auto-recover RATE_LIMITED keys if timer expired
                if (entry.state == KeyState.RATE_LIMITED
                        and entry.quarantine_until is not None
                        and now >= entry.quarantine_until):
                    entry.state = KeyState.HEALTHY
                    entry.quarantine_until = None
                    logger.info(f"[keyrotator:{self.provider}] {entry.alias} auto-recovered")

                if entry.state == KeyState.HEALTHY:
                    return entry

            logger.error(f"[keyrotator:{self.provider}] All {total} keys are exhausted")
            self._add_history("SYSTEM", "EXHAUSTED", "FAIL", f"All {total} keys are currently unavailable.")
            return None

    def report_error(self, entry: KeyEntry, code: int, message: str = ""):
        """
        Called after an API call fails.
        - 429 → RATE_LIMITED, quarantine for rate_limit_quarantine_sec
        - 402, 403 → SPENT/DEAD, permanent block (manual revive only)
        - Other codes → DEAD, permanent block
        """
        with self._lock:
            entry.total_fail += 1
            entry.last_error_code = code
            entry.last_error_msg = message[:200]  # truncate for safety

            now = time.time()
            if code == 429:
                entry.state = KeyState.RATE_LIMITED
                entry.quarantine_until = now + self.rate_limit_quarantine_sec
                logger.warning(
                    f"[keyrotator:{self.provider}] {entry.alias} → RATE_LIMITED "
                    f"(429, {self.rate_limit_quarantine_sec}s quarantine)"
                )
                self._add_history(entry.alias, "RATE_LIMITED", "FAIL", f"429: {message[:100]}")
            elif code == 402:
                entry.state = KeyState.SPENT
                entry.quarantine_until = None  # permanent
                logger.error(
                    f"[keyrotator:{self.provider}] {entry.alias} → SPENT "
                    f"(402 spend cap, manual revive required)"
                )
                self._add_history(entry.alias, "SPENT", "FAIL", "402: Quota exceeded")
            elif code == 403:
                entry.state = KeyState.DEAD
                entry.quarantine_until = None  # permanent
                logger.error(
                    f"[keyrotator:{self.provider}] {entry.alias} → DEAD "
                    f"(403 auth error, manual revive required)"
                )
            else:
                # Unknown error — treat as dead
                entry.state = KeyState.DEAD
                entry.quarantine_until = None
                logger.error(
                    f"[keyrotator:{self.provider}] {entry.alias} → DEAD "
                    f"(code {code})"
                )

    def report_success(self, entry: KeyEntry):
        with self._lock:
            entry.total_success += 1
            entry.state = KeyState.HEALTHY
            entry.last_error_code = None
            entry.last_error_msg = ""
            entry.success_times.append(time.time())
            self._add_history(entry.alias, "SUCCESS", "OK", "")

    def _add_history(self, alias: str, event: str, status: str, msg: str):
        # Already inside lock from public methods
        self.history.insert(0, {
            "time": time.strftime("%H:%M:%S"),
            "alias": alias,
            "event": event,
            "status": status,
            "msg": msg
        })
        if len(self.history) > 20:
            self.history.pop()

    def revive(self, key_index: int) -> bool:
        """
        Manually revive a SPENT or DEAD key. Called from the dashboard Revive button.
        Returns True if revived, False if index is invalid.
        """
        with self._lock:
            if key_index < 0 or key_index >= len(self._entries):
                return False
            entry = self._entries[key_index]
            prev_state = entry.state
            entry.state = KeyState.HEALTHY
            entry.quarantine_until = None
            logger.info(
                f"[keyrotator:{self.provider}] {entry.alias} manually revived "
                f"(was: {prev_state})"
            )
            return True

    def get_status(self) -> dict:
        """Returns a serializable snapshot for the status endpoint."""
        with self._lock:
            now = time.time()
            keys_status = []
            healthy_count = 0
            
            for e in self._entries:
                # 1. Apply auto-recovery if timer expired
                if (e.state == KeyState.RATE_LIMITED 
                        and e.quarantine_until is not None 
                        and now >= e.quarantine_until):
                    e.state = KeyState.HEALTHY
                    e.quarantine_until = None
                    logger.info(f"[keyrotator:{self.provider}] {e.alias} auto-recovered (via status check)")

                # 2. Calculate TTL for UI
                ttl = None
                if e.state == KeyState.RATE_LIMITED and e.quarantine_until:
                    ttl = max(0, int(e.quarantine_until - now))
                
                # 3. Prune old timestamps (> 60s) for RPM calculation
                e.success_times = [t for t in e.success_times if now - t < 60]
                rpm = len(e.success_times)
                
                if e.state == KeyState.HEALTHY:
                    healthy_count += 1

                keys_status.append({
                    "index":          e.index,
                    "alias":          e.alias,
                    "state":          e.state.value,
                    "ttl_seconds":    ttl,
                    "total_success":  e.total_success,
                    "total_fail":     e.total_fail,
                    "last_error_code": e.last_error_code,
                    "rpm_current":    rpm,
                    "rpm_limit":      15 if "gemini" in self.provider.lower() else 50
                })

            total = len(self._entries)
            return {
                "provider":       self.provider,
                "total_keys":     total,
                "healthy_keys":   healthy_count,
                "health_pct":     round((healthy_count / total * 100) if total else 0, 1),
                "is_contest_mode": os.getenv("CONTEST_MODE", "false").lower() == "true",
                "keys":           keys_status,
                "history":        self.history
            }


class AllKeysExhaustedError(Exception):
    """Raised when get_key() returns None."""
    pass
