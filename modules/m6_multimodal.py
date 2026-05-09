"""
M6 MultimodalPlanner — Visual Planning with AI Infographic Generation

Visual source routing (priority):
  1. Gemini infographic (generated from narration text) — for concept/diagram/data/slide types
  2. Pexels B-roll (keyword search)                    — for action/demo/real_world types
  3. Fallback solid-color slide                         — when both fail

Feature flags (in .env):
  INFOGRAPHIC_ENABLED=true    — enables Gemini image gen (default: true)
  AVATAR_ENABLED=true         — enables professor avatar PiP (default: true)
"""

import os
import asyncio
from typing import List, Dict, Any
from .schemas import FullScript, ScriptSegment
from utils.visuals import SlideGenerator
from .llm_client import LLMClient
from loguru import logger

# Import the new infographic generator
from .m6b_infographic_gen import InfographicGenerator
from . import nlm_studio


# Visual types that benefit from AI-generated infographics
_INFOGRAPHIC_TYPES = {"concept", "diagram", "data", "slide", "theory", "definition", "example", "story", "lesson"}
# Visual types that prefer real-world B-roll footage (only used if explicitly requested)
_BROLL_TYPES = {"action", "real_world", "footage"}


class MultimodalPlanner:
    def __init__(self, output_dir="temp/visuals"):
        self.generator = SlideGenerator()
        self.output_dir = output_dir
        self.llm = LLMClient()
        self.infographic_gen = InfographicGenerator(
            output_dir=os.path.join(output_dir, "infographics")
        )
        os.makedirs(self.output_dir, exist_ok=True)

    async def plan_visuals(self, script: FullScript) -> List[Dict[str, Any]]:
        visual_plan = []

        # 1. Batch generate Pexels keywords (always, used as audio-search + B-roll fallback)
        logger.info("M6: Planning visual assets for all segments...")
        keywords_map = await self._generate_keywords_map(script)

        # 2. Pre-generate all infographics concurrently
        subject = getattr(script, "subject", None) or getattr(script, "topic", None)
        infographic_map = await self.infographic_gen.generate_all(
            script.segments, subject=subject
        )

        # Get notebook_id from script metadata (set by M1)
        notebook_id = getattr(script, "notebook_id", None)
        nlm_slide_map: dict = {}
        
        # Pre-generate NLM slides concurrently if available
        if notebook_id and nlm_studio.is_available():
            logger.info("M6: Pre-generating NLM slides for all segments...")
            slide_tasks = [
                nlm_studio.generate_slides(
                    notebook_id=notebook_id,
                    concept=seg.concept,
                    segment_id=seg.segment_id,
                    visual_content_spec=seg.visual_content_spec,
                    output_dir=self.output_dir,
                )
                for seg in script.segments
            ]
            slide_results = await asyncio.gather(*slide_tasks, return_exceptions=True)
            for seg, result in zip(script.segments, slide_results):
                if isinstance(result, str) and result:
                    nlm_slide_map[seg.segment_id] = result
            logger.info(f"M6: NLM slides generated: {len(nlm_slide_map)}/{len(script.segments)}")

        for i, segment in enumerate(script.segments):
            # ── Route visual source ──────────────────────────────────────────
            visual_type = (segment.visual_type or "concept").lower().strip()
            seg_id_str = segment.segment_id
            nlm_slide_path = nlm_slide_map.get(seg_id_str)
            infographic_path = infographic_map.get(seg_id_str)

            # Priority: NLM slide → Gemini infographic → Pexels B-roll
            # ── Strict STEM Routing ──────────────────────────────────────────
            # Prevent hallucinatory text and irrelevant diagrams in Math/Physics
            is_stem = False
            is_physics_schematic = False
            if subject:
                sub = subject.lower()
                con = segment.concept.lower()
                stem_keywords = ("math", "physics", "geometry", "optics", "calculus", "science", "chemistry", "chemical", "biology", "cell", "anatomy", "data science", "machine learning", "ai", "artificial intelligence")
                if any(k in sub or k in con for k in stem_keywords):
                    is_stem = True
                
                # Check for critical physics concepts that MUST be schematics
                physics_schematic_keywords = ("pendulum", "oscillat", "rigid body", "moment of inertia", "torque", "angular", "vector", "force", "acceleration", "kinematics")
                if any(k in con for k in physics_schematic_keywords) and "physics" in sub:
                    is_physics_schematic = True
                    visual_type = "schematic"

            # ── Strict STEM Routing Logic ────────────────────────────────────
            # For STEM subjects, we prefer grounded NLM slides or deterministic fallback slides.
            # We ONLY allow Gemini if it's a non-technical 'example' or 'story' and no NLM is available.
            _STEM_BROLL_ALLOWED = {"action", "real_world", "footage"}   # B-roll is OK for these

            if nlm_slide_path:
                visual_source = "nlm_slide"
                logger.info(f"M6: Seg {seg_id_str} → NLM slide")
            elif is_physics_schematic:
                # Critical physics concept: MUST use NLM or Fallback Slide (No Gemini, No B-roll)
                visual_source = "nlm_slide" if notebook_id else "fallback_slide"
                logger.warning(f"M6: Seg {seg_id_str} (Physics Schematic) → Enforcing {visual_source} for '{segment.concept}'")
            elif is_stem:
                # General STEM segment
                if visual_type in _STEM_BROLL_ALLOWED:
                    visual_source = "pexels_broll"
                    logger.info(f"M6: Seg {seg_id_str} (STEM) → Pexels B-roll ({visual_type})")
                elif infographic_path:
                    # Allow Gemini only for safe, non-technical types
                    _STEM_SAFE_INFOGRAPHIC = {"example", "story", "analogy"}
                    if visual_type in _STEM_SAFE_INFOGRAPHIC and not notebook_id:
                        visual_source = "gemini_infographic"
                        logger.info(f"M6: Seg {seg_id_str} (STEM-safe) → AI infographic ({visual_type})")
                    else:
                        visual_source = "nlm_slide" if notebook_id else "fallback_slide"
                        logger.warning(f"M6: Seg {seg_id_str} (STEM) → Blocking Gemini for '{visual_type}'. Using {visual_source}.")
                else:
                    visual_source = "fallback_slide"
                    logger.warning(f"M6: Seg {seg_id_str} (STEM) → NLM+Gemini both failed. Using fallback_slide.")
            else:
                # Non-STEM: normal routing
                if infographic_path:
                    visual_source = "gemini_infographic"
                    logger.info(f"M6: Seg {seg_id_str} → AI infographic ({visual_type})")
                else:
                    visual_source = "pexels_broll"
                    logger.info(f"M6: Seg {seg_id_str} → Pexels B-roll ({visual_type})")

            # ── Fallback slide (used by renderer if both Pexels and infographic fail) ──
            slide_path = os.path.join(self.output_dir, f"slide_{segment.segment_id}.png")
            try:
                self.generator.generate_slide(
                    title=segment.concept,
                    content=segment.visual_content_spec,
                    output_path=slide_path,
                )
            except Exception as e:
                logger.warning(f"M6: Fallback slide failed for {segment.segment_id}: {e}")

            # ── Pexels keywords ──────────────────────────────────────────────
            lookup_id = seg_id_str.replace("seg_", "")
            search_terms = keywords_map.get(lookup_id)
            if not search_terms or not isinstance(search_terms, list):
                search_terms = [
                    segment.concept,
                    "educational visualization",
                    "learning background",
                    "abstract science",
                ]

            # ── Narration-anchor enforcement ──────────────────────────────────
            # Ensure the visual spec references the narration content explicitly.
            # This prevents the M6B image generator from drifting to generic imagery.
            narration_anchor = segment.narration[:150].strip()
            content_spec_anchored = (
                f"{segment.visual_content_spec} "
                f"[NARRATION CONTEXT: '{narration_anchor}...'] "
                f"The visual must directly illustrate what is being described in this narration."
            )

            # ── Sequential reveal logic (unchanged from original) ─────────────
            content_spec = content_spec_anchored
            reveal_sequential = False
            elements = []
            if (
                "reveal:sequential" in content_spec.lower()
                or content_spec.count(",") >= 3
                or content_spec.count(";") >= 2
            ):
                reveal_sequential = True
                delimiter = ";" if ";" in content_spec else ","
                raw_elements = [e.strip() for e in content_spec.split(delimiter) if e.strip()]
                elements = [e.replace("reveal:sequential", "").strip() for e in raw_elements]
                elements = [e for e in elements if e]

            visual_plan.append({
                "segment_id": segment.segment_id,
                "visual_type": visual_type,
                "visual_source": visual_source,
                "nlm_slide_path": nlm_slide_path,        # NLM slide PNG (highest priority)
                "infographic_path": infographic_path,    # Gemini infographic (fallback 1)
                "content_spec": content_spec_anchored,
                "duration_seconds": segment.duration_seconds,
                "image_path": slide_path,                # fallback slide
                "pexels_keywords": search_terms,
                "narration_context": segment.narration[:200],
                "reveal_sequential": reveal_sequential,
                "elements": elements,
            })

        infographic_count = sum(
            1 for v in visual_plan if v["visual_source"] == "gemini_infographic"
        )
        broll_count = len(visual_plan) - infographic_count
        logger.success(
            f"M6: Visual plan complete — "
            f"{infographic_count} AI infographics, {broll_count} B-roll segments."
        )
        return visual_plan

    async def _generate_keywords_map(self, script: FullScript) -> dict:
        """Batch-generate Pexels search keywords for all segments via LLM."""
        try:
            keywords_raw = await self.llm.generate_text(
                self._build_keywords_prompt(script), temperature=0.1
            )
        except Exception as e:
            logger.error(f"M6: LLM failed to generate keywords: {e}. Using concept fallback.")
            return {}

        try:
            import re
            import json
            match = re.search(r"\{.*\}", keywords_raw, re.DOTALL)
            raw_map = json.loads(match.group(0)) if match else {}
            return {
                str(k).strip().replace("ID ", "").replace("seg_", ""): v
                for k, v in raw_map.items()
            }
        except Exception as e:
            logger.warning(f"M6: Failed to parse keywords JSON: {e}")
            return {}

    def _build_keywords_prompt(self, script: FullScript) -> str:
        segments_info = "\n".join([
            f"ID {s.segment_id}: '{s.concept}'\nNarration: {s.narration}\nVisual Spec: {s.visual_content_spec}\n---"
            for s in script.segments
        ])

        return f"""
Act as a Visual Director for a high-end educational YouTube channel.
Your task: for each lesson segment, generate Pexels B-roll keywords that are ANCHORED 
to what the narration is saying at that EXACT moment.

CRITICAL RULE — NARRATION SYNC:
The keywords for each segment must describe a visual that a viewer would expect to see 
while HEARING that segment's narration. If the narration says "imagine a treasure hunt", 
the visual must show a treasure hunt or a map — NOT a generic science lab.

ANTI-PATTERNS (these will cause a poor evaluation score):
- Generic visuals: "education", "science", "knowledge", "abstract" → REJECTED
- Mismatched visuals: narration talks about vectors, visual shows a forest → REJECTED
- Photographic imagery for math/physics: narration explains a formula, visual shows people → REJECTED

CORRECT APPROACH:
- Read the narration first, identify the CORE ACTION or CONCEPT being described right now
- Generate keywords that show that specific action/concept
- For math/physics: prefer "animation", "diagram", "schematic", "graph" keywords

Example:
Narration: "A vector has both magnitude AND direction — unlike a scalar, which only has size."  
Keywords: ["arrow with magnitude label diagram", "vector vs scalar comparison animation", 
           "physics vector direction illustration", "force direction arrow graphic", 
           "mathematical vector schematic dark background"]

Segments to process:
{segments_info}

Return ONLY a flat JSON object where keys are the numeric IDs and values are arrays of 5 keyword strings.
Example: {{"1": ["scene 1", "scene 2", "scene 3", "scene 4", "scene 5"]}}
"""
