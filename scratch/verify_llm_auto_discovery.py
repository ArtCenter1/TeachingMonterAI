import asyncio
import os
import sys
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to sys.path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.llm_client import LLMClient

async def test_auto_discovery():
    logger.info("Starting LLM Auto-Discovery Verification Test...")
    client = LLMClient()
    
    # We purposely pass a model name that DOES NOT EXIST to trigger the 404/NOT_FOUND logic
    # This should trigger the new 'Auto-discovery' catch block in llm_client.py
    invalid_model = "models/gemini-this-model-does-not-exist-999"
    
    logger.info(f"Testing with intentional invalid model: {invalid_model}")
    
    try:
        # We use a very simple prompt
        response = await client.generate_text(
            prompt="Hello, say 'Auto-discovery worked' if you are alive.",
            model_override=invalid_model
        )
        logger.success(f"Response received successfully: {response}")
        print("\n--- VERIFICATION RESULT ---")
        print("SUCCESS: The LLMClient successfully recovered from an invalid model name and auto-discovered a valid one.")
        print("---------------------------\n")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print("\n--- VERIFICATION RESULT ---")
        print("FAILED: The LLMClient did not recover. Check the logs above for the error.")
        print("---------------------------\n")

if __name__ == "__main__":
    asyncio.run(test_auto_discovery())
