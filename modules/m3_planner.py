import os
import json
from .schemas import ConceptNode, ConceptGraph, StudentModel
from .utils import extract_json
from .llm_client import LLMClient
from loguru import logger

# Minimum number of concept nodes required for a valid lesson plan.
# Below this, the graph is considered under-generated and a retry is triggered.
MIN_CONCEPT_NODES = 3


class ConceptPlanner:
    def __init__(self):
        self.llm = LLMClient()
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

    def _load_curriculum_context(self, topic: str) -> str:
        """
        Load curriculum markdown for the given topic, if one exists.
        Returns the first 2000 chars (fits comfortably in prompt context).
        """
        CURRICULUM_MAP = {
            "optic": "resources/curriculum/physics/optics_and_light.md",
            "light": "resources/curriculum/physics/optics_and_light.md",
            "refraction": "resources/curriculum/physics/optics_and_light.md",
            "reflection": "resources/curriculum/physics/optics_and_light.md",
            "nuclear": "resources/curriculum/physics/nuclear_physics_basics.md",
            "circulatory": "resources/curriculum/biology/human_circulatory_system.md",
            "kinematics": "resources/curriculum/physics/kinematics_and_dynamics.md",
            "dynamics": "resources/curriculum/physics/kinematics_and_dynamics.md",
            "pendulum": "resources/curriculum/physics/mechanics_pendulums.md",
        }
        topic_lower = topic.lower()
        for keyword, path in CURRICULUM_MAP.items():
            if keyword in topic_lower:
                full_path = os.path.join(os.path.dirname(__file__), "..", path)
                full_path = os.path.normpath(full_path)
                if os.path.exists(full_path):
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read(2000)
                    logger.info(f"M3: Loaded curriculum context from {path}")
                    return content
        return ""

    def _build_prompt(
        self, topic: str, student_model: StudentModel, retry_hint: str = ""
    ) -> str:
        """
        Builds the LLM prompt for concept graph generation.
        On retry, injects a hint explaining the previous attempt failed.
        """
        retry_block = ""
        if retry_hint:
            retry_block = f"""
IMPORTANT — YOUR PREVIOUS ATTEMPT FAILED: {retry_hint}
You MUST return at least {MIN_CONCEPT_NODES} nodes this time. A single-node response is incorrect.
"""
        
        curriculum_context = self._load_curriculum_context(topic)
        curriculum_block = ""
        if curriculum_context:
            curriculum_block = f"""
CURRICULUM REFERENCE (use this as your factual ground truth — do not invent concepts):
---
{curriculum_context}
---
Your concept nodes MUST be drawn from the above content. Do not use concepts not present in this reference.
"""

        return f"""
You are a pedagogical lesson planner specializing in concept scaffolding.

Your task: Plan a lesson sequence for the topic: "{topic}".
Student Model: {student_model.model_dump_json()}
{curriculum_block}
STEP 1 — THINK FIRST (do not output this):
Analyze the topic and break it down into {MIN_CONCEPT_NODES} to 7 distinct sub-concepts that build progressively.
List them explicitly: 1. Simplest foundational concept, 2. Next level, ..., up to the full topic.
Each sub-concept must be a separate, teachable unit.

STEP 2 — OUTPUT the concept graph as JSON.

CONSTRAINTS (strictly enforced):
- You MUST return EXACTLY between {MIN_CONCEPT_NODES} and 7 concept nodes. NOT 1, NOT 2 — minimum {MIN_CONCEPT_NODES}.
- Returning fewer than {MIN_CONCEPT_NODES} nodes is a failure and will be rejected.
- The final node must cover the complete topic "{topic}".
- Each node must teach something new that cannot be derived from the previous node alone.
- If a topic has common points of confusion (e.g. "Simple vs Physical Pendulum"), you MUST include a "disambiguation" node specifically to clarify the difference. Set "is_disambiguation": true for these nodes.
- Prerequisites must use the EXACT concept name of a prior node, or be an assumed prior knowledge concept already in the student model.
- Scaffold from concrete → abstract, simple → complex.
- total_duration_minutes must be <= 25.

EXAMPLE for topic "Photosynthesis":
{{
    "nodes": [
        {{
            "concept": "Plants need food to grow",
            "prerequisites": [],
            "misconceptions": ["Plants eat soil"],
            "visual_type": "Animation",
            "duration_minutes": 4.0
        }},
        {{
            "concept": "Plants make their own food using sunlight",
            "prerequisites": ["Plants need food to grow"],
            "misconceptions": ["Plants get food from the ground"],
            "visual_type": "Diagram",
            "duration_minutes": 5.0
        }},
        {{
            "concept": "Photosynthesis chemical process",
            "prerequisites": ["Plants make their own food using sunlight"],
            "misconceptions": ["Photosynthesis is magic"],
            "visual_type": "Flowchart",
            "duration_minutes": 6.0
        }}
    ],
    "total_duration_minutes": 15.0
}}

Return ONLY a JSON object matching this exact schema (no explanation text):
{{
    "nodes": [
        {{
            "concept": "Exact concept name (string)",
            "prerequisites": ["exact name of a prior node concept, or assumed prior knowledge"],
            "misconceptions": ["common student error 1", "common student error 2"],
            "visual_type": "Animation" | "Flowchart" | "Diagram" | "Derivation",
            "is_disambiguation": true | false,
            "duration_minutes": 3.0
        }}
    ],
    "total_duration_minutes": 12.0
}}

NOTE ON DISAMBIGUATION: If a node's primary purpose is to address the listed misconceptions or distinguish the concept from a related one, set "is_disambiguation": true. This will trigger special pedagogical handling.
{retry_block}
"""

    async def plan(
        self, topic: str, student_model: StudentModel, model_override: str | None = None
    ) -> ConceptGraph:
        """
        Generate a ConceptGraph with at least MIN_CONCEPT_NODES nodes.
        Attempts up to 2 LLM calls before falling back to a minimal template stub.
        """
        if not self.google_api_key and not self.openrouter_api_key:
            logger.warning("No LLM API keys found, falling back to template stub.")
            return self.get_fallback_stub(topic)

        last_error = ""
        for attempt in range(1, 3):  # Max 2 attempts
            retry_hint = last_error if attempt > 1 else ""
            prompt = self._build_prompt(topic, student_model, retry_hint=retry_hint)

            try:
                response_text = await self.llm.generate_text(
                    prompt=prompt,
                    model_override=model_override,
                    temperature=0.7,
                    max_tokens=2048,
                    model_size="medium",
                )

                data = extract_json(response_text)
                graph = ConceptGraph(**data)

                # --- POST-PARSE GUARD (Pydantic Silent Acceptance Fix) ---
                # ConceptGraph(**data) accepts any valid JSON including 1-node lists.
                # We must check and reject under-generated graphs BEFORE returning.
                # Do NOT add min_length to the schema — it would cause ValidationError
                # which is caught by the except block and silently falls back to stub.
                node_count = len(graph.nodes)
                logger.debug(
                    f"M3 [{topic}] — attempt {attempt}: generated {node_count} node(s)"
                )

                if node_count < MIN_CONCEPT_NODES:
                    last_error = (
                        f"Only {node_count} node(s) were returned. "
                        f"The minimum required is {MIN_CONCEPT_NODES}. "
                        f"You must break '{topic}' into more sub-concepts."
                    )
                    logger.warning(
                        f"M3 under-generation on attempt {attempt}: {last_error}"
                    )
                    continue  # Trigger retry

                # Validate prerequisite consistency (non-blocking — logs only)
                known_concepts = {n.concept for n in graph.nodes}
                known_prior = set(student_model.knowledge_embedding)
                for node in graph.nodes:
                    for prereq in node.prerequisites:
                        if prereq not in known_concepts and prereq not in known_prior:
                            logger.warning(
                                f"M3 prerequisite '{prereq}' for node '{node.concept}' "
                                f"does not match any known concept name. Check LLM output."
                            )

                logger.info(
                    f"M3 [{topic}] — successfully generated {node_count} nodes on attempt {attempt}"
                )
                return graph

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"M3 attempt {attempt} failed with exception: {last_error}"
                )
                continue

        # Both attempts failed
        logger.critical(
            f"M3 FAILED after 2 attempts for topic '{topic}'. "
            f"Last error: {last_error}. "
            f"Falling back to template stub. Check pipeline.log for raw LLM output."
        )
        return self.get_fallback_stub(topic)

    def get_fallback_stub(self, topic: str) -> ConceptGraph:
        """
        3-node template stub used ONLY when both LLM attempts fail.
        Unlike the old 1-node get_mock_data(), this preserves basic scaffolding
        and is clearly named to distinguish it from an actual failure.
        """
        return ConceptGraph(
            nodes=[
                ConceptNode(
                    concept=f"Foundations of {topic}",
                    prerequisites=[],
                    misconceptions=[f"Confusing {topic} with a related concept"],
                    visual_type="Diagram",
                    duration_minutes=4.0,
                ),
                ConceptNode(
                    concept=f"Core Mechanisms of {topic}",
                    prerequisites=[f"Foundations of {topic}"],
                    misconceptions=[f"Oversimplifying the mechanism of {topic}"],
                    visual_type="Animation",
                    duration_minutes=6.0,
                ),
                ConceptNode(
                    concept=f"Common Pitfalls and Disambiguation of {topic}",
                    prerequisites=[f"Core Mechanisms of {topic}"],
                    misconceptions=[
                        f"Assuming {topic} applies universally without conditions"
                    ],
                    visual_type="Flowchart",
                    is_disambiguation=True,
                    duration_minutes=5.0,
                ),
            ],
            total_duration_minutes=15.0,
        )
