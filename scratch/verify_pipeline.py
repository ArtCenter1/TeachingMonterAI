import sys
import os
import json
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

from modules.schemas import ConceptGraph, FullScript
from modules.m8_logger import ErrorLogger

def verify_foundation_observability():
    logger.info("Starting Foundation & Observability Verification (Priority 3 & 4)")
    
    # 1. Check schemas for new fields
    from modules.schemas import CIDPPScores, ConceptNode
    
    scores = CIDPPScores(clarity=8, integrity=9, depth=7, practicality=6, pertinence=8, adaptability=7, engagement=8)
    logger.success("CIDPPScores successfully validated with Adaptability and Engagement")
    
    node = ConceptNode(concept="Test", prerequisites=[], misconceptions=[], visual_type="diagram", duration_minutes=1.0, is_disambiguation=True)
    logger.success("ConceptNode successfully validated with is_disambiguation flag")
    
    # 2. Verify M3 Planner Disambiguation Logic
    from modules.m3_planner import ConceptPlanner
    from modules.schemas import StudentModel, StudentLevel, ModalityPreference
    
    mock_student = StudentModel(
        level=StudentLevel.MIDDLE_SCHOOL,
        cognitive_load_budget=0.7,
        modality_preference=ModalityPreference.VISUAL,
        abstraction_tolerance=0.5
    )
    
    planner = ConceptPlanner()
    prompt = planner._build_prompt("Pendulums", mock_student)
    if "is_disambiguation" in prompt:
        logger.success("M3 Planner prompt includes Disambiguation instructions")
    else:
        logger.error("M3 Planner prompt MISSING Disambiguation instructions")

    # 3. Verify M4 Generator Persona Logic
    from modules.m4_generator import ScriptGenerator
    generator = ScriptGenerator()
    gen_prompt = generator._build_prompt(node, "Middle School student", [], mock_student)
    if "Cognitive Load" in gen_prompt and "Modality" in gen_prompt:
        logger.success("M4 Generator prompt includes Persona constraints")
    else:
        logger.error("M4 Generator prompt MISSING Persona constraints")

    # 4. Verify M8 Logger AV Mismatch
    error_logger = ErrorLogger()
    if hasattr(error_logger, "log_av_mismatch"):
        logger.success("M8 Logger has log_av_mismatch capability")
    else:
        logger.error("M8 Logger MISSING log_av_mismatch method")

    # 5. Check Curriculum Support
    curriculum_path = "resources/curriculum/physics/kinematics_and_dynamics.md"
    if os.path.exists(curriculum_path):
        logger.success(f"Curriculum expanded: {curriculum_path} exists")
    else:
        logger.error(f"Curriculum MISSING: {curriculum_path}")

    logger.info("Verification Complete.")

if __name__ == "__main__":
    verify_foundation_observability()
