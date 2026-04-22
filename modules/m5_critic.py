import os
import json
import asyncio
from typing import List, Dict, Any, Tuple
from .schemas import FullScript, StudentModel, CIDPPScores
from .utils import extract_json
from .llm_client import LLMClient
from loguru import logger


class SyntheticStudentTester:
    """Runs 4 synthetic student personas in a SINGLE batched LLM call.

    Previous implementation made 4 separate LLM calls (one per persona),
    which exhausted the 9-key Gemini pool during the critic stage.
    Batching into 1 call reduces total critic-stage LLM calls from ~8 to ~5.
    """

    def __init__(self, model_name: str):
        self.llm = LLMClient()
        self.model = model_name
        self.personas = {
            "Persona A (Confused Visual)": {
                "description": "A visual learner who feels completely lost without diagrams or spatial representations.",
                "mandate": "Identify segments lacking clear visual scaffolds. Flag text-only explanations.",
            },
            "Persona B (Math-Anxious)": {
                "description": "A student with severe math anxiety who shuts down when encountering ungrounded equations.",
                "mandate": "Find formulas or quantitative statements introduced WITHOUT a prior relatable analogy.",
            },
            "Persona C (High-Performer)": {
                "description": "An advanced student who is easily bored and frustrated by oversimplification.",
                "mandate": "Identify places where the explanation was too simplified or skipped important nuance.",
            },
            "Persona D (Low-Prior/High-Curiosity)": {
                "description": "A complete beginner — no background knowledge, but highly curious and motivated.",
                "mandate": "Find assumed knowledge gaps — terms, concepts, or steps used without explanation.",
            },
        }

    async def test_script(self, script: FullScript) -> List[Dict[str, Any]]:
        """Run all 4 synthetic personas in ONE batched LLM call to conserve API keys."""
        # Build the persona block for the prompt
        persona_block = ""
        for name, config in self.personas.items():
            persona_block += (
                f"\n### {name}\n"
                f"- Who: {config['description']}\n"
                f"- Mandate: {config['mandate']}\n"
            )

        # Truncate script to ~3000 chars to stay within token budget
        script_text = script.json()[:3000]

        prompt = f"""You are simulating 4 different students who just watched an educational video.
Each student has a distinct perspective and MUST find specific problems.

THE 4 STUDENTS:
{persona_block}

SCRIPT TO REVIEW:
{script_text}

CRITICAL RULES:
- Each persona MUST report at least 2 gaps and 1 confusing quote.
- NEVER set is_perfect to true for any persona.
- Be specific — quote the script where possible.

Return ONLY a JSON array with exactly 4 objects (one per persona):
[
  {{
    "persona": "Persona A (Confused Visual)",
    "is_perfect": false,
    "gaps": ["specific gap 1", "specific gap 2"],
    "confusing_quotes": ["exact quote from script"],
    "suggested_improvement": "One concrete fix"
  }},
  {{
    "persona": "Persona B (Math-Anxious)",
    "is_perfect": false,
    "gaps": ["specific gap 1", "specific gap 2"],
    "confusing_quotes": ["exact quote from script"],
    "suggested_improvement": "One concrete fix"
  }},
  {{
    "persona": "Persona C (High-Performer)",
    "is_perfect": false,
    "gaps": ["specific gap 1", "specific gap 2"],
    "confusing_quotes": ["exact quote from script"],
    "suggested_improvement": "One concrete fix"
  }},
  {{
    "persona": "Persona D (Low-Prior/High-Curiosity)",
    "is_perfect": false,
    "gaps": ["specific gap 1", "specific gap 2"],
    "confusing_quotes": ["exact quote from script"],
    "suggested_improvement": "One concrete fix"
  }}
]
"""

        try:
            response = await self.llm.generate_text(
                prompt=prompt,
                model_override=self.model,
                system_instruction=(
                    "You are 4 different students reviewing the same lesson. "
                    "You are extremely strict adversarial critics who ALWAYS find faults. "
                    "Each persona has a unique lens. None of them ever finds content perfect. "
                    "Return a JSON array of 4 objects — nothing else."
                ),
                temperature=0.9,
                model_size="medium",
            )
            raw_data = extract_json(response)

            # Handle both list and single-object responses
            if isinstance(raw_data, dict):
                raw_data = [raw_data]

            results = []
            persona_names = list(self.personas.keys())
            for i, entry in enumerate(raw_data[:4]):
                # Enforce persona name alignment
                expected_name = persona_names[i] if i < len(persona_names) else f"Persona {i}"
                entry["persona"] = entry.get("persona", expected_name)

                # Post-parse guard: force is_perfect=False
                if entry.get("is_perfect", False) is True:
                    logger.warning(
                        f"Synthetic student {entry['persona']} returned is_perfect=True. Overriding."
                    )
                    entry["is_perfect"] = False
                    if not entry.get("gaps"):
                        entry["gaps"] = [
                            f"[Auto-flagged] {entry['persona']} found no specific gaps — review manually."
                        ]
                results.append(entry)

            # If LLM returned fewer than 4, pad with error entries
            while len(results) < 4:
                idx = len(results)
                name = persona_names[idx] if idx < len(persona_names) else f"Persona {idx}"
                results.append({
                    "persona": name,
                    "is_perfect": False,
                    "gaps": [f"[Auto-padded] Batched call returned only {len(raw_data)} responses."],
                    "confusing_quotes": [],
                    "suggested_improvement": "Run synthetic test again for full coverage.",
                })

            logger.info(f"Batched synthetic student test: {len(results)} personas in 1 LLM call")
            return results

        except Exception as e:
            logger.error(f"Batched synthetic student test failed: {str(e)}")
            # Return fail signals for all 4 personas
            return [
                {
                    "persona": name,
                    "is_perfect": False,
                    "gaps": [
                        f"[System Error] Batched test failed: {str(e)}. Treat as unverified."
                    ],
                    "confusing_quotes": [],
                    "suggested_improvement": "Re-run synthetic student test.",
                }
                for name in self.personas.keys()
            ]


class CIDPPCritic:
    def __init__(self):
        self.llm = LLMClient()
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.synthetic_model = os.getenv(
            "SYNTHETIC_STUDENT_MODEL", "google/gemini-2.0-flash-exp:free"
        )
        self.tester = SyntheticStudentTester(self.synthetic_model)

    async def score_variants(
        self,
        scripts: List[FullScript],
        student_model: StudentModel,
        model_override: str = None,
    ) -> Tuple[FullScript, List[Dict[str, Any]]]:
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
                review.clarity
                + review.integrity
                + review.depth
                + review.practicality
                + review.pertinence
            )
            scored_data.append(
                {
                    "script": script,
                    "review": review,
                    "total_score": total_score,
                    "strategy": script.scaffolding_strategy,
                }
            )

        # Sort by total score descending
        scored_data.sort(key=lambda x: x["total_score"], reverse=True)

        best_variant = scored_data[0]["script"]

        # Phase 4 - Part 2: Synthetic Student Testing on the winner
        logger.info(
            f"Running synthetic student tests on selected variant: {scored_data[0]['strategy']}"
        )
        feedback = await self.tester.test_script(best_variant)

        # Phase 4 - Part 3: Refinement Loop (The "Gold Standard" step)
        refined_script = await self.refine_script(
            best_variant, student_model, feedback, model_override
        )

        selection_log = [
            {
                "strategy": d["strategy"],
                "total_score": d["total_score"],
                "breakdown": {
                    "clarity": d["review"].clarity,
                    "integrity": d["review"].integrity,
                    "depth": d["review"].depth,
                    "practicality": d["review"].practicality,
                    "pertinence": d["review"].pertinence,
                },
                "revisions": d["review"].revisions,
            }
            for d in scored_data
        ]

        # Attach synthetic feedback to the winning selection log entry
        for entry in selection_log:
            if entry["strategy"] == scored_data[0]["strategy"]:
                entry["synthetic_student_feedback"] = feedback
                break

        logger.info(
            f"Selected strategy: {scored_data[0]['strategy']} with score {scored_data[0]['total_score']}"
        )
        return refined_script, selection_log

    async def refine_script(
        self,
        script: FullScript,
        student_model: StudentModel,
        feedback: List[Dict[str, Any]],
        model_override: str = None,
    ) -> FullScript:
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
            logger.info(
                "No critical gaps identified by synthetic students. Skipping refinement."
            )
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
                temperature=0.3,
                max_tokens=1024,
                model_size="medium",
            )
            data = extract_json(response_text)
            return FullScript(**data)
        except Exception as e:
            logger.error(f"Error refining script: {str(e)}")
            return script

    async def review(
        self,
        script: FullScript,
        student_model: StudentModel,
        model_override: str = None,
    ) -> CIDPPScores:
        """
        Score a script on the CIDPP rubric.
        """
        # Local LLM CIDPP scoring is now the primary path
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
                system_instruction="You are a rigorous educational critic who scores scripts based on clarity, integrity, depth, practicality, and pertinence (CIDPP).",
            )
            data = extract_json(response_text)
            return CIDPPScores(**data)
        except Exception as e:
            logger.error(f"Error reviewing script: {str(e)}")
            return self.get_mock_data()

    def get_mock_data(self) -> CIDPPScores:
        return CIDPPScores(
            clarity=8, integrity=10, depth=7, practicality=7, pertinence=8, revisions=[]
        )
