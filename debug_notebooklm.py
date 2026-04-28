import notebooklm
import asyncio

async def main():
    try:
        client = await notebooklm.NotebookLMClient.from_storage()
        print(f"Client properties: {dir(client)}")
        # Check specific modules
        print(f"Notebooks: {dir(client.notebooks)}")
        print(f"Sources: {dir(client.sources)}")
        print(f"Artifacts: {dir(client.artifacts)}")
        print(f"Chat: {dir(client.chat)}")
        await client.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
