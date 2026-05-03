import httpx
import anyio
import logging
logging.basicConfig(level=logging.DEBUG)

async def main():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://notebooklm.google.com/")
            print("Status code:", resp.status_code)
    except Exception as e:
        import traceback
        traceback.print_exc()

anyio.run(main)
