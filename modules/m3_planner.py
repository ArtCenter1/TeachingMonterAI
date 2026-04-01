import os
import json
import google.generativeai as genai
from .schemas import ConceptNode, ConceptGraph, StudentModel
from loguru import logger

class ConceptPlanner:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")

    async def plan(self, topic: str, student_model: StudentModel) -> ConceptGraph:
        if not self.api_key:
            logger.warning("No API key found for ConceptPlanner, falling back to mock data.")
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
            response = self.model.generate_content(prompt)
            content = response.text.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            
            data = json.loads(content)
            return ConceptGraph(**data)
        except Exception as e:
            logger.error(f"Error planning concepts with Gemini: {str(e)}")
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
