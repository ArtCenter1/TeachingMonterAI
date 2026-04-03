import os
import json
from .schemas import ConceptNode, ConceptGraph, StudentModel
from .utils import extract_json
from .llm_client import LLMClient
from loguru import logger

class ConceptPlanner:
    def __init__(self):
        self.llm = LLMClient()
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

    async def plan(self, topic: str, student_model: StudentModel, model_override: str = None) -> ConceptGraph:
        if not self.google_api_key and not self.openrouter_api_key:
            logger.warning("No LLM API keys found, falling back to mock data.")
            return self.get_mock_data(topic)

        prompt = f"""
        Plan a lesson sequence for the topic: "{topic}".
        Student Model: {student_model.json()}

        Create an ordered sequence of concepts following pedagogical scaffolding (simple to complex).
        Ensure every concept's prerequisites are met by previous nodes or the student's knowledge.
        Target the Zone of Proximal Development (ZPD).

        Return the data as a JSON object matching this schema:
        {{
            "nodes": [
                {{
                    "concept": "Name of concept",
                    "prerequisites": ["list", "of", "names"],
                    "misconceptions": ["list", "of", "common", "errors"],
                    "visual_type": "Animation" | "Flowchart" | "Diagram" | "Derivation",
                    "duration_minutes": float
                }}
            ],
            "total_duration_minutes": float
        }}
        
        Keep total_duration_minutes <= 25.
        """

        try:
            response_text = await self.llm.generate_text(
                prompt=prompt,
                model_override=model_override,
                system_instruction="You are a pedagogical lesson planner who specializes in concept mapping and scaffolding."
            )
            data = extract_json(response_text)
            return ConceptGraph(**data)
        except Exception as e:
            logger.error(f"Error planning concepts: {str(e)}")
            return self.get_mock_data(topic)

    def get_mock_data(self, topic: str) -> ConceptGraph:
        return ConceptGraph(
            nodes=[
                ConceptNode(
                    concept=f"Intro to {topic}",
                    prerequisites=[],
                    misconceptions=[],
                    visual_type="Animation",
                    duration_minutes=2.0
                )
            ],
            total_duration_minutes=2.0
        )
