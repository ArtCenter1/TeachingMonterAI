import asyncio
import os
import uuid
from main import m1, m2, m3, m4, m5, m6, m8
from modules.schemas import GenerationRequest, FullScript
from loguru import logger

async def smoke_test():
    """Run a partial pipeline to verify RLT logging in m8_feedback.json."""
    run_id = f"smoke-{uuid.uuid4().hex[:8]}"
    logger.info(f"Starting RLT Smoke Test | Run ID: {run_id}")
    
    request_data = GenerationRequest(
        course_requirement="The water cycle",
        student_persona="Elementary student, likes emojis",
        model_override="google/gemini-2.0-flash-exp:free"
    )
    
    try:
        # Step-by-step partial pipeline
        logger.info("Stage 1: Sourcing")
        fact_bundle = await m1.source(request_data.course_requirement)
        
        logger.info("Stage 2: Persona")
        student_model = await m2.parse(request_data.student_persona)
        
        logger.info("Stage 3: Planner")
        concept_graph = await m3.plan(request_data.course_requirement, student_model)
        
        logger.info("Stage 4: Generator")
        scripts = await m4.generate_variants(concept_graph, student_model, fact_bundle)
        
        logger.info("Stage 5: Critic (Target for RLT)")
        script, selection_log = await m5.score_variants(
            scripts, student_model,
            fact_bundle=fact_bundle,
            concept_graph=concept_graph
        )
        
        logger.info("Stage 8: Logger (Persist to disk)")
        run_data = {
            "request": request_data.model_dump(),
            "student_model": student_model.model_dump(),
            "selected_strategy": script.scaffolding_strategy,
            "script": script.model_dump(),
            "video_url": "http://mock/video.mp4",
            "generation_time_seconds": 123
        }
        await m8.log_run(run_id, run_data, selection_log=selection_log)
        
        # Verification
        import json
        if os.path.exists("m8_feedback.json"):
            with open("m8_feedback.json", "r") as f:
                logs = json.load(f)
                entry = next((l for l in logs if l["run_id"] == run_id), None)
                if entry:
                    logger.success(f"Log entry found for {run_id}")
                    sel_log = entry.get("selection_log", [])
                    for variant in sel_log:
                        rlt = variant.get("rlt_comprehension_score")
                        logger.info(f"Variant [{variant['strategy']}]: RLT Score = {rlt}")
                        if rlt is not None:
                            logger.success("RLT metric confirmed in m8_feedback.json")
                else:
                    logger.error(f"Run ID {run_id} not found in logs")

    except Exception as e:
        logger.exception(f"Smoke test failed: {e}")

if __name__ == "__main__":
    os.environ["RLT_BLEND_WEIGHT"] = "0.30"
    asyncio.run(smoke_test())
