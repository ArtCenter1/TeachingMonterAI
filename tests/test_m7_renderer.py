import os
import pytest
import asyncio
from modules.m7_renderer import VideoRenderer
from modules.schemas import FullScript, ScriptSegment

@pytest.mark.asyncio
async def test_renderer_initialization():
    """Verifies renderer directories are created."""
    renderer = VideoRenderer(output_dir="temp/test_output")
    assert os.path.exists("temp/test_output")
    assert os.path.exists("temp/audio")
    assert os.path.exists("temp/video")

@pytest.mark.asyncio
async def test_renderer_mock_run(monkeypatch):
    """
    Tests a basic render pass with mocked external calls:
    - Mocks Cartesia TTS
    - Mocks Pexels lookup
    - Mocks MoviePy clip creation
    """
    renderer = VideoRenderer(output_dir="temp/test_output")
    
    # Mock script
    script = FullScript(
        title="Test Lesson",
        scaffolding_strategy="Inquiry-based",
        hook="Welcome to the test!",
        checks=["What did you learn?"],
        segments=[
            ScriptSegment(
                segment_id="seg1",
                concept="Testing",
                narration="This is a test of the Teaching Monster AI rendering pipeline.",
                visual_type="video",
                visual_content_spec="A cute monster teaching science",
                duration_seconds=5.0
            )
        ]
    )
    
    # Mock visual plan
    visual_plan = [
        {
            "segment_id": "seg1",
            "search_query": "science",
            "type": "video",
            "concept": "Testing"
        }
    ]
    
    # Mock internal methods to avoid API calls
    async def mock_generate_audio(segment, dir):
        path = os.path.join(dir, f"{segment.segment_id}.mp3")
        with open(path, "wb") as f:
            f.write(b"fake audio data")
        return path
        
    async def mock_source_visual(visual, duration):
        # We need a real MoviePy object if we want to test concatenation,
        # but for a unit test, we can just return a ColorClip
        from moviepy.editor import ColorClip
        return ColorClip(size=(1080, 1920), color=(0,0,0), duration=duration)

    monkeypatch.setattr(renderer, "_generate_audio", mock_generate_audio)
    monkeypatch.setattr(renderer, "_source_visual", mock_source_visual)
    
    # Run render
    # Note: concatenate_videoclips will still be called.
    # We might need to mock it if MoviePy is not installed on the host.
    try:
        results = await renderer.render(visual_plan, script, run_id="test_run")
        assert "video" in results
        print("\n[SUCCESS] Renderer logic verified (with mocks).")
    except Exception as e:
        pytest.fail(f"Renderer failed even with mocks: {e}")

if __name__ == "__main__":
    asyncio.run(test_renderer_initialization())
    asyncio.run(test_renderer_mock_run(None))
