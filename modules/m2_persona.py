import os
import json
from .schemas import StudentModel, StudentLevel, ModalityPreference
from .utils import extract_json
from .llm_client import LLMClient
from loguru import logger


class PersonaParser:
    def __init__(self):
        self.llm = LLMClient()
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

    async def parse(
        self, persona_string: str, model_override: str = None
    ) -> StudentModel:
        if not self.google_api_key and not self.openrouter_api_key:
            logger.warning("No LLM API keys found, falling back to mock data.")
            return self.get_mock_data()

        prompt = f"""
        Extract a structured pedagogical student model from the following persona description:
        "{persona_string}"

        Analyze the description and infer the student's educational background, knowledge level, learning preferences, and potential misconceptions.

        Examples:
        - "High school student learning biology for the first time": level="high_school", knowledge_embedding=["basic science concepts"], misconception_risk={{"photosynthesis": ["plants eat soil"]}}, cognitive_load_budget=0.6, modality_preference="visual", abstraction_tolerance=0.4
        - "University researcher in physics": level="IB", knowledge_embedding=["calculus", "quantum mechanics"], misconception_risk={{"relativity": ["time dilation is illusion"]}}, cognitive_load_budget=0.9, modality_preference="verbal", abstraction_tolerance=0.9
        - "Working professional without STEM background": level="middle_school", knowledge_embedding=["basic arithmetic"], misconception_risk={{"energy": ["energy is matter"]}}, cognitive_load_budget=0.5, modality_preference="mixed", abstraction_tolerance=0.3

        Return the data as a JSON object matching this schema:
        {{
            "level": "IB" | "AP" | "high_school" | "middle_school",
            "knowledge_embedding": ["specific concepts they know"],
            "misconception_risk": {{"concept_name": ["list of common errors they might have"]}},
            "cognitive_load_budget": 0.0 to 1.0 (higher for advanced students),
            "modality_preference": "visual" | "verbal" | "mixed",
            "abstraction_tolerance": 0.0 to 1.0 (higher for abstract thinkers)
        }}

        Be specific and reason step-by-step about implied knowledge and preferences.
        """

        try:
            response_text = await self.llm.generate_text(
                prompt=prompt,
                model_override=model_override,
                system_instruction="You are a pedagogical expert who extracts student mental models.",
            )
            data = extract_json(response_text)
            return StudentModel(**data)
        except Exception as e:
            logger.error(f"Error parsing persona: {str(e)}")
            return self.get_mock_data()

    def get_mock_data(self) -> StudentModel:
        return StudentModel(
            level=StudentLevel.HIGH_SCHOOL,
            knowledge_embedding=["basic algebra"],
            misconception_risk={"forces": ["force causes motion"]},
            cognitive_load_budget=0.7,
            modality_preference=ModalityPreference.MIXED,
            abstraction_tolerance=0.5,
        )
