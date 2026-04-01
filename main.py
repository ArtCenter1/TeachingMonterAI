import time
import uuid
import asyncio
import os
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
from modules.schemas import GenerationRequest, GenerationResponse
from modules.m1_sourcing import SourcingModule
from modules.m2_persona import PersonaParser
from modules.m3_planner import ConceptPlanner
from modules.m4_generator import ScriptGenerator
from modules.m5_critic import CIDPPCritic
from modules.m6_multimodal import MultimodalPlanner
from modules.m7_renderer import VideoRenderer
from modules.m8_logger import FeedbackLogger
from loguru import logger

app = FastAPI(title="Teaching Monster AI Agent API")

# Initialize modules
m1 = SourcingModule()
m2 = PersonaParser()
m3 = ConceptPlanner()
m4 = ScriptGenerator()
m5 = CIDPPCritic()
m6 = MultimodalPlanner()
m7 = VideoRenderer()
m8 = FeedbackLogger()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/generate", response_model=GenerationResponse)
async def generate_video(request: GenerationRequest):
    start_time = time.time()
    run_id = str(uuid.uuid4())
    logger.info(f"Starting generation for run_id: {run_id}")

    try:
        # 1. Parallel call M1 (Sourcing) and M2 (Persona)
        logger.info("Stage 1 & 2: Sourcing and Persona Parsing")
        m1_task = asyncio.create_task(m1.source(request.course_requirement))
        m2_task = asyncio.create_task(m2.parse(request.student_persona))
        
        fact_bundle, student_model = await asyncio.gather(m1_task, m2_task)

        # 3. Concept Planning
        logger.info("Stage 3: Concept Planning")
        concept_graph = await m3.plan(request.course_requirement, student_model)

        # 4. Script Generation
        logger.info("Stage 4: Script Generation")
        script = await m4.generate(concept_graph, student_model, fact_bundle)

        # 5. CIDPP Critic
        logger.info("Stage 5: CIDPP Critic Review")
        critic_scores = await m5.review(script, student_model)
        # In MVP, we just proceed. In Phase 2, we implement the revision loop here.

        # 6. Multimodal Planning
        logger.info("Stage 6: Multimodal Planning")
        visual_plan = await m6.plan_visuals(script)

        # 7. Video Rendering
        logger.info("Stage 7: Video Rendering")
        # In a real app, this might be a background task, 
        # but the API contract expects the URL in the response.
        video_url = await m7.render(visual_plan, script)

        generation_time = int(time.time() - start_time)
        
        # 8. Feedback Logging
        logger.info("Stage 8: Feedback Logging")
        run_data = {
            "request": request.dict(),
            "student_model": student_model.dict(),
            "concept_graph": concept_graph.dict(),
            "critic_scores": critic_scores.dict(),
            "video_url": video_url,
            "generation_time_seconds": generation_time
        }
        await m8.log_run(run_id, run_data)

        return GenerationResponse(
            video_url=video_url,
            supplementary_url=fact_bundle.study_guide_url,
            generation_time_seconds=generation_time
        )

    except Exception as e:
        logger.error(f"Error in generation pipeline: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    if not GOOGLE_API_KEY:
        logger.warning("GOOGLE_API_KEY not found in environment. Real AI modules will fail.")
    uvicorn.run(app, host="0.0.0.0", port=8000)
