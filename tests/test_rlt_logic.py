import pytest
import asyncio
from modules.m5b_probe_generator import ProbeGenerator
from modules.m5_critic import NaiveStudentEvaluator, CIDPPCritic
from modules.schemas import FullScript, FactBundle, ConceptGraph, ConceptNode, ScriptSegment, StudentModel, RLTScore
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_probe_generator_format():
    """Test that ProbeGenerator returns the expected list of probes."""
    fact_bundle = FactBundle(
        facts=[
            {"id": "f1", "claim": "The speed of light is 299,792,458 m/s.", "concepts": ["speed of light"]},
            {"id": "f2", "claim": "Gravity on Earth is 9.8 m/s^2.", "concepts": ["gravity"]}
        ]
    )
    concept_graph = ConceptGraph(
        nodes=[
            ConceptNode(concept="speed of light", prerequisites=[], misconceptions=[], visual_type="animation", duration_minutes=1.0),
            ConceptNode(concept="gravity", prerequisites=[], misconceptions=[], visual_type="diagram", duration_minutes=1.0)
        ],
        total_duration_minutes=2.0
    )

    # Mock LLM response
    mock_llm = AsyncMock()
    mock_llm.generate_text.return_value = """
    [
        {"question": "What is the speed of light?", "correct_answer": "299,792,458 m/s", "concept": "speed of light"},
        {"question": "What is Earth's gravity?", "correct_answer": "9.8 m/s^2", "concept": "gravity"}
    ]
    """
    
    with patch('modules.m5b_probe_generator.LLMClient', return_value=mock_llm):
        pg = ProbeGenerator()
        probes = await pg.generate(fact_bundle, concept_graph)
        assert len(probes) == 2
        assert probes[0].question == "What is the speed of light?"
        assert probes[1].correct_answer == "9.8 m/s^2"

@pytest.mark.asyncio
async def test_naive_student_scoring():
    """Test NaiveStudentEvaluator's keyword matching logic."""
    script = FullScript(
        title="Light Speed",
        scaffolding_strategy="Intuition-First",
        hook="Ready to go fast?",
        segments=[
            ScriptSegment(
                segment_id="s1",
                concept="speed of light",
                narration="Light travels at 300,000 km/s roughly, but exactly 299,792,458 meters per second.", 
                visual_type="animation",
                visual_content_spec="Speed lines",
                duration_seconds=10.0
            )
        ]
    )
    
    mock_probe = MagicMock()
    mock_probe.question = "How fast is light?"
    mock_probe.correct_answer = "299,792,458"
    
    # Mock LLM response from the student
    mock_llm = AsyncMock()
    mock_llm.generate_text.return_value = '[{"question": "How fast is light?", "student_answer": "The script says it is 299,792,458 meters per second."}]'
    
    with patch('modules.m5_critic.LLMClient', return_value=mock_llm):
        student = NaiveStudentEvaluator()
        result = await student.evaluate(script, [mock_probe])
        assert result.probes_correct == 1
        assert result.comprehension_score == 1.0

@pytest.mark.asyncio
async def test_critic_blend_math():
    """Test that CIDPPCritic calculates the blend correctly (0.7/0.3)."""
    # Mock CIDPP review (all 10s = 50 total = 1.0 normalised)
    mock_review = MagicMock()
    mock_review.clarity = 10
    mock_review.integrity = 10
    mock_review.depth = 10
    mock_review.practicality = 10
    mock_review.pertinence = 10
    mock_review.revisions = []
    
    # Create critic AFTER patching or mock its methods
    critic = CIDPPCritic()
    critic.review = AsyncMock(return_value=mock_review)
    
    # Mock RLT score (0.5 score)
    mock_rlt = RLTScore(probes_total=2, probes_correct=1, comprehension_score=0.5, student_answers=[])
    critic.naive_student.evaluate = AsyncMock(return_value=mock_rlt)
    
    # Mock Probe Gen and FeedbackLogger (graduation check)
    with patch('modules.m5_critic.probe_gen.generate', AsyncMock(return_value=[MagicMock(), MagicMock()])), \
         patch('modules.m5_critic.FeedbackLogger') as mock_fb_class:
        
        mock_fb = mock_fb_class.return_value
        mock_fb.get_rlt_run_count.return_value = 0 # Ensure we stay at 0.7/0.3
        
        with patch.dict('os.environ', {'RLT_BLEND_WEIGHT': '0.30'}):
            scripts = [FullScript(
                title="Test", 
                scaffolding_strategy="S1", 
                hook="test hook", 
                segments=[]
            )]
            best, logs = await critic.score_variants(
                scripts, 
                StudentModel(
                    level="high_school", 
                    personas=[], 
                    cognitive_load_budget=5.0, 
                    modality_preference="visual", 
                    abstraction_tolerance=0.5
                ),
                fact_bundle=MagicMock(),
                concept_graph=MagicMock()
            )
            
            # Math: (0.7 * 1.0) + (0.3 * 0.5) = 0.7 + 0.15 = 0.85
            assert logs[0]['blended_score'] == pytest.approx(0.85)
            assert logs[0]['cidpp_normalised'] == 1.0
            assert logs[0]['rlt_comprehension_score'] == 0.5
            assert logs[0]['cidpp_weight'] == 0.7
            assert logs[0]['rlt_weight'] == 0.3
