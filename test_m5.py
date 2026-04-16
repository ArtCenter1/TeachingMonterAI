import asyncio
from modules.m5_critic import SyntheticStudentTester
from modules.schemas import FullScript, ScriptSegment


async def test_m5():
    tester = SyntheticStudentTester("google/gemini-2.0-flash-exp:free")
    script = FullScript(
        title="Test Script",
        scaffolding_strategy="Intuition-First",
        hook="Welcome to this lesson",
        segments=[
            ScriptSegment(
                segment_id="seg1",
                concept="Test Concept",
                narration="This is a test narration.",
                visual_type="Animation",
                visual_content_spec="Show a diagram",
                duration_seconds=30.0,
                citations=[],
            )
        ],
        checks=["What did you learn?"],
    )
    results = await tester.test_script(script)
    for result in results:
        print(f"Persona: {result['persona']}")
        print(f"Is perfect: {result['is_perfect']}")
        print(f"Gaps: {result['gaps']}")
        print(f"Confusing quotes: {result['confusing_quotes']}")
        print(f"Suggestion: {result['suggested_improvement']}")
        print("---")


if __name__ == "__main__":
    asyncio.run(test_m5())
