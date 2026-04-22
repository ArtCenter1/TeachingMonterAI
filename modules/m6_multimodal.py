import os
from typing import List, Dict, Any
from .schemas import FullScript, ScriptSegment
from utils.visuals import SlideGenerator
from .llm_client import LLMClient
from loguru import logger

class MultimodalPlanner:
    def __init__(self, output_dir="temp/visuals"):
        self.generator = SlideGenerator()
        self.output_dir = output_dir
        self.llm = LLMClient()
        os.makedirs(self.output_dir, exist_ok=True)

    async def plan_visuals(self, script: FullScript) -> List[Dict[str, Any]]:
        visual_plan = []
        
        # 1. Batch generate search keywords for all segments
        logger.info("M6: Planning Pexels search keywords for segments...")
        keywords_prompt = self._build_keywords_prompt(script)
        keywords_raw = await self.llm.generate_text(keywords_prompt, temperature=0.1)
        
        # Parse result
        try:
            import re
            import json
            match = re.search(r'\{.*\}', keywords_raw, re.DOTALL)
            raw_map = json.loads(match.group(0)) if match else {}
            # Normalize keys to string and strip any whitespace/prefixes the LLM might add
            keywords_map = {str(k).strip().replace("ID ", "").replace("seg_", ""): v for k, v in raw_map.items()}
        except Exception as e:
            logger.warning(f"M6: Failed to parse keywords JSON: {e}")
            keywords_map = {}

        for i, segment in enumerate(script.segments):
            slide_path = os.path.join(self.output_dir, f"slide_{segment.segment_id}.png")
            
            # 2. Generate fallback slide
            try:
                self.generator.generate_slide(
                    title=segment.concept,
                    content=segment.visual_content_spec,
                    output_path=slide_path
                )
            except Exception as e:
                logger.error(f"M6: Slide generation failed for segment {segment.segment_id}: {e}")

            # 3. Assemble visual entry
            # Normalize segment_id for lookup
            lookup_id = str(segment.segment_id).replace("seg_", "")
            
            # Fallback chain: [LLM-provided] -> [narration-derived] -> [concept-derived] -> [subject-generic]
            search_terms = keywords_map.get(lookup_id)
            
            if not search_terms or not isinstance(search_terms, list):
                # Local fallback if LLM failed or ID mismatch
                search_terms = [
                    segment.concept, 
                    "educational visualization",
                    "learning background",
                    "abstract science"
                ]
                
            visual_plan.append({
                "segment_id": segment.segment_id,
                "visual_type": segment.visual_type,
                "content_spec": segment.visual_content_spec,
                "duration_seconds": segment.duration_seconds,
                "image_path": slide_path,
                "pexels_keywords": search_terms,
                "narration_context": segment.narration[:200] # For downstream debugging
            })
            
        logger.success(f"M6: Visual plan complete with {len(visual_plan)} segments.")
        return visual_plan

    def _build_keywords_prompt(self, script: FullScript) -> str:
        segments_info = "\n".join([
            f"ID {s.segment_id}: '{s.concept}'\nNarration: {s.narration}\nVisual Spec: {s.visual_content_spec}\n---"
            for s in script.segments
        ])
        
        return f"""
Act as a Visual Director for a high-end educational YouTube channel.
Your task is to extract concrete, search-friendly visual keywords from the narration of each lesson segment.

Rules:
1. Keywords must be highly specific to the *narration* context.
2. Avoid abstract words like "education", "science", "knowledge".
3. Use realistic B-roll scene descriptions.
4. Provide 5 distinct keywords/phrases per segment.

Example:
Narration: "Imagine the heart as a double-pump, pushing oxygenated blood to the brain."
Keywords: ["human heart animation", "blood cells flowing", "circulatory system", "medical visualization heart", "pumping heart close up"]

Segments to process:
{segments_info}

Return ONLY a flat JSON object where keys are the numeric IDs and values are arrays of 5 keyword strings.
Example: {{"1": ["scene 1", "scene 2", "scene 3", "scene 4", "scene 5"]}}
"""
