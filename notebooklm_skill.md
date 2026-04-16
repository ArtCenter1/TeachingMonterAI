# NotebookLM Sourcing Skill

**Name:** notebooklm
**Description:** Research educational topics using Google NotebookLM to provide grounded facts with citations from authoritative sources.

**Parameters:**
- topic (string): The educational topic to research
- audience_level (string): Target audience (e.g., "AP/IB secondary education")
- source_hint (string): Preferred authoritative sources (e.g., "IB Biology textbook, AP Biology CED")

**Output:** JSON with facts array containing claim, citation, confidence.

**Implementation:**
Uses notebooklm-py library to create/query a notebook with Wikipedia and specified sources, then extracts pedagogical facts.

**Code Example:**
```python
import asyncio
from notebooklm import NotebookLMClient

async def source_topic(topic: str, source_hint: str) -> dict:
    async with NotebookLMClient.from_storage() as client:
        # Create or find notebook
        notebooks = await client.notebooks.list()
        nb = next((n for n in notebooks if "TeachingMonster_Sourcing" in n.title), None)
        if not nb:
            nb = await client.notebooks.create("TeachingMonster_Sourcing")
            # Seed with sources if needed

        # Query for facts
        query = f"Provide 5 facts about '{topic}' for {audience_level} with citations."
        result = await client.chat.ask(nb.id, query)

        # Parse and return JSON
        return {
            "facts": [
                {"claim": result.answer, "citation": "Google NotebookLM", "confidence": 0.9}
            ]
        }
```

**Requirements:** notebooklm-py installed, auth configured.