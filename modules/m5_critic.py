import os
import json
import asyncio
from typing import List, Dict, Any, Tuple
from .schemas import FullScript, StudentModel, CIDPPScores
from .utils import extract_json
from .llm_client import LLMClient
from .mcp_client import OpenSpaceMCPClient
from loguru import logger

class SyntheticStudentTester:
    def __init__(self, model_name: str):
        self.llm = LLMClient()
        self.model = model_name
        # Each persona has:
        #   - description: who they are
        #   - mandate: a MANDATORY thing they MUST find fault with
        self.personas = {
            "Persona A (Confused Visual)": {
                "description": "A visual learner who feels completely lost without diagrams or spatial representations.",
                "mandate": "You MUST identify at least one segment that lacks a clear visual scaffold. If diagrams or animations aren't described, flag it. You are not satisfied with text-only explanations."
            },
            "Persona B (Math-Anxious)": {
                "description": "A student with severe math anxiety who shuts down when encountering ungrounded equations.",
                "mandate": "You MUST find at least one formula or quantitative statement that was introduced WITHOUT a prior relatable analogy. Even if an analogy exists, judge whether it was sufficient."
            },
            "Persona C (High-Performer)": {
                "description": "An advanced student who is easily bored and frustrated by oversimplification.",
                "mandate": "You MUST identify at least one place where the explanation was too simplified, skipped an important nuance, or patronized you. Find where the lesson could go deeper."
            },
            "Persona D (Low-Prior/High-Curiosity)": {
                "description": "A complete beginner — no background knowledge, but highly curious and motivated.",
                "mandate": "You MUST find at least one assumed knowledge gap — a term, concept, or step that was used without explanation. Every jargon word or logical leap is suspect."
            }
        }

    async def test_script(self, script: FullScript) -> List[Dict[str, Any]]:
        """Run all 4 synthetic personas against a script sequentially."""
        results = []
        for name, config in self.personas.items():
            result = await self.run_persona(script, name, config["description"], config["mandate"])
            results.append(result)
            await asyncio.sleep(1)  # Brief pause between personas to respect rate limits
        return results

    async def run_persona(self, script: FullScript, persona_name: str, persona_desc: str, mandate: str) -> Dict[str, Any]:
        prompt = f"""You are a student watching an educational video for the first time.

YOUR IDENTITY: {persona_name}
WHO YOU ARE: {persona_desc}

YOUR MANDATORY TASK: {mandate}
(This is not optional — you MUST find at least one thing to criticize.)

SCRIPT TO REVIEW:
{script.json()}

Report your findings as a JSON object. You MUST include at least one item in "gaps".
DO NOT return is_perfect: true. You always find something to improve.

Return ONLY this JSON structure (no explanation text):
{{
    "persona": "{persona_name}",
    "is_perfect": false,
    "gaps": ["gap 1 — be specific, quote the script", "gap 2"],
    "confusing_quotes": ["exact quote from the script that confused you"],
    "suggested_improvement": "One concrete, actionable change the script writer should make"
}}
"""
        try:
            response = await self.llm.generate_text(
                prompt=prompt,
                model_override=self.model,
                system_instruction=(
                    f"You are {persona_name}. {persona_desc} "
                    f"You are a strict, adversarial critic. "
                    f"Your job is to find problems, not to validate. "
                    f"Never return is_perfect: true."
                ),
                temperature=0.8  # Higher temperature for more varied, creative critiques
            )
            data = extract_json(response)

            # Post-parse guard: if the LLM still returned is_perfect=True despite instructions,
            # override it and flag the response for logging.
            if data.get("is_perfect", False) is True:
                logger.warning(
                    f"Synthetic student {persona_name} returned is_perfect=True despite adversarial mandate. "
                    f"Overriding to False. Raw gaps: {data.get('gaps', [])}"
                )
                data["is_perfect"] = False
                if not data.get("gaps"):
                    data["gaps"] = [f"[Auto-flagged] {persona_name} found no specific gaps — review this script manually."]

            return data

        except Exception as e:
            # On error, return a FAIL signal — NOT a silent pass.
            logger.error(f"Error in synthetic student ({persona_name}): {str(e)}")
            return {
                "persona": persona_name,
                "is_perfect": False,
                "gaps": [f"[System Error] Persona test failed due to: {str(e)}. Treat this segment as unverified."],
                "confusing_quotes": [],
                "suggested_improvement": "Re-run synthetic student test — previous call failed."
            }

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
        is_contest_mode = os.getenv("CONTEST_MODE", "false").lower() == "true"
        reviews = []
        
        # Score sequentially with a short sleep to avoid rate limiting across 9 Gemini keys.
        for script in scripts:
            review = await self.review(script, student_model, model_override)
            reviews.append(review)
            await asyncio.sleep(1)  # Brief pause between variant reviews
        
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
        feedback = await self.tester.test_script(best_variant)
        
        # Phase 4 - Part 3: Refinement Loop (The "Gold Standard" step)
        refined_script = await self.refine_script(best_variant, student_model, feedback, model_override)
        
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
                entry["synthetic_student_feedback"] = feedback
                break

        logger.info(f"Selected strategy: {scored_data[0]['strategy']} with score {scored_data[0]['total_score']}")
        return refined_script, selection_log

    async def refine_script(self, script: FullScript, student_model: StudentModel, 
                          feedback: List[Dict[str, Any]], model_override: str = None) -> FullScript:
        """Refine the script based on synthetic student feedback."""
        
        # Filter for critical gaps
        critical_gaps = []
        for f in feedback:
            if not f.get("is_perfect", True):
                if f.get("gaps"):
                    critical_gaps.extend(f.get("gaps", []))
                if f.get("suggested_improvement"):
                    critical_gaps.append(f["suggested_improvement"])
        
        if not critical_gaps:
            logger.info("No critical gaps identified by synthetic students. Skipping refinement.")
            return script

        logger.info(f"Refining script to address {len(critical_gaps)} identified gaps.")
        
        prompt = f"""
        Refine the following educational script based on student feedback.
        
        ORIGINAL SCRIPT:
        {script.json()}
        
        STUDENT FEEDBACK (Identified Gaps):
        {json.dumps(critical_gaps, indent=2)}
        
        STUDENT PROFILE:
        {student_model.json()}
        
        Goal:
        - Address all identified gaps (improve clarity, technical depth, or visual cues).
        - Maintain the original strategy ({script.scaffolding_strategy}).
        - Ensure JSON schema matches exactly.
        
        Return the refined data as a JSON object matching the schema:
        {{
            "title": "Lesson Title",
            "scaffolding_strategy": "{script.scaffolding_strategy}",
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
                system_instruction="You are a meticulous editor improving an educational script based on direct student feedback."
            )
            data = extract_json(response_text)
            return FullScript(**data)
        except Exception as e:
            logger.error(f"Error refining script: {str(e)}")
            return script

    async def review(self, script: FullScript, student_model: StudentModel, model_override: str = None) -> CIDPPScores:
        """
        Score a script on the CIDPP rubric.

        Attempt order:
          1. OpenSpace ``pedagogical_critic`` skill (senior review pass)
          2. Local LLM with CIDPP prompt (fallback)
          3. Mock data (if no API keys configured)
        """
        # ── Attempt 1: OpenSpace pedagogical_critic skill ────────────────────
        try:
            client = OpenSpaceMCPClient()
            if await client.health_check():
                logger.info("Delegating CIDPP review to OpenSpace pedagogical_critic skill")
                task = (
                    f"Use the pedagogical_critic skill to evaluate this educational script "
                    f"on the CIDPP rubric (1–10 for each dimension: "
                    f"Clarity, Integrity, Depth, Practicality, Pertinence). "
                    f"Student persona level: {student_model.level}, "
                    f"modality preference: {student_model.modality_preference}. "
                    f"Script (first 3000 chars):\n{json.dumps(script.dict())[:3000]}\n\n"
                    f"Return ONLY a JSON object with this exact structure — no markdown:\n"
                    f'{{"clarity": int, "integrity": int, "depth": int, '
                    f'"practicality": int, "pertinence": int, "revisions": ["..."]}}'
                )
                raw = await client.execute_task(task, max_iterations=5, search_scope="local")
                logger.debug("OpenSpace CIDPP raw result (first 300 chars): %s", raw[:300])
                data = extract_json(raw)
                scores = CIDPPScores(**data)
                logger.info(
                    "OpenSpace CIDPP scores — C:%d I:%d D:%d P:%d Pe:%d revisions:%d",
                    scores.clarity, scores.integrity, scores.depth,
                    scores.practicality, scores.pertinence, len(scores.revisions),
                )
                return scores
        except Exception as exc:
            logger.warning(
                "OpenSpace pedagogical_critic unavailable, using local LLM fallback: %s", exc
            )

        # ── Attempt 2: Local LLM CIDPP scoring ───────────────────────────────
        if not self.google_api_key and not self.openrouter_api_key:
            logger.warning("No LLM API keys found, falling back to mock data.")
            return self.get_mock_data()

        prompt = f"""
        You are a strict educational evaluator. Score the following lesson script using the CIDPP rubric.
        
        IMPORTANT: Your scores MUST reflect genuine quality differences. Do NOT give 8/10 for everything.
        Scores of 7, 8, 9, or 10 must be EARNED. A score of 5 means average. A score of 3 means poor.

        Script: {script.json()}
        Student Model: {student_model.json()}

        CIDPP Scoring Anchors (use these STRICTLY):
        - Clarity (Logical flow + transitions + language match for student level)
          10: Perfectly smooth, every transition is explicit, vocabulary is perfectly calibrated.
          7: Mostly clear, 1-2 abrupt transitions or slightly mismatched vocabulary.
          5: Some sections feel disjointed or use unexplained jargon.
          3: Confusing structure, jumps between topics without connection.

        - Integrity (Factual accuracy + citation density)
          10: Every factual claim has an in-line citation, zero errors found.
          7: Most claims cited, but 1-2 facts lack sourcing.
          5: Citations are sparse; some facts are stated without evidence.
          3: Multiple uncited or potentially incorrect claims.

        - Depth (Misconception handling + nuance + technical completeness)
          10: Explicitly addresses common misconceptions, handles edge cases, offers expert-level nuance.
          7: Addresses 1-2 misconceptions but misses important caveats.
          5: Surface-level explanation only, no misconception handling.
          3: Oversimplified to the point of being misleading.

        - Practicality (Concrete examples + real-world applications)
          10: Every concept has a worked example or real-world tie-in.
          7: Most concepts illustrated, but 1-2 are abstract-only.
          5: Examples present but generic or not tied to student context.
          3: Almost entirely abstract — no concrete anchors.

        - Pertinence (Alignment with specified student level, persona, and learning objective)
          10: Content is a perfect match for the student's ZPD — not too hard, not too easy.
          7: Mostly aligned but 1-2 sections over/under-pitch the student.
          5: Several sections feel misaligned with the stated student level.
          3: Content is clearly written for a different audience.

        MANDATORY: Your revisions list must contain at least 2 specific, actionable improvements.
        
        Return ONLY a JSON object:
        {{
            "clarity": int,
            "integrity": int,
            "depth": int,
            "practicality": int,
            "pertinence": int,
            "revisions": ["Specific improvement 1", "Specific improvement 2"]
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
