import os
import json
from typing import List
from .schemas import FullScript, ScriptSegment, ConceptGraph, StudentModel, FactBundle
from .utils import extract_json
from .llm_client import LLMClient
from loguru import logger

class ScriptGenerator:
    def __init__(self):
        self.llm = LLMClient()
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

    async def generate(self, concept_graph: ConceptGraph, student_model: StudentModel, fact_bundle: FactBundle, model_override: str = None) -> FullScript:
        if not self.google_api_key and not self.openrouter_api_key:
            logger.warning("No LLM API keys found, falling back to mock data.")
            return self.get_mock_data(concept_graph)

        prompt = f"""
        Generate a full educational script for the following lesson plan.
        Topic: {concept_graph.nodes[0].concept if concept_graph.nodes else "Topic"}
        Student Model: {student_model.json()}
        Facts: {fact_bundle.json()}
        Concept Graph: {concept_graph.json()}

        Requirements:
        1. Narrative Flow: Ensure smooth transitions between concepts.
        2. Visual Cues: For each segment, provide a 'visual_content_spec' detailing what should be on screen.
        3. Pacing: Match student level (vocabulary, complexity).
        4. Citations: Every factual claim must be attributed to a source in the facts.
        5. Hook: First 60 seconds must have a curiosity trigger.
        6. Checks: Include Socratic questions or checks for understanding.

        Return the data as a JSON object matching this schema:
        {{
            "title": "Lesson Title",
            "scaffolding_strategy": "Name of strategy used",
            "hook": "The opening curiosity trigger",
            "segments": [
                {{
                    "segment_id": "string",
                    "concept": "concept name",
                    "narration": "Full narration text",
                    "visual_type": "Animation" | "Diagram" | etc.,
                    "visual_content_spec": "Detailed visual description",
                    "duration_seconds": float,
                    "citations": [{{"claim": "string", "source": "string"}}]
                }}
            ],
            "checks": ["question 1", "question 2"]
        }}
        """

        try:
            response_text = await self.llm.generate_text(
                prompt=prompt,
                model_override=model_override,
                system_instruction="You are an expert educational content creator who turns lesson plans into engaging video scripts."
            )
            data = extract_json(response_text)
            return FullScript(**data)
        except Exception as e:
            logger.error(f"Error generating script: {str(e)}")
            return self.get_mock_data(concept_graph)

    def get_mock_data(self, concept_graph: ConceptGraph) -> FullScript:
        return FullScript(
            title="Introductory Lesson",
            scaffolding_strategy="Intuition-First",
            segments=[
                ScriptSegment(
                    segment_id="seg_0",
                    concept=concept_graph.nodes[0].concept if concept_graph.nodes else "Intro",
                    narration="Welcome to this lesson.",
                    visual_type="Animation",
                    visual_content_spec="Title slide",
                    duration_seconds=30.0
                )
            ],
            hook="Ready to learn?",
            checks=[]
        )
