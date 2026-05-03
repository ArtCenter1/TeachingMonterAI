import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

async def test_search():
    api_key = os.getenv("SEARCH_API_KEY")
    cx = os.getenv("SEARCH_CX")
    topic = "Quantum Computing"
    
    search_query = f"{topic} educational concepts site:.edu"
    search_url = "https://www.googleapis.com/customsearch/v1"
    search_params = {"key": api_key, "cx": cx, "q": search_query, "num": 5}

    logger.info(f"Testing Google Search with Key: {api_key[:8]}... CX: {cx}")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(search_url, params=search_params) as response:
            status = response.status
            body = await response.text()
            if status == 200:
                logger.success("Search successful!")
                print(body[:500])
            else:
                logger.error(f"Search failed with status {status}")
                print(body)

if __name__ == "__main__":
    asyncio.run(test_search())
