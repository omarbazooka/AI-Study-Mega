import pytest
from app.ai_system.services.llm.api_key_pool import APIKey, APIKeyPool
from app.ai_system.services.llm.exceptions import AllKeysExhaustedException

def test_api_key_availability():
    pool = APIKeyPool()
    key = APIKey(value="test_val", alias="TEST_KEY", pool=pool)
    assert key.is_available() is True

    # Check active status
    key.is_active = False
    assert key.is_available() is False
    key.is_active = True

    # Check cooldown
    key.set_cooldown(10)
    assert key.is_available() is False

    key.clear_cooldown()
    assert key.is_available() is True

def test_key_pool_exhaustion():
    import os
    from unittest.mock import patch
    
    with patch.dict(os.environ, {"LLM_ALLOW_CROSS_GROUP_KEY_BORROWING": "false"}):
        pool = APIKeyPool()
        
        # Override keys in pool manually for testing
        pool._keys["FAST"] = [
            APIKey(value="key1", alias="FAST_1", pool=pool),
            APIKey(value="key2", alias="FAST_2", pool=pool)
        ]

        key_1 = pool.get_available_key("FAST")
        assert key_1.value == "key1"

        # Put both keys on cooldown
        pool.report_rate_limit(pool._keys["FAST"][0], cooldown_seconds=60)
        pool.report_rate_limit(pool._keys["FAST"][1], cooldown_seconds=60)

        with pytest.raises(AllKeysExhaustedException):
            pool.get_available_key("FAST")

def test_key_pool_round_robin_rotation():
    pool = APIKeyPool()
    pool._keys["FAST"] = [
        APIKey(value="key1", alias="FAST_1", pool=pool),
        APIKey(value="key2", alias="FAST_2", pool=pool)
    ]
    pool._current_index["FAST"] = 0

    # First is available, rotating pointer moves to 1
    key1 = pool.get_available_key("FAST")
    assert key1.value == "key1"
    assert pool._current_index["FAST"] == 1

    # Second is available, rotating pointer moves to 0
    key2 = pool.get_available_key("FAST")
    assert key2.value == "key2"
    assert pool._current_index["FAST"] == 0

    # Cycles back to first key
    key3 = pool.get_available_key("FAST")
    assert key3.value == "key1"
    assert pool._current_index["FAST"] == 1
