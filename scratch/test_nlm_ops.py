import asyncio
import os
from notebooklm import NotebookLMClient
from loguru import logger

async def test_nlm_ops():
    logger.info("Testing NLM Client from storage...")
    try:
        async with await NotebookLMClient.from_storage() as client:
            logger.info("Listing notebooks...")
            notebooks = await client.notebooks.list()
            logger.info(f"Found {len(notebooks)} notebooks.")
            
            logger.info("Attempting to create a test notebook...")
            title = "Smoke Test Notebook " + str(int(asyncio.get_event_loop().time()))
            nb = await client.notebooks.create(title=title)
            nb_id = getattr(nb, "id", None) or getattr(nb, "notebook_id", None)
            logger.success(f"Successfully created notebook: {title} (ID: {nb_id})")
            
            # Clean up if possible (though create is the main hurdle)
    except Exception as e:
        logger.error(f"NLM Operation failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_nlm_ops())
