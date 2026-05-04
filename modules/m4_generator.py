import os
import json
import asyncio
import random
from typing import List, Dict, Any, Tuple, Optional
from .schemas import FullScript, ScriptSegment, ConceptGraph, StudentModel, FactBundle
from .utils import extract_json
from .llm_client import LLMClient
from loguru import logger
from utils.analogy_store import analogy_store
from .m8_logger import StrategyTracker
from .utils import infer_subject
from . import nlm_studio


class ScriptGenerator:
    def __init__(self):
        self.llm = LLMClient()
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

        # Define available pedagogical strategies
        self.strategies = {
            "Intuition-First": "Intuition → Formula → Application (best for IB/AP students comfortable with abstraction)",
            "Cognitive-Conflict": "Misconception → Correction → Reconstruction (best for topics with strong prior errors)",
            "Inductive": "Example → Generalization (best for concrete learners, younger audiences)",
        }

        # Meta-policy: Epsilon-Greedy selection (Phase 3)
        self.strategy_tracker = StrategyTracker()
        self.epsilon_start = 0.15
        self.epsilon_min = 0.05
        self.epsilon_decay_rate = 0.001

        # Load misconception library
        self.misconception_library = self._load_misconceptions()

    def _load_misconceptions(self) -> Dict[str, Dict[str, List[str]]]:
        """Load the misconception library from resources/misconceptions.json."""
        path = "resources/misconceptions.json"
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        logger.warning(
            "Misconception library not found at resources/misconceptions.json"
        )
        return {}

    def get_relevant_misconceptions(
        self, concept_graph: ConceptGraph
    ) -> Dict[str, List[str]]:
        """Fetch misconceptions for concepts in the graph from the library."""
        found = {}
        for node in concept_graph.nodes:
            for subject, concepts in self.misconception_library.items():
                for concept, misconceptions in concepts.items():
                    if (
                        concept.lower() in node.concept.lower()
                        or node.concept.lower() in concept.lower()
                    ):
                        found[node.concept] = misconceptions
                        break
        return found

    def _get_epsilon(self) -> float:
        """Calculate current epsilon value with step-based decay."""
        total = self.strategy_tracker.total_run_count()
        return max(self.epsilon_min, self.epsilon_start - self.epsilon_decay_rate * total)

    def _select_strategy(self, level: str, subject: str) -> Tuple[Optional[str], str]:
        """Returns (strategy_name, mode) where mode is 'Exploit' | 'Explore' | 'ColdStart'."""
        min_runs = 5  # require at least this many runs per strategy before trusting data
        stats = self.strategy_tracker.get_full_stats()
        
        # Count runs per strategy for this level/subject
        strategy_totals = {s: 0 for s in self.strategies}
        for entry in stats:
            if entry['level'] == level and entry['subject'] == subject:
                strategy_totals[entry['strategy']] = entry['total']
        
        # Cold-start check
        if any(v < min_runs for v in strategy_totals.values()):
            return None, 'ColdStart'
        
        epsilon = self._get_epsilon()
        if random.random() < epsilon:
            chosen = random.choice(list(self.strategies.keys()))
            return chosen, 'Explore'
        else:
            win_rates = self.strategy_tracker.get_win_rates(level=level, subject=subject)
            if not win_rates:
                return None, 'ColdStart'
            best = max(win_rates, key=win_rates.get)
            return best, 'Exploit'

    async def _generate_all(
        self,
        concept_graph: ConceptGraph,
        student_model: StudentModel,
        fact_bundle: FactBundle,
        model_override: str = None,
    ) -> List[FullScript]:
        """Generate all 3 variants (Best-of-N mode) with throttled concurrency."""
        # Semaphore limits simultaneous LLM calls to avoid exhausting all API keys at once
        sem = asyncio.Semaphore(3)

        async def _guarded_generate(strategy_name, strategy_desc):
            async with sem:
                result = await self.generate(
                    concept_graph,
                    student_model,
                    fact_bundle,
                    strategy_name,
                    strategy_desc,
                    model_override,
                )
                await asyncio.sleep(2)  # stagger calls to spread rate-limit windows
                return result

        tasks = [
            _guarded_generate(name, desc)
            for name, desc in self.strategies.items()
        ]
        variants = await asyncio.gather(*tasks, return_exceptions=False)
        return list(variants)


    async def generate_variants(
        self,
        concept_graph: ConceptGraph,
        student_model: StudentModel,
        fact_bundle: FactBundle,
        model_override: str = None,
    ) -> List[FullScript]:
        """Generate script variants based on meta-policy (Epsilon-Greedy)."""
        # Check if we should use NotebookLM for script/audio
        notebook_id = fact_bundle.metadata.get("notebook_id")
        
        if notebook_id:
            topic_context = concept_graph.nodes[0].concept if concept_graph.nodes else "Education"
            logger.info(f"M4: Using NotebookLM flow for script generation (ID: {notebook_id})")
            try:
                script = await self._generate_with_notebooklm(notebook_id, concept_graph, student_model, topic_context)
                return [script]
            except Exception as e:
                logger.error(f"M4: NotebookLM flow failed ({e}). Falling back to legacy LLM flow.")


        is_contest_mode = os.getenv("CONTEST_MODE", "false").lower() == "true"
        
        if is_contest_mode:
            logger.info("[M4] Contest mode: generating all 3 variants for Best-of-3 Selection")
            return await self._generate_all(concept_graph, student_model, fact_bundle, model_override)

        # Legacy LLM flow
        level = student_model.level
        subject = fact_bundle.metadata.get("subject", "General")
        strategy, mode = self._select_strategy(level, subject)
        
        if mode == 'ColdStart' or strategy is None:
            logger.info(f"[M4] Cold-start ({level}/{subject}): generating all 3 for exploration")
            return await self._generate_all(concept_graph, student_model, fact_bundle, model_override)
        
        logger.info(f"[M4] [{mode}] ε={self._get_epsilon():.3f} → selected strategy '{strategy}' for {level}/{subject}")
        strategy_desc = self.strategies[strategy]
        variant = await self.generate(
            concept_graph,
            student_model,
            fact_bundle,
            strategy,
            strategy_desc,
            model_override,
        )
        # Transient flags for M8 handling
        variant.greedy_selected = True
        variant.greedy_mode = mode
        return [variant]

    def _get_exemplary_lessons(self, subject: str, level: str, strategy: str) -> str:
        """Fetch top-scoring lessons from M8 logs for few-shot injection."""
        path = "m8_feedback.json"
        if not os.path.exists(path):
            return ""
        try:
            with open(path, "r") as f:
                logs = json.load(f)
        except Exception:
            return ""
        
        candidates = []
        for entry in logs:
            data = entry.get("data", {})
            if not data:
                continue
                
            # Check strategy
            if data.get("selected_strategy") != strategy:
                continue
            
            # Check level
            student_level = data.get("student_model", {}).get("level", "high_school")
            if student_level != level:
                continue
            
            # Check subject
            req = data.get("request", {}).get("course_requirement", "")
            req_subject = infer_subject(req)
            if req_subject != subject:
                continue
                
            # Check score >= 40
            score = data.get("ai_student_scores", {}).get("Total", 0)
            if score >= 40:
                script = data.get("script")
                if script:  # Ensure we actually logged the script
                    candidates.append((score, script))
                
        # Sort by score desc, take top 2
        candidates.sort(key=lambda x: x[0], reverse=True)
        top_candidates = candidates[:2]
        
        if not top_candidates:
            return ""
            
        examples_str = "\n".join([json.dumps(c[1], indent=2) for c in top_candidates])
        return f"\nEXEMPLARY LESSONS (Reference for quality and style - these scored highly):\n{examples_str}\n"

    async def generate(
        self,
        concept_graph: ConceptGraph,
        student_model: StudentModel,
        fact_bundle: FactBundle,
        strategy_name: str = "Intuition-First",
        strategy_desc: str = None,
        model_override: str = None,
    ) -> FullScript:
        if not self.google_api_key and not self.openrouter_api_key:
            logger.warning("No LLM API keys found, falling back to mock data.")
            return self.get_mock_data(concept_graph, strategy_name)

        if not strategy_desc:
            strategy_desc = self.strategies.get(strategy_name, "Standard explanation")

        # Get few-shot examples
        level = student_model.level.value
        subject = infer_subject(concept_graph.nodes[0].concept if concept_graph.nodes else "")
        exemplars = self._get_exemplary_lessons(subject, level, strategy_name)

        prompt = f"""
        Generate a full educational script for the following lesson plan.
        Topic: {concept_graph.nodes[0].concept if concept_graph.nodes else "Topic"}
        Student Model: {student_model.json()}
        Facts: {fact_bundle.json()}
        Concept Graph: {concept_graph.json()}

        PEDAGOGICAL ANALOGIES (Use if relevant):
        {json.dumps(self.get_relevant_analogies(concept_graph), indent=2)}

        COMMON MISCONCEPTIONS (Address in narration for Cognitive-Conflict strategy):
        {json.dumps(self.get_relevant_misconceptions(concept_graph), indent=2)}
        {exemplars}
        SCAFFOLDING STRATEGY: {strategy_name} ({strategy_desc})

        Requirements:
        1. Narrative Flow: Ensure smooth transitions between concepts.
        2. Visual Cues: For each segment, provide a 'visual_content_spec' detailing what should be on screen. If the subject is Physics or Mathematics, the 'visual_content_spec' MUST specifically request clean vector schematics, technical diagrams, or 2D graphs without text, avoiding realistic imagery that causes nonsensical artifacts.
        3. Pacing: Match student level (vocabulary, complexity).
        4. Citations: Every factual claim must be attributed to a source in the facts.
        5. Hook: First 60 seconds must have a curiosity trigger.
        6. Checks: Include Socratic questions or checks for understanding.
        7. For Cognitive-Conflict strategy, explicitly address and correct the listed misconceptions.
        8. Verbosity: Every segment narration MUST be between 150-250 words. Do not be overly concise. Explain in detail to ensure the final video length is substantial.

        Return the data as a JSON object matching this schema:
        {{
            "title": "Lesson Title",
            "scaffolding_strategy": "{strategy_name}",
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
                temperature=0.8,
                max_tokens=8192,
                model_size="large",
            )
            data = extract_json(response_text)
            
            # Post-generation validation: check for overly concise segments
            for seg in data.get("segments", []):
                narration = seg.get("narration", "")
                word_count = len(narration.split())
                if word_count < 100:
                    logger.warning(f"M4: Segment {seg.get('segment_id')} is too short ({word_count} words).")
                    # We could trigger a retry here, but for now we just log it.
            # Ensure strategy name is preserved
            data["scaffolding_strategy"] = strategy_name
            data["subject"] = subject
            return FullScript(**data)
        except Exception as e:
            logger.error(f"Error generating script ({strategy_name}): {str(e)}")
            return self.get_mock_data(concept_graph, strategy_name)

    def get_mock_data(
        self, concept_graph: ConceptGraph, strategy_name: str = "Intuition-First"
    ) -> FullScript:
        return FullScript(
            title="Introductory Lesson",
            scaffolding_strategy=strategy_name,
            segments=[
                ScriptSegment(
                    segment_id="seg_0",
                    concept=concept_graph.nodes[0].concept
                    if concept_graph.nodes
                    else "Intro",
                    narration=f"Welcome to this {strategy_name} lesson.",
                    visual_type="Animation",
                    visual_content_spec="Title slide",
                    duration_seconds=30.0,
                )
            ],
            hook="Ready to learn?",
            checks=[],
        )

    async def _generate_with_notebooklm(
        self, 
        notebook_id: str, 
        concept_graph: ConceptGraph, 
        student_model: StudentModel,
        topic_context: str
    ) -> FullScript:
        """
        NotebookLM-powered generation:
        1. Generate Audio Overview (Podcast).
        2. Transcribe and Plan visuals based on the actual audio.
        """
        import uuid
        run_id = str(uuid.uuid4())[:8]
        audio_dir = os.path.join("temp", "audio")
        os.makedirs(audio_dir, exist_ok=True)
        audio_path = os.path.join(audio_dir, f"notebooklm_{run_id}.mp3")

        # 1. Generate and Download Audio
        logger.info(f"M4: Generating NotebookLM Audio Overview for {notebook_id}...")
        await nlm_studio.generate_audio(notebook_id, audio_path)

        if not os.path.exists(audio_path):
            logger.error("M4: NotebookLM audio generation failed. Falling back to legacy LLM flow.")
            raise RuntimeError("NotebookLM Audio Generation Failed")

        # 2. Transcribe and Align Visuals via Gemini 2.0 Flash (Multimodal)
        logger.info("M4: Transcribing and planning visuals via Gemini Multimodal...")
        
        from google.genai import types as genai_types
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        
        audio_part = genai_types.Part.from_bytes(data=audio_bytes, mime_type="audio/mpeg")
        
        prompt = f"""
        You are a video editor and pedagogical director. 
        Listen to this educational podcast about '{topic_context}'.
        
        Create a high-fidelity visual script for a Teaching Monster video that matches this audio perfectly.
        The student is at {student_model.level} level.
        
        Return a JSON object following this structure:
        {{
          "title": "...",
          "scaffolding_strategy": "NotebookLM Podcast Alignment",
          "hook": "...",
          "segments": [
            {{
              "segment_id": "seg_0",
              "concept": "...",
              "narration": "The exact transcript part for this segment",
              "visual_type": "gemini_infographic | pexels_broll",
              "visual_content_spec": "Detailed prompt for the visual",
              "duration_seconds": 12.5
            }},
            ...
          ],
          "checks": ["Socratic question 1", "Socratic question 2"]
        }}
        
        Rules:
        1. Segments must cover the ENTIRE audio file. 
        2. 'duration_seconds' for all segments must sum up to the total length of the audio.
        3. Be descriptive in 'visual_content_spec'.
        4. If the topic is Physics or Mathematics, ensure 'visual_content_spec' explicitly requests clean vector schematics, technical diagrams, or 2D graphs, avoiding realistic/photographic imagery that could generate nonsensical artifacts.
        """
        
        try:
            response_text = await self.llm.generate_multimodal(
                contents=[audio_part, prompt],
                system_instruction="You are a JSON-only visual script generator.",
                model_override="models/gemini-2.0-flash"
            )
            
            script_data = extract_json(response_text)
            script_data["subject"] = infer_subject(topic_context)
            full_script = FullScript(**script_data)
            
            # Attach the audio path to the script so M7 knows to use it
            full_script.total_audio_path = audio_path
            full_script.notebook_id = notebook_id
            
            logger.success(f"M4: Successfully generated script aligned with NotebookLM audio ({len(full_script.segments)} segments)")
            return full_script
            
        except Exception as e:
            logger.error(f"M4: Gemini Multimodal alignment failed: {e}")
            raise

    def get_relevant_analogies(self, concept_graph: ConceptGraph) -> Dict[str, str]:
        """Fetch pre-curated analogies for concepts in the graph."""
        found = {}
        # We don't have 'subject' in concept_graph yet,
        # so we check all subjects for matching concept keywords.
        subjects = ["Computer Science", "Physics", "Biology", "Mathematics"]

        for node in concept_graph.nodes:
            for subject in subjects:
                analogy = analogy_store.get_analogy(subject, node.concept)
                if analogy:
                    found[node.concept] = analogy
                    break  # Move to next node
        return found
