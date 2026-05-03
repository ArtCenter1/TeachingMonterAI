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
                    segment_id=str(seg.segment_id),
                    visual_content_spec=seg.visual_content_spec,
                    output_dir=self.output_dir,
                )
                for seg in script.segments
            ]
            slide_results = await asyncio.gather(*slide_tasks, return_exceptions=True)
            for seg, result in zip(script.segments, slide_results):
                if isinstance(result, str) and result:
                    nlm_slide_map[str(seg.segment_id)] = result
            logger.info(f"M6: NLM slides generated: {len(nlm_slide_map)}/{len(script.segments)}")

        for i, segment in enumerate(script.segments):
            # ── Route visual source ──────────────────────────────────────────
            visual_type = str(segment.visual_type).lower().strip()
            seg_id_str = str(segment.segment_id)

            # Priority: NLM slide → Gemini infographic → Pexels B-roll
            nlm_slide_path = nlm_slide_map.get(seg_id_str)
            infographic_path = infographic_map.get(seg_id_str)

            if nlm_slide_path:
                visual_source = "nlm_slide"
                logger.info(f"M6: Seg {seg_id_str} → NLM slide")
            elif infographic_path is not None:
                visual_source = "gemini_infographic"
                logger.info(
                    f"M6: Seg {seg_id_str} → AI infographic ({visual_type})"
                )
            else:
                visual_source = "pexels_broll"
                logger.info(
                    f"M6: Seg {seg_id_str} → Pexels B-roll ({visual_type})"
                )

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

            # ── Sequential reveal logic (unchanged from original) ─────────────
            content_spec = segment.visual_content_spec
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
                "content_spec": segment.visual_content_spec,
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
Your task is to extract concrete, search-friendly visual keywords from the narration of each lesson segment.
These keywords will be used for B-roll video search AND background music matching.

Rules:
1. Keywords must be highly specific to the *narration* context.
2. Avoid abstract words like "education", "science", "knowledge".
3. Use realistic B-roll scene descriptions (useful also for audio mood matching).
4. Provide 5 distinct keywords/phrases per segment.

Example:
Narration: "Imagine the heart as a double-pump, pushing oxygenated blood to the brain."
Keywords: ["human heart animation", "blood cells flowing", "circulatory system", "medical visualization heart", "pumping heart close up"]

Segments to process:
{segments_info}

Return ONLY a flat JSON object where keys are the numeric IDs and values are arrays of 5 keyword strings.
Example: {{"1": ["scene 1", "scene 2", "scene 3", "scene 4", "scene 5"]}}
"""
