import notebooklm
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    try:
        async with await notebooklm.NotebookLMClient.from_storage() as client:
            print("Connected to NotebookLM!")
            notebooks = await client.notebooks.list()
            print(f"Found {len(notebooks)} notebooks.")
            for nb in notebooks[:5]:
                print(f"- {nb.title} (ID: {nb.id})")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
