import os
import json
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from .schemas import FullScript, StudentModel, CIDPPScores, FactBundle, ConceptGraph, RLTScore
from .utils import extract_json
from .llm_client import LLMClient
from .m5b_probe_generator import probe_gen
from .m8_logger import FeedbackLogger
from . import nlm_studio
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
                "mandate": "Identify segments lacking clear visual scaffolds. Check if 'visual preference' was honored (did narration say 'Look at...' or 'Observe...').",
            },
            "Persona B (Math-Anxious)": {
                "description": "A student with severe math anxiety who shuts down when encountering ungrounded equations.",
                "mandate": "Check cognitive load. Find formulas introduced WITHOUT a prior relatable analogy. Flag if steps are too large.",
            },
            "Persona C (High-Performer)": {
                "description": "An advanced student who is easily bored and frustrated by oversimplification.",
                "mandate": "Check abstraction level. Did it lean into formulas if requested? Identify places where it felt 'dumbed down' or repetitive.",
            },
            "Persona D (Low-Prior/High-Curiosity)": {
                "description": "A complete beginner — no background knowledge, but highly curious and motivated.",
                "mandate": "Check engagement. Were the hooks (opening, mid, closing) actually interesting? Flag generic 'today we learn' phrasing.",
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
        script_text = script.model_dump_json()[:3000]

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
    "suggested_improvement": "One concrete fix",
    "adaptability_comment": "How well did it fit your visual/verbal needs?",
    "engagement_comment": "Did the hooks keep you interested?"
  }},
  {{
    "persona": "Persona B (Math-Anxious)",
    "is_perfect": false,
    "gaps": ["specific gap 1", "specific gap 2"],
    "confusing_quotes": ["exact quote from script"],
    "suggested_improvement": "One concrete fix",
    "adaptability_comment": "Did the cognitive load feel right?",
    "engagement_comment": "Did you feel encouraged or discouraged?"
  }},
  {{
    "persona": "Persona C (High-Performer)",
    "is_perfect": false,
    "gaps": ["specific gap 1", "specific gap 2"],
    "confusing_quotes": ["exact quote from script"],
    "suggested_improvement": "One concrete fix",
    "adaptability_comment": "Was the abstraction level appropriate?",
    "engagement_comment": "Was it boring or intellectually stimulating?"
  }},
  {{
    "persona": "Persona D (Low-Prior/High-Curiosity)",
    "is_perfect": false,
    "gaps": ["specific gap 1", "specific gap 2"],
    "confusing_quotes": ["exact quote from script"],
    "suggested_improvement": "One concrete fix",
    "adaptability_comment": "Were the explanations clear for a beginner?",
    "engagement_comment": "Did the hooks actually 'hook' you?"
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
                    "adaptability_comment": "Auto-padded entry.",
                    "engagement_comment": "Auto-padded entry."
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
                    "adaptability_comment": "Unable to verify adaptability due to system error.",
                    "engagement_comment": "Unable to verify engagement due to system error."
                }
                for name in self.personas.keys()
            ]


class NaiveStudentEvaluator:
    """Simulates a naive student answering comprehension probes based ONLY on the script.

    This implements the P4-B 'RLT-Style' reward signal.
    """

    def __init__(self):
        self.llm = LLMClient()
        self.model = os.getenv("RLT_STUDENT_MODEL", "models/gemini-2.0-flash")

    async def evaluate(self, script: FullScript, probes: List[Any]) -> RLTScore:
        """Answer probes based strictly on narration text."""
        if not probes:
            return RLTScore(probes_total=0, probes_correct=0, comprehension_score=0, student_answers=[])

        # Concatenate all narration segments
        narration_text = "\n".join([s.narration for s in script.segments])
        
        # Build probe questions for LLM
        questions_text = "\n".join([f"{i+1}. {p.question}" for i, p in enumerate(probes)])

        prompt = f"""
        You are a student who has ONLY read the lesson transcript below.
        Answer each question using ONLY information present in the transcript.
        
        LESSON TRANSCRIPT:
        {narration_text[:4000]}
        
        QUESTIONS:
        {questions_text}
        
        RULES:
        1. If the transcript does NOT contain the answer, write exactly: "Not covered"
        2. Do not use any outside knowledge.
        3. Be concise (1 sentence max).
        
        Return ONLY a JSON array of objects:
        [
          {{"question": "...", "student_answer": "..."}}
        ]
        """

        try:
            logger.info(f"[RLT] Naive Student evaluating script: '{script.title}'")
            response = await self.llm.generate_text(
                prompt=prompt,
                model_override=self.model,
                system_instruction="You are a naive student answering based on a provided text. Return ONLY JSON.",
                temperature=0.0, # Deterministic answering
                model_size="small"
            )
            
            answers = extract_json(response)
            if not isinstance(answers, list):
                raise ValueError("Expected list of answers")

            correct_count = 0.0
            results = []
            
            for i, probe in enumerate(probes):
                # Match answer from LLM to original probe
                student_ans = "Not covered"
                if i < len(answers):
                    student_ans = answers[i].get("student_answer", "Not covered")
                
                # Check for correct keyphrase (case-insensitive substring match)
                is_correct = False
                if student_ans.lower() != "not covered":
                    if probe.correct_answer.lower() in student_ans.lower():
                        is_correct = True
                        correct_count += 1.0
                    elif "not covered" not in student_ans.lower():
                        # Partial credit could go here, but stick to binary for now
                        pass
                
                results.append({
                    "question": probe.question,
                    "student_answer": student_ans,
                    "correct_keyphrase": probe.correct_answer,
                    "is_correct": is_correct
                })

            score = RLTScore(
                probes_total=len(probes),
                probes_correct=correct_count,
                comprehension_score=correct_count / len(probes),
                student_answers=results
            )
            logger.success(f"[RLT] Evaluation complete: {correct_count}/{len(probes)} correct")
            return score

        except Exception as e:
            logger.error(f"[RLT] Naive Student evaluation failed: {e}")
            return RLTScore(probes_total=len(probes), probes_correct=0, comprehension_score=0, student_answers=[])


class CIDPPCritic:
    def __init__(self):
        self.llm = LLMClient()
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.synthetic_model = os.getenv(
            "SYNTHETIC_STUDENT_MODEL", "models/gemini-2.0-flash"
        )
        self.tester = SyntheticStudentTester(self.synthetic_model)
        self.naive_student = NaiveStudentEvaluator()

    async def score_variants(
        self,
        scripts: List[FullScript],
        student_model: StudentModel,
        fact_bundle: Optional[FactBundle] = None,
        concept_graph: Optional[ConceptGraph] = None,
        model_override: str | None = None,
        max_revisions: int = 1,
    ) -> Tuple[FullScript, List[Dict[str, Any]]]:
        """Review multiple scripts and select the one with the highest pedagogical score (CIDPP + RLT)."""
        is_contest_mode = os.getenv("CONTEST_MODE", "false").lower() == "true"
        
        # ── Dynamic Weight Graduation (P4-B) ────────────────────────────────
        # Default weights
        rlt_weight = float(os.getenv("RLT_BLEND_WEIGHT", "0.30"))
        
        # Graduation Logic: check accumulated RLT runs
        try:
            m8 = FeedbackLogger()
            rlt_runs = m8.get_rlt_run_count()
            if rlt_runs >= 50:
                logger.info(f"[P4-B] Graduation threshold reached ({rlt_runs} runs). Using 0.60/0.40 blend.")
                rlt_weight = 0.40
            else:
                logger.info(f"[P4-B] Status: {rlt_runs}/50 runs for graduation. Using {rlt_weight:.2f} RLT weight.")
        except Exception as e:
            logger.warning(f"[P4-B] Weight graduation check failed: {e}. Using default {rlt_weight}")

        cidpp_weight = 1.0 - rlt_weight
        
        # ── Generate shared probes ───────────────────────────────────────────
        probes = []
        if fact_bundle and concept_graph:
            probes = await probe_gen.generate(fact_bundle, concept_graph, model_override=model_override)

        reviews = []
        # Score CIDPP sequentially
        for script in scripts:
            if script is None:
                logger.warning("[M5] Skipping None script in variants list.")
                continue
            review = await self.review(script, student_model, model_override)
            reviews.append(review)
            await asyncio.sleep(1)

        scored_data = []
        for script, review in zip(scripts, reviews):
            # CIDPP normalisation (0-50 -> 0-1)
            cidpp_total = (
                review.clarity
                + review.integrity
                + review.depth
                + review.practicality
                + review.pertinence
                + review.adaptability
                + review.engagement
            )
            cidpp_n = cidpp_total / 70.0

            # RLT scoring (0-1)
            rlt_res = None
            if probes:
                rlt_res = await self.naive_student.evaluate(script, probes)
                rlt_val = rlt_res.comprehension_score
            else:
                rlt_val = cidpp_n # neutral fallback if no probes

            # Final Blended Score
            blended = (cidpp_weight * cidpp_n) + (rlt_weight * rlt_val)

            scored_data.append(
                {
                    "script": script,
                    "review": review,
                    "cidpp_total": cidpp_total,
                    "cidpp_normalised": cidpp_n,
                    "cidpp_weight": cidpp_weight,
                    "rlt_score": rlt_res,
                    "rlt_weight": rlt_weight,
                    "blended_score": blended,
                    "strategy": script.scaffolding_strategy,
                }
            )

        # Sort by blended score descending
        scored_data.sort(key=lambda x: x["blended_score"], reverse=True)

        best_variant = scored_data[0]["script"]

        # advisory check: NLM Quiz for curriculum coverage
        nlm_quiz = []
        nlm_notebook_id = fact_bundle.metadata.get("notebook_id") if fact_bundle else None
        if nlm_notebook_id and nlm_studio.is_available():
            logger.info(f"[M5] NLM available. Generating advisory quiz for coverage check...")
            nlm_quiz = await nlm_studio.generate_quiz(nlm_notebook_id)

        # Phase 4 - Part 2 & 3: Synthetic Student Testing & Refinement Loop
        refined_script = best_variant
        all_feedback = []
        
        # If we have a total_audio_path (NotebookLM flow), we SKIP refinement 
        # because the script must match the pre-generated audio exactly.
        if best_variant.total_audio_path:
            logger.info("[M5] NotebookLM audio detected. Skipping refinement to maintain audio-script alignment.")
            max_revisions = 0

        for rev in range(max_revisions):
            logger.info(
                f"Running synthetic student tests on selected variant (revision {rev+1}/{max_revisions})"
            )
            feedback = await self.tester.test_script(refined_script)
            all_feedback.extend(feedback)
            
            # Check if we can break early
            has_gaps = False
            for f in feedback:
                if not f.get("is_perfect", True):
                    has_gaps = True
                    break
                    
            if not has_gaps and rev > 0:
                logger.info("No gaps found. Ending refinement loops early.")
                break

            refined_script = await self.refine_script(
                refined_script, student_model, feedback, model_override
            )

        selection_log = [
            {
                "strategy": d["strategy"],
                "blended_score": d["blended_score"],
                "cidpp_normalised": d["cidpp_normalised"],
                "cidpp_weight": d["cidpp_weight"],
                "rlt_comprehension_score": d["rlt_score"].comprehension_score if d["rlt_score"] else None,
                "rlt_weight": d["rlt_weight"],
                "rlt_probes_total": d["rlt_score"].probes_total if d["rlt_score"] else 0,
                "rlt_probes_correct": d["rlt_score"].probes_correct if d["rlt_score"] else 0,
                "cidpp_total": d["cidpp_total"],
                "blend_note": "conservative_0.70_0.30 → graduate to 0.60_0.40 at ≥50 RLT runs",
                "breakdown": {
                    "clarity": d["review"].clarity,
                    "integrity": d["review"].integrity,
                    "depth": d["review"].depth,
                    "practicality": d["review"].practicality,
                    "pertinence": d["review"].pertinence,
                    "adaptability": d["review"].adaptability,
                    "engagement": d["review"].engagement,
                },
                "revisions": d["review"].revisions,
            }
            for d in scored_data
        ]

        # Attach synthetic feedback to the winning selection log entry
        for entry in selection_log:
            if entry["strategy"] == scored_data[0]["strategy"]:
                entry["synthetic_student_feedback"] = all_feedback
                entry["nlm_advisory_quiz"] = nlm_quiz
                break

        logger.info(
            f"Selected strategy: {scored_data[0]['strategy']} with blended score {scored_data[0]['blended_score']:.4f}"
        )
        return refined_script, selection_log

    async def refine_script(
        self,
        script: FullScript,
        student_model: StudentModel,
        feedback: List[Dict[str, Any]],
        model_override: str | None = None,
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
        {script.model_dump_json()}
        
        STUDENT FEEDBACK (Identified Gaps):
        {json.dumps(critical_gaps, indent=2)}
        
        STUDENT PROFILE:
        {student_model.model_dump_json()}
        
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
        model_override: str | None = None,
    ) -> CIDPPScores:
        """
        Score a script on the CIDPP rubric.
        """
        if script is None:
            logger.error("[M5] Received None script for review. Returning mock scores.")
            return self.get_mock_data()
        # Local LLM CIDPP scoring is now the primary path
        if not self.google_api_key and not self.openrouter_api_key:
            logger.warning("No LLM API keys found, falling back to mock data.")
            return self.get_mock_data()

        prompt = f"""
        You are a strict educational evaluator. Score the following lesson script using the CIDPP rubric.
        
        IMPORTANT: Your scores MUST reflect genuine quality differences. Do NOT give 8/10 for everything.
        Scores of 7, 8, 9, or 10 must be EARNED. A score of 5 means average. A score of 3 means poor.

        Script: {script.model_dump_json()}
        Student Model: {student_model.model_dump_json()}

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

        - Adaptability (Adherence to student-specific cognitive load, modality, and abstraction tolerance)
          10: Perfectly follows all adaptive constraints (load, modality, abstraction).
          7: Follows most constraints but misses 1 nuance (e.g. slightly too abstract).
          5: General attempt at adaptation but feels like a template.
          3: Completely ignores student-specific constraints.

        - Engagement (Hooks, re-engagement prompts, and closing challenges)
          10: Captivating opening, strong mid-video re-engagement, compelling closing.
          7: Has all 3 required elements, but 1 feels forced or generic.
          5: Missing 1 of the 3 mandatory engagement elements.
          3: Boring, generic, or missing multiple engagement elements.

        MANDATORY: Your revisions list must contain at least 2 specific, actionable improvements.
        
        Return ONLY a JSON object:
        {{
            "clarity": int,
            "integrity": int,
            "depth": int,
            "practicality": int,
            "pertinence": int,
            "adaptability": int,
            "engagement": int,
            "revisions": ["Specific improvement 1", "Specific improvement 2"]
        }}
        """

        for attempt in range(3):
            try:
                response_text = await self.llm.generate_text(
                    prompt=prompt,
                    model_override=model_override,
                    system_instruction="You are a rigorous educational critic who scores scripts based on clarity, integrity, depth, practicality, and pertinence (CIDPP). Return ONLY raw JSON.",
                )
                data = extract_json(response_text)
                return CIDPPScores(**data)
            except Exception as e:
                logger.warning(f"Error reviewing script (attempt {attempt+1}): {str(e)}")
                if attempt < 2:
                    await asyncio.sleep(1)
                else:
                    logger.error(f"Failed to review script after 3 attempts. Using mock data.")
                    return self.get_mock_data()
        
        return self.get_mock_data()

    def get_mock_data(self) -> CIDPPScores:
        return CIDPPScores(
            clarity=8, 
            integrity=10, 
            depth=7, 
            practicality=7, 
            pertinence=8,
            adaptability=7,
            engagement=8,
            revisions=[]
        )
