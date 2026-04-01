import os
from typing import List, Dict, Any
from .schemas import FullScript, ScriptSegment
from utils.visuals import SlideGenerator

class MultimodalPlanner:
    def __init__(self, output_dir="temp/visuals"):
        self.generator = SlideGenerator()
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    async def plan_visuals(self, script: FullScript) -> List[Dict[str, Any]]:
        visual_plan = []
        for i, segment in enumerate(script.segments):
            slide_path = os.path.join(self.output_dir, f"slide_{segment.segment_id}.png")
            
            # Use the generator to create the slide
            self.generator.generate_slide(
                title=segment.concept,
                content=segment.visual_content_spec,
                output_path=slide_path
            )
            
            visual_plan.append({
                "segment_id": segment.segment_id,
                "visual_type": segment.visual_type,
                "content_spec": segment.visual_content_spec,
                "duration_seconds": segment.duration_seconds,
                "image_path": slide_path
            })
        return visual_plan
