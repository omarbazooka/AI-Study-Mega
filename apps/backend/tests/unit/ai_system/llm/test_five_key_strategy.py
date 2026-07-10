import pytest
from app.ai_system.services.llm.api_key_pool import APIKeyPool, APIKey
from app.ai_system.services.llm.exceptions import AllKeysExhaustedException

def test_api_key_cooldown_deduplication():
    # Instantiate a clean pool for testing
    pool = APIKeyPool()
    
    # Reset internal structure
    pool._keys = {}
    pool._current_index = {}
    
    # Register identical physical keys under different profile aliases
    physical_key = "gsk_test_physical_value_abc123"
    key1 = APIKey(value=physical_key, alias="KEY_ALIAS_PLANNING", pool=pool)
    key2 = APIKey(value=physical_key, alias="KEY_ALIAS_QUIZ", pool=pool)
    
    pool._keys["PLANNING"] = [key1]
    pool._keys["QUIZ"] = [key2]
    pool._current_index["PLANNING"] = 0
    pool._current_index["QUIZ"] = 0
    
    # Both keys must start as active and available
    assert key1.is_available() is True
    assert key2.is_available() is True
    
    # Trigger a rate limit cooldown on the PLANNING key (alias 1)
    pool.report_rate_limit(key1, cooldown_seconds=60)
    
    # Assert BOTH aliases are now globally cooled down and unavailable
    assert key1.is_available() is False
    assert key2.is_available() is False
    
    # Assert attempts to query the keys raise AllKeysExhaustedException
    with pytest.raises(AllKeysExhaustedException):
        pool.get_available_key("PLANNING")
        
    with pytest.raises(AllKeysExhaustedException):
        pool.get_available_key("QUIZ")
        
    # Clear the global cooldown status (simulate a success call on the same physical key)
    pool.report_success(key2)
    
    # Assert both keys are successfully reactivated
    assert key1.is_available() is True
    assert key2.is_available() is True
