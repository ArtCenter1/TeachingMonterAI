from modules.m8_logger import ErrorLogger
from pydantic import BaseModel
import sys
import os


class MockRequest(BaseModel):
    topic: str = "Test Subject"
    persona: str = "Persona A"


def test_failure():
    logger = ErrorLogger("m8_errors.json")
    try:
        print("Starting simulated failure in 'm5_critic'...")
        # Simulate an error
        x = 1 / 0
    except Exception as e:
        print(f"Caught error: {e}")
        logger.log_error(
            run_id="test_run_123",
            exc=e,
            failed_stage="m5_critic",
            request_data={"topic": "Test Subject", "persona": "Persona A"},
        )
        print("Error successfully logged to m8_errors.json")


if __name__ == "__main__":
    test_failure()
