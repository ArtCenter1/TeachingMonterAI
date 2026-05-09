import asyncio
import os
import uuid
import argparse
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# Add logging to file to match main.py
logger.add("pipeline.log", rotation="10 MB")

from modules.schemas import GenerationRequest
from modules.m1_sourcing import SourcingModule
from modules.m2_persona import PersonaParser
from modules.m3_planner import ConceptPlanner
from modules.m4_generator import ScriptGenerator
from modules.m5_critic import CIDPPCritic
from modules.m6_multimodal import MultimodalPlanner
from modules.m7_renderer import VideoRenderer
from modules.m8_logger import FeedbackLogger

async def run_full_pipeline(subject, requirement, persona="High school student", notebook_id=None):
    run_id = f"manual-{uuid.uuid4().hex[:8]}"
    logger.info(f"Starting Manual Pipeline Run | Run ID: {run_id} | Subject: {subject} | Notebook: {notebook_id}")
    
    # ... (rest of the code remains same until script creation)
    # Note: the script is selected by M5, but M4 generates variants.
    # In run_pipeline.py, scripts are generated in Stage 4.
    # We should ensure notebook_id is in the FullScript objects created by M4.
    # Actually M4.generate_variants should handle this if we pass it.
    
    # Initialize Modules
    m1 = SourcingModule()
    m2 = PersonaParser()
    m3 = ConceptPlanner()
    m4 = ScriptGenerator()
    m5 = CIDPPCritic()
    m6 = MultimodalPlanner()
    m7 = VideoRenderer()
    m8 = FeedbackLogger()

    request_data = GenerationRequest(
        course_requirement=requirement,
        student_persona=persona
    )

    try:
        logger.info("Stage 1: Sourcing")
        fact_bundle = await m1.source(request_data.course_requirement)
        if notebook_id:
            fact_bundle.metadata["notebook_id"] = notebook_id
            logger.info(f"Manual override: Injected notebook_id {notebook_id} into metadata.")
        
        logger.info("Stage 2: Persona")
        student_model = await m2.parse(request_data.student_persona)
        
        logger.info("Stage 3: Planner")
        concept_graph = await m3.plan(request_data.course_requirement, student_model)
        
        logger.info("Stage 4: Generator")
        scripts = await m4.generate_variants(concept_graph, student_model, fact_bundle)
        
        # Inject subject into scripts for M6 to use
        for s in scripts:
            s.subject = subject

        logger.info("Stage 5: Critic")
        script, selection_log = await m5.score_variants(
            scripts, student_model,
            fact_bundle=fact_bundle,
            concept_graph=concept_graph
        )
        
        # Ensure subject is preserved after critic selection
        script.subject = subject
        logger.info(f"Selected Strategy: {script.scaffolding_strategy} | Subject: {script.subject}")

        logger.info("Stage 6: Multimodal Planning")
        visual_plan = await m6.plan_visuals(script)
        
        # Audit visual plan (visual_plan is a list of dicts)
        for i, seg_plan in enumerate(visual_plan):
            source = seg_plan.get("visual_source")
            v_type = seg_plan.get("visual_type")
            path = seg_plan.get("infographic_path")
            logger.info(f"Segment {i+1} Type: {v_type} | Source: {source} | Path: {path}")

        logger.info("Stage 7: Rendering (Skipped for visual-only audit, or run if needed)")
        # render_results = await m7.render(visual_plan, script, run_id=run_id)
        
        logger.info("Stage 8: Logging (Partial)")
        run_data = {
            "request": request_data.model_dump(),
            "student_model": student_model.model_dump(),
            "selected_strategy": script.scaffolding_strategy,
            "script": script.model_dump(),
            "visual_plan": visual_plan,
            "generation_time_seconds": 0 
        }
        await m8.log_run(run_id, run_data, selection_log=selection_log)
        
        logger.success(f"Pipeline run complete. Visuals in temp/visuals/infographics/")
        return visual_plan

    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Teaching Monster AI pipeline.")
    parser.add_argument("--subject", type=str, required=True, help="Curriculum subject (e.g. Taxonomy)")
    parser.add_argument("--requirement", type=str, required=True, help="Specific requirement (e.g. Diversity of Life)")
    parser.add_argument("--persona", type=str, default="High school student", help="Student persona")
    parser.add_argument("--notebook_id", type=str, default=None, help="Notebook ID for grounded assets")
    
    args = parser.parse_args()
    
    asyncio.run(run_full_pipeline(args.subject, args.requirement, args.persona, args.notebook_id))
