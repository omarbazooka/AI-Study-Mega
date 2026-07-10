import logging
import threading
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

def _hash_key(key: str) -> str:
    """Helper to calculate SHA-256 hash of API key for safe logging and comparison."""
    if not key:
        return ""
    return hashlib.sha256(key.strip().encode("utf-8")).hexdigest()


class APIKey:
    """Represents an individual API key with tracking metadata."""
    def __init__(self, value: str, alias: str, pool: 'APIKeyPool'):
        self.value: str = value.strip()
        self.alias: str = alias
        self.pool: 'APIKeyPool' = pool
        self.is_active: bool = True
        self.usage_count: int = 0
        self.failure_count: int = 0

    def is_available(self) -> bool:
        """Returns True if the key is active and not cooling down globally."""
        if not self.is_active:
            return False
            
        # Check global cooldown for this physical key
        cooldown_until = self.pool.get_physical_cooldown(self.value)
        if cooldown_until is not None:
            now = datetime.now(timezone.utc)
            if now < cooldown_until:
                return False
        return True

    def set_cooldown(self, seconds: int):
        """Puts the physical key on global cooldown."""
        self.pool.set_physical_cooldown(self.value, seconds)

    def clear_cooldown(self):
        """Clears the global cooldown for this physical key."""
        self.pool.clear_physical_cooldown(self.value)


class APIKeyPool:
    """Thread-safe pool that manages key rotation, deduplication, and physical cooldown tracking."""
    def __init__(self):
        self._lock = threading.RLock()
        self._keys: Dict[str, List[APIKey]] = {}
        self._current_index: Dict[str, int] = {}
        
        # Track cooldowns by physical key hash to deduplicate across pools
        self._physical_cooldowns: Dict[str, datetime] = {}
        
        self._initialize_pool()

    def _initialize_pool(self):
        """Loads and wraps all API keys from settings."""
        # 5 Profile Map
        group_attrs = {
            "PLANNING": settings.GROQ_PLANNING_API_KEY,
            "MEMORY_MAP": settings.GROQ_MEMORY_MAP_API_KEY,
            "EXECUTION_REDUCE": settings.GROQ_EXECUTION_REDUCE_API_KEY,
            "VERIFICATION": settings.GROQ_VERIFICATION_API_KEY,
            "QUIZ": settings.GROQ_QUIZ_API_KEY,
        }
        
        default_key = settings.GROQ_DEFAULT_API_KEY.strip()
        
        for group, primary_key in group_attrs.items():
            primary_key = primary_key.strip()
            key_val = primary_key if primary_key else default_key
            
            if key_val:
                self._keys[group] = [
                    APIKey(value=key_val, alias=f"GROQ_{group}_KEY", pool=self)
                ]
            else:
                self._keys[group] = []
                logger.warning(f"No API key configured for profile '{group}' and no default fallback key.")
                
            self._current_index[group] = 0
            logger.info(f"Initialized {len(self._keys[group])} keys for profile group '{group}'.")

        # Backward compatibility bridge for old tests (FAST, REASONING, SUMMARY, VERIFIER)
        old_groups = ["FAST", "REASONING", "SUMMARY", "VERIFIER", "EMBEDDING"]
        for old_g in old_groups:
            # We map them to the corresponding new profiles
            mapped_p = self._map_old_group(old_g)
            if mapped_p in self._keys:
                self._keys[old_g] = self._keys[mapped_p]
                self._current_index[old_g] = 0

    def _map_old_group(self, old_group: str) -> str:
        old_g = old_group.upper()
        mapping = {
            "FAST": "PLANNING",
            "REASONING": "EXECUTION_REDUCE",
            "SUMMARY": "MEMORY_MAP",
            "VERIFIER": "VERIFICATION",
            "EMBEDDING": "MEMORY_MAP"
        }
        return mapping.get(old_g, "EXECUTION_REDUCE")

    def get_physical_cooldown(self, key_val: str) -> Optional[datetime]:
        """Returns the global cooldown timestamp for a physical key value."""
        kh = _hash_key(key_val)
        with self._lock:
            return self._physical_cooldowns.get(kh)

    def set_physical_cooldown(self, key_val: str, seconds: int):
        """Sets the global cooldown timestamp for a physical key value."""
        kh = _hash_key(key_val)
        until = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        with self._lock:
            self._physical_cooldowns[kh] = until

    def clear_physical_cooldown(self, key_val: str):
        """Clears the global cooldown for a physical key value."""
        kh = _hash_key(key_val)
        with self._lock:
            self._physical_cooldowns.pop(kh, None)

    def get_available_key(self, group: str) -> APIKey:
        """
        Retrieves the next available key for the given group.
        If all keys are cooled down/disabled, raises AllKeysExhaustedException.
        """
        group = group.upper()
        with self._lock:
            from .exceptions import AllKeysExhaustedException
            if group not in self._keys or not self._keys[group]:
                raise AllKeysExhaustedException(group)

            keys = self._keys[group]
            num_keys = len(keys)
            start_index = self._current_index.get(group, 0)

            for i in range(num_keys):
                candidate_idx = (start_index + i) % num_keys
                key = keys[candidate_idx]
                if key.is_available():
                    self._current_index[group] = (candidate_idx + 1) % num_keys
                    key.usage_count += 1
                    return key

            raise AllKeysExhaustedException(group)

    def report_rate_limit(self, key: APIKey, cooldown_seconds: Optional[int] = None):
        """Marks a key as rate-limited globally."""
        from .config import LLMConfig
        seconds = cooldown_seconds if cooldown_seconds is not None else LLMConfig.API_KEY_COOLDOWN_SECONDS
        key.set_cooldown(seconds)
        with self._lock:
            key.failure_count += 1
            logger.warning(
                f"API Key {key.alias} (Hash: {_hash_key(key.value)[:10]}) was marked as rate-limited. "
                f"Cooldown set for {seconds} seconds."
            )

    def report_success(self, key: APIKey):
        """Clears cooldown status upon successful LLM call."""
        key.clear_cooldown()

    def disable_key(self, key: APIKey):
        """Disables a key completely due to permanent errors."""
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
        """Helper to get keys in group."""
        return self._keys.get(group.upper(), [])


# Singleton instance of the APIKeyPool
api_key_pool = APIKeyPool()
