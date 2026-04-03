import os
import json
import asyncio
from typing import List, Dict, Any, Tuple
from .schemas import FullScript, StudentModel, CIDPPScores
from .utils import extract_json
from .llm_client import LLMClient
from loguru import logger

class CIDPPCritic:
    def __init__(self):
        self.llm = LLMClient()
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

    async def score_variants(self, scripts: List[FullScript], student_model: StudentModel, 
                            model_override: str = None) -> Tuple[FullScript, List[Dict[str, Any]]]:
        """Review multiple scripts and select the one with the highest pedagogical score."""
        tasks = []
        for script in scripts:
            tasks.append(self.review(script, student_model, model_override))
        
        reviews = await asyncio.gather(*tasks)
        
        scored_data = []
        for script, review in zip(scripts, reviews):
            # Calculate aggregate score
            total_score = (
                review.clarity + 
                review.integrity + 
                review.depth + 
                review.practicality + 
                review.pertinence
            )
            scored_data.append({
                "script": script,
                "review": review,
                "total_score": total_score,
                "strategy": script.scaffolding_strategy
            })

        # Sort by total score descending
        scored_data.sort(key=lambda x: x["total_score"], reverse=True)
        
        best_variant = scored_data[0]["script"]
        selection_log = [
            {
                "strategy": d["strategy"],
                "total_score": d["total_score"],
                "breakdown": {
                    "clarity": d["review"].clarity,
                    "integrity": d["review"].integrity,
                    "depth": d["review"].depth,
                    "practicality": d["review"].practicality,
                    "pertinence": d["review"].pertinence
                },
                "revisions": d["review"].revisions
            } for d in scored_data
        ]
        
        logger.info(f"Selected strategy: {scored_data[0]['strategy']} with score {scored_data[0]['total_score']}")
        return best_variant, selection_log

    async def review(self, script: FullScript, student_model: StudentModel, model_override: str = None) -> CIDPPScores:
        if not self.google_api_key and not self.openrouter_api_key:
            logger.warning("No LLM API keys found, falling back to mock data.")
            return self.get_mock_data()

        prompt = f"""
        Score this educational lesson script on the CIDPP dimensions for the specified student model.
        Script: {script.json()}
        Student Model: {student_model.json()}

        CIDPP Rubric:
        - Clarity: Logical flow, smooth transitions, understandable language.
        - Integrity: Factual accuracy, citations present for all claims.
        - Depth: Nuance, addressing misconceptions.
        - Practicality: Concrete examples, applications.
        - Pertinence: Alignment with student level and persona.

        Return the scores (1-10) and a list of concrete revision instructions as a JSON object matching this schema:
        {{
            "clarity": int,
            "integrity": int,
            "depth": int,
            "practicality": int,
            "pertinence": int,
            "revisions": ["instruction 1", "instruction 2"]
        }}
        """

        try:
            response_text = await self.llm.generate_text(
                prompt=prompt,
                model_override=model_override,
                system_instruction="You are a rigorous educational critic who scores scripts based on clarity, integrity, depth, practicality, and pertinence (CIDPP)."
            )
            data = extract_json(response_text)
            return CIDPPScores(**data)
        except Exception as e:
            logger.error(f"Error reviewing script: {str(e)}")
            return self.get_mock_data()

    def get_mock_data(self) -> CIDPPScores:
        return CIDPPScores(
            clarity=8,
            integrity=10,
            depth=7,
            practicality=7,
            pertinence=8,
            revisions=[]
        )
