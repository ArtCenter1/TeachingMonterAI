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
            # Assuming a standard extract_json utility exists in modules/utils.py
            # If not, we'll implement a local regex extraction
            import re
            import json
            match = re.search(r'\{.*\}', keywords_raw, re.DOTALL)
            keywords_map = json.loads(match.group(0)) if match else {}
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
            # Fallback keywords to concept if LLM failed
            search_terms = keywords_map.get(str(segment.segment_id), [segment.concept, "education", "abstract"])
            if not isinstance(search_terms, list):
                search_terms = [str(search_terms)]
                
            visual_plan.append({
                "segment_id": segment.segment_id,
                "visual_type": segment.visual_type,
                "content_spec": segment.visual_content_spec,
                "duration_seconds": segment.duration_seconds,
                "image_path": slide_path,
                "pexels_keywords": search_terms
            })
            
        logger.success(f"M6: Visual plan complete with {len(visual_plan)} segments.")
        return visual_plan

    def _build_keywords_prompt(self, script: FullScript) -> str:
        segments_info = "\n".join([
            f"ID {s.segment_id}: '{s.concept}' (Visual: {s.visual_content_spec})"
            for s in script.segments
        ])
        
        return f"""
Act as a visual director for an educational video. 
For each segment below, provide 3 descriptive search keywords for Pexels Video.
Keywords must be realistic B-roll scenes, not abstract diagrams.
Examples: "chalkboard math formulas", "forest aerial view", "microscope bacteria", "students in library".

Segments:
{segments_info}

Return ONLY a flat JSON object where keys are the IDs and values are arrays of 3 keyword strings.
Example: {{"1": ["sun setting", "clouds moving", "horizon"]}}
"""
