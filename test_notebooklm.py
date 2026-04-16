import asyncio
from modules.mcp_client import OpenSpaceMCPClient


async def test_notebooklm():
    client = OpenSpaceMCPClient("http://openspace-evolution-engine:8081/mcp")
    topic = "Photosynthesis"
    source_hint = "IB Biology textbook, AP Biology CED, Khan Academy"

    task = f'Research the educational topic \'{topic}\' for a secondary education audience (AP/IB level). Use the following as primary authoritative sources: {source_hint}. Return a JSON object with this exact structure — no markdown:\n{{\n  "facts": [\n    {{"claim": "The factual statement", "citation": "Source title / URL / page", "confidence": 0.9}}\n  ],\n  "study_guide_url": null\n}}\nProvide at least 3 unique, verifiable facts with citations. Do NOT hallucinate citations.'

    print("Testing NotebookLM via OpenSpace MCP...")
    try:
        result = await client.execute_task(task, max_iterations=5, search_scope="local")
        print("Success! Result:")
        print(result[:500])  # First 500 chars
        if "facts" in result:
            print("Contains facts - skill working")
        else:
            print("No facts found - may need manual installation")
    except Exception as e:
        print(f"Failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_notebooklm())
