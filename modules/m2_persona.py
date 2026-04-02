import os
import json
import google.generativeai as genai
from .schemas import StudentModel, StudentLevel, ModalityPreference
from .utils import extract_json
from loguru import logger

class PersonaParser:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("models/gemini-2.5-flash")

    async def parse(self, persona_string: str) -> StudentModel:
        if not self.api_key:
            logger.warning("No API key found for PersonaParser, falling back to mock data.")
            return self.get_mock_data()

        prompt = f"""
        Extract a structured pedagogical student model from the following persona description:
        "{persona_string}"

        Return the data as a JSON object matching this schema:
        {{
            "level": "IB" | "AP" | "high_school" | "middle_school",
            "knowledge_embedding": ["string", "string"],  // Implied known concepts
            "misconception_risk": {{"concept_name": ["list of common errors"]}},
            "cognitive_load_budget": 0.0 to 1.0,  // 0.3 = low, 0.7 = high
            "modality_preference": "visual" | "verbal" | "mixed",
            "abstraction_tolerance": 0.0 to 1.0  // 0.0 = concrete, 1.0 = abstract
        }}

        Be specific and reason about implied knowledge (e.g., 'no calculus' implies algebra but not limits).
        """

        try:
            response = self.model.generate_content(prompt)
            data = extract_json(response.text)
            return StudentModel(**data)
        except Exception as e:
            logger.error(f"Error parsing persona with Gemini: {str(e)}")
            return self.get_mock_data()

    def get_mock_data(self) -> StudentModel:
        return StudentModel(
            level=StudentLevel.HIGH_SCHOOL,
            knowledge_embedding=["basic algebra"],
            misconception_risk={"forces": ["force causes motion"]},
            cognitive_load_budget=0.7,
            modality_preference=ModalityPreference.MIXED,
            abstraction_tolerance=0.5
        )
