import asyncio
import os
from modules.m7_renderer import VideoRenderer
from modules.schemas import FullScript, ScriptSegment

async def test_render_notebooklm_flow():
    renderer = VideoRenderer()
    run_id = "test_nb_flow"
    
    # Mock Script with total_audio_path
    script = FullScript(
        title="Test NotebookLM Flow",
        scaffolding_strategy="Case Study",
        hook="Welcome to the test.",
        segments=[
            ScriptSegment(
                segment_id="1",
                concept="Introduction",
                narration="This is the first segment.",
                visual_type="Animation",
                visual_content_spec="A friendly monster waving.",
                duration_seconds=5.0
            ),
            ScriptSegment(
                segment_id="2",
                concept="Deep Dive",
                narration="This is the second segment, which is a bit longer.",
                visual_type="Diagram",
                visual_content_spec="A flowchart of the process.",
                duration_seconds=10.0
            )
        ],
        checks=[],
        total_audio_path=os.path.abspath("resources/bg_music.mp3") # Using a real mp3 as dummy
    )
    
    # Mock Visual Plan (List of Dicts)
    visual_plan = [
        {
            "segment_id": "1",
            "video_prompt": "A friendly monster waving in a classroom.",
            "overlay_text": "Intro",
            "duration_seconds": 5.0,
            "visual_source": "pexels_broll"
        },
        {
            "segment_id": "2",
            "video_prompt": "A scientific flowchart showing process.",
            "overlay_text": "Process",
            "duration_seconds": 10.0,
            "visual_source": "pexels_broll"
        }
    ]
    
    print(f"Starting render with total_audio_path: {script.total_audio_path}")
    results = await renderer.render(visual_plan, script, run_id=run_id)
    print(f"Render results: {results}")

if __name__ == "__main__":
    asyncio.run(test_render_notebooklm_flow())
