import os
import json
import google.generativeai as genai
from .schemas import FactBundle
from loguru import logger

class SourcingModule:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")

    async def source(self, topic: str) -> FactBundle:
        if not self.api_key:
            logger.warning("No API key found for SourcingModule, falling back to mock data.")
            return self.get_mock_data(topic)

        prompt = f"""
        Provide detailed, authoritative educational facts about the topic: "{topic}".
        Focus on secondary education (AP/IB level). 
        Identify core concepts, key formulas (if applicable), and standard definitions.
        
        Return the data as a JSON object matching this schema:
        {{
            "facts": [
                {{
                    "claim": "string",
                    "citation": "string (e.g. Textbook, Scientific Law)",
                    "confidence": 0.0 to 1.0
                }}
            ],
            "study_guide_url": "string (optional URL for further reading)"
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            content = response.text.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            
            data = json.loads(content)
            return FactBundle(**data)
        except Exception as e:
            logger.error(f"Error sourcing facts with Gemini: {str(e)}")
            return self.get_mock_data(topic)

    def get_mock_data(self, topic: str) -> FactBundle:
        return FactBundle(
            facts=[{"claim": f"Core concepts of {topic} involve fundamental principles.", "citation": "Educational Standard", "confidence": 0.9}],
            study_guide_url="https://example.com/guide"
        )
