import time
import logging
import asyncio
from typing import Dict

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """
    A reusable, concurrency-safe circuit breaker for tracking service or model health.
    Transitions: Closed -> Open -> Half-Open -> Closed/Open
    """
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        
        # State stored per key (e.g., model name or provider name)
        # Structure: {key: {"state": "CLOSED"|"OPEN", "failures": int, "last_failure_time": float}}
        self._states: Dict[str, dict] = {}
        self._locks_by_loop = {}

    def _get_lock(self) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            if not hasattr(self, "_fallback_lock"):
                self._fallback_lock = asyncio.Lock()
            return self._fallback_lock
            
        if loop not in self._locks_by_loop:
            self._locks_by_loop[loop] = asyncio.Lock()
        return self._locks_by_loop[loop]

    async def _get_state(self, key: str) -> dict:
        if key not in self._states:
            self._states[key] = {
                "state": "CLOSED",
                "failures": 0,
                "last_failure_time": 0.0
            }
        return self._states[key]

    async def allow_request(self, key: str) -> bool:
        """
        Checks if a request to the given key is allowed.
        If the circuit is open and the cooldown has passed, transitions to half-open.
        """
        async with self._get_lock():
            state_info = await self._get_state(key)
            if state_info["state"] == "OPEN":
                now = time.perf_counter()
                elapsed = now - state_info["last_failure_time"]
                if elapsed >= self.cooldown_seconds:
                    logger.info(f"[CIRCUIT BREAKER] Key '{key}' cooldown elapsed. Transitioning from OPEN to HALF-OPEN.")
                    state_info["state"] = "HALF-OPEN"
                    return True
                return False
            return True

    async def record_success(self, key: str):
        """Records a successful call, resetting failures and closing the circuit."""
        async with self._get_lock():
            state_info = await self._get_state(key)
            if state_info["state"] != "CLOSED":
                logger.info(f"[CIRCUIT BREAKER] Key '{key}' call succeeded. Closing circuit.")
            state_info["state"] = "CLOSED"
            state_info["failures"] = 0

    async def record_failure(self, key: str):
        """Records a failure. If failures exceed threshold, opens the circuit."""
        async with self._get_lock():
            state_info = await self._get_state(key)
            state_info["failures"] += 1
            state_info["last_failure_time"] = time.perf_counter()
            
            if state_info["failures"] >= self.failure_threshold:
                if state_info["state"] != "OPEN":
                    logger.warning(
                        f"[CIRCUIT BREAKER] Key '{key}' reached {state_info['failures']} failures. "
                        f"Opening circuit for {self.cooldown_seconds}s."
                    )
                state_info["state"] = "OPEN"

# Singleton registry for central tracking
circuit_breaker_registry = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)

