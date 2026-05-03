import asyncio
from notebooklm import NotebookLMClient
import logging

logging.basicConfig(level=logging.DEBUG)

async def main():
    try:
        async with await NotebookLMClient.from_storage() as client:
            print("Connected. Listing notebooks...")
            nbs = await client.notebooks.list()
            print(f"Found {len(nbs)} notebooks.")
            
            print("Creating notebook...")
            nb = await client.notebooks.create(title="Test Notebook Connection")
            nb_id = getattr(nb, "id", None) or getattr(nb, "notebook_id", None)
            print(f"Notebook ID: {nb_id}")
            
            print("Adding source...")
            await client.sources.add_text(nb_id, "Test Source", "This is a test document content", wait=True)
            print("Source added!")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
