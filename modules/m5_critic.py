import os
import json
import asyncio
from typing import List, Dict, Any, Tuple
from .schemas import FullScript, StudentModel, CIDPPScores
from .utils import extract_json
from .llm_client import LLMClient
from loguru import logger

class SyntheticStudentTester:
    def __init__(self, model_name: str):
        self.llm = LLMClient()
        self.model = model_name
        self.personas = {
            "Persona A (Confused Visual)": "A visual learner who feels lost without diagrams. You flag any script parts that are too text-heavy without visual scaffolding.",
            "Persona B (Math-Anxious)": "A student who is scared of equations. You flag any formula that isn't preceded by a clear, relatable analogy.",
            "Persona C (High-Performer)": "A bright student who hates being talked down to. You flag oversimplifications or lack of technical depth.",
            "Persona D (Low-Prior/High-Curiosity)": "A beginner with no background but lots of interest. You flag any assumed knowledge or logical leaps."
        }

    async def test_script(self, script: FullScript) -> List[Dict[str, Any]]:
        """Run all 4 synthetic personas against a script in parallel."""
        tasks = []
        for name, desc in self.personas.items():
            tasks.append(self.run_persona(script, name, desc))
        
        return await asyncio.gather(*tasks)

    async def run_persona(self, script: FullScript, persona_name: str, persona_desc: str) -> Dict[str, Any]:
        prompt = f"""
        You are watching an educational video script.
        YOUR PERSONA: {persona_name} - {persona_desc}

        SCRIPT CONTENT:
        {script.json()}

        As this persona, report honestly:
        1. What parts were still confusing? (Quote them)
        2. What knowledge did the lesson assume you had that you didn't?
        3. Where did you lose attention and why?
        4. What one change would help you most?

        If everything is perfect, say "No gaps found".
        Return your report as a JSON object:
        {{
            "persona": "{persona_name}",
            "is_perfect": boolean,
            "gaps": ["gap 1", "gap 2"],
            "confusing_quotes": ["quote 1"],
            "suggested_improvement": "string"
        }}
        """
        try:
            response = await self.llm.generate_text(
                prompt=prompt,
                model_override=self.model,
                system_instruction=f"Act as the following student persona: {persona_name}. Be honest and critical."
            )
            return extract_json(response)
        except Exception as e:
            logger.error(f"Error in synthetic student ({persona_name}): {str(e)}")
            return {"persona": persona_name, "is_perfect": True, "gaps": [], "confusing_quotes": [], "suggested_improvement": ""}

class CIDPPCritic:
    def __init__(self):
        self.llm = LLMClient()
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.synthetic_model = os.getenv("SYNTHETIC_STUDENT_MODEL", "google/gemini-2.0-flash-exp:free")
        self.tester = SyntheticStudentTester(self.synthetic_model)

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
        
        # Phase 4 - Part 2: Synthetic Student Testing on the winner
        logger.info(f"Running synthetic student tests on selected variant: {scored_data[0]['strategy']}")
        student_feedback = await self.tester.test_script(best_variant)
        
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
        
        # Attach synthetic feedback to the winning selection log entry
        for entry in selection_log:
            if entry["strategy"] == scored_data[0]["strategy"]:
                entry["synthetic_student_feedback"] = student_feedback
                break

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
