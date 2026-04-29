import asyncio
import os
import sys
from loguru import logger

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import nlm_studio

async def run_smoke_test():
    logger.info("Starting NLM Studio Smoke Test...")
    
    # 1. Preflight
    success = await nlm_studio.preflight_check()
    if not success:
        logger.error("Preflight failed. Check NLM_SLIDES_ENABLED/NLM_AUDIO_ENABLED and ~/.notebooklm/storage_state.json")
        return

    logger.success("Preflight passed!")

    # 2. Ensure Notebook
    notebook_id = await nlm_studio.ensure_notebook("Smoke Test Topic", "Computer Science")
    if not notebook_id:
        logger.error("Failed to create notebook.")
        return
    
    logger.success(f"Notebook created: {notebook_id}")

    # 3. Add Source
    test_text = "The Turing Machine is a mathematical model of computation that defines an abstract machine."
    await nlm_studio.add_sources_to_notebook(notebook_id, [test_text])
    logger.success("Source added.")

    # 4. Generate Quiz (Lightweight)
    logger.info("Testing Quiz Generation...")
    quiz = await nlm_studio.generate_quiz(notebook_id)
    if quiz:
        logger.success(f"Quiz generated: {len(quiz)} questions found.")
        for q in quiz[:1]:
            logger.info(f"Sample Q: {q['question']}")
    else:
        logger.warning("No quiz generated (might be expected if sources are too small or NLM is slow).")

    # 5. Generate Slide (Optional, takes time)
    if os.getenv("NLM_TEST_SLIDES", "false").lower() == "true":
        logger.info("Testing Slide Generation (this may take minutes)...")
        slide_path = await nlm_studio.generate_slides(
            notebook_id, 
            "Turing Machine", 
            "smoke_1", 
            "An abstract machine that manipulates symbols on a strip of tape.",
            "temp/output"
        )
        if slide_path:
            logger.success(f"Slide generated: {slide_path}")
        else:
            logger.error("Slide generation failed.")

    logger.success("NLM Smoke Test Completed.")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
