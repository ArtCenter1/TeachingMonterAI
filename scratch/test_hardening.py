import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Add project root to sys.path
sys.path.append(os.getcwd())

from modules.m8_logger import ErrorLogger
from modules.m4_generator import ScriptGenerator
from modules.schemas import StudentModel, StudentLevel, ModalityPreference, ConceptGraph, FactBundle

async def test_log_masking():
    print("\n--- Testing Log Masking ---")
    logger = ErrorLogger("scratch/test_errors.json")
    
    # Dummy keys
    google_key = "AIzaSyCorrectLengthButFakeKey1234567890"
    openrouter_key = "sk-or-v1-abcdefghijklmnopqrstuvwxyz123456"
    
    try:
        # Simulate an exception that includes a key in the message
        raise ValueError(f"Failed with key {google_key}")
    except Exception as e:
        request_data = {
            "google_api_key": google_key,
            "openrouter_api_key": openrouter_key,
            "other_field": "safe data"
        }
        logger.log_error("test_run_123", e, request_data=request_data, failed_stage="test")
    
    import json
    with open("scratch/test_errors.json", "r") as f:
        logs = json.load(f)
        entry = logs[0]
        
        print(f"Error Message: {entry['error_message']}")
        print(f"Sanitized Request: {entry['request']}")
        
        assert "AIzaSy" in entry['error_message'] and "REDACTED" in entry['error_message']
        assert entry['request']['google_api_key'] == "[REDACTED]"
        assert entry['request']['openrouter_api_key'] == "[REDACTED]"
        print("[SUCCESS] Log masking and request sanitization successful!")

async def test_nlm_fallback():
    print("\n--- Testing NLM Fallback Guard ---")
    generator = ScriptGenerator()
    
    # Mock _generate_with_notebooklm to return None
    generator._generate_with_notebooklm = AsyncMock()
    generator._generate_with_notebooklm.return_value = None
    
    # Mock _generate_all to see if it's called
    generator._generate_all = AsyncMock()
    legacy_variant = MagicMock()
    generator._generate_all.return_value = [legacy_variant]
    
    # Mock _select_strategy to return a strategy
    generator._select_strategy = MagicMock(return_value=("Intuition-First", "Exploit"))
    
    # Mock generate to return a variant
    generator.generate = AsyncMock(return_value=legacy_variant)
    
    student_model = StudentModel(
        level=StudentLevel.HIGH_SCHOOL,
        cognitive_load_budget=0.7,
        modality_preference=ModalityPreference.MIXED,
        abstraction_tolerance=0.5
    )
    
    concept_graph = ConceptGraph(nodes=[], total_duration_minutes=0.0)
    fact_bundle = FactBundle(facts=[], metadata={"notebook_id": "test_id"})
    
    # This should now fall through to legacy flow instead of returning [None]
    results = await generator.generate_variants(concept_graph, student_model, fact_bundle)
    
    print(f"Results: {results}")
    assert results == [legacy_variant]
    print("[SUCCESS] NLM fallback guard successful!")

if __name__ == "__main__":
    asyncio.run(test_log_masking())
    asyncio.run(test_nlm_fallback())
