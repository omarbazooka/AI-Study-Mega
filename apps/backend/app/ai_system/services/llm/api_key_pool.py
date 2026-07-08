import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from .config import LLMConfig
from .exceptions import AllKeysExhaustedException

logger = logging.getLogger(__name__)

class APIKey:
    """Represents an individual API key with tracking metadata."""
    def __init__(self, value: str, alias: str):
        self.value: str = value
        self.alias: str = alias
        self.cooldown_until: Optional[datetime] = None
        self.is_active: bool = True
        self.usage_count: int = 0
        self.failure_count: int = 0

    def is_available(self) -> bool:
        """Returns True if the key is active and not cooling down."""
        if not self.is_active:
            return False
        if self.cooldown_until is not None:
            now = datetime.now(timezone.utc)
            if now < self.cooldown_until:
                return False
        return True

    def set_cooldown(self, seconds: int):
        """Puts the key on cooldown for the specified number of seconds."""
        self.cooldown_until = datetime.now(timezone.utc) + timedelta(seconds=seconds)

    def clear_cooldown(self):
        """Clears the key's cooldown status."""
        self.cooldown_until = None


class APIKeyPool:
    """Thread-safe pool that manages key rotation via round-robin, cooldown, and status tracking."""
    def __init__(self):
        self._lock = threading.Lock()
        self._keys: Dict[str, List[APIKey]] = {}
        self._current_index: Dict[str, int] = {}
        self._initialize_pool()

    def _initialize_pool(self):
        """Loads and wraps all API keys defined in LLMConfig."""
        groups = ["FAST", "REASONING", "SUMMARY", "VERIFIER", "EMBEDDING"]
        for group in groups:
            raw_keys = LLMConfig.get_keys_for_group(group)
            self._keys[group] = [
                APIKey(value=key, alias=f"{group}_KEY_{i+1}")
                for i, key in enumerate(raw_keys)
            ]
            self._current_index[group] = 0
            logger.info(f"Initialized {len(self._keys[group])} keys for group '{group}'.")

    def get_available_key(self, group: str) -> APIKey:
        """
        Retrieves the next available key for the given group using round-robin.
        If all keys are cooled down/disabled, raises AllKeysExhaustedException.
        """
        group = group.upper()
        with self._lock:
            if group not in self._keys or not self._keys[group]:
                raise AllKeysExhaustedException(group)

            keys = self._keys[group]
            num_keys = len(keys)
            start_index = self._current_index.get(group, 0)

            # Try to find an available key starting from the last index (round-robin)
            for i in range(num_keys):
                candidate_idx = (start_index + i) % num_keys
                key = keys[candidate_idx]
                if key.is_available():
                    # Move the pointer to the next key for subsequent calls
                    self._current_index[group] = (candidate_idx + 1) % num_keys
                    key.usage_count += 1
                    return key

            raise AllKeysExhaustedException(group)

    def report_rate_limit(self, key: APIKey, cooldown_seconds: Optional[int] = None):
        """Marks a key as rate-limited, sets its cooldown period, and increments failure count."""
        seconds = cooldown_seconds if cooldown_seconds is not None else LLMConfig.API_KEY_COOLDOWN_SECONDS
        with self._lock:
            key.set_cooldown(seconds)
            key.failure_count += 1
            logger.warning(
                f"API Key {key.alias} was marked as rate-limited. Cooldown set for {seconds} seconds. "
                f"Total failures: {key.failure_count}"
            )

    def report_success(self, key: APIKey):
        """Clears cooldown status upon successful LLM call."""
        with self._lock:
            key.clear_cooldown()

    def disable_key(self, key: APIKey):
        """Disables a key completely due to permanent errors (e.g., invalid token)."""
        with self._lock:
            key.is_active = False
            key.failure_count += 1
            logger.error(f"API Key {key.alias} has been disabled due to fatal provider error.")

    def enable_key(self, key: APIKey):
        """Enables a key."""
        with self._lock:
            key.is_active = True
            key.clear_cooldown()
            logger.info(f"API Key {key.alias} has been manually enabled.")

    def get_all_keys(self, group: str) -> List[APIKey]:
        """Helper to get keys in group (useful for tests/debugging)."""
        return self._keys.get(group.upper(), [])


# Singleton instance of the APIKeyPool
api_key_pool = APIKeyPool()
