import time
import uuid
import asyncio
import os
import traceback
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header, Request
from fastapi.staticfiles import StaticFiles
from typing import Optional
from loguru import logger

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Add a file logger for persistent debugging
logger.add("pipeline.log", rotation="10 MB")

from modules.schemas import GenerationRequest, GenerationResponse
from modules.m1_sourcing import SourcingModule
from modules.m2_persona import PersonaParser
from modules.m3_planner import ConceptPlanner
from modules.m4_generator import ScriptGenerator
from modules.m5_critic import CIDPPCritic
from modules.m6_multimodal import MultimodalPlanner
from modules.m7_renderer import VideoRenderer
from modules.m8_logger import FeedbackLogger

app = FastAPI(title="Teaching Monster AI Agent API")

# Mount the output directory to serve static video files
app.mount("/output", StaticFiles(directory="temp/output"), name="output")

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
async def generate_video(
    request_data: GenerationRequest, 
    request: Request,
    x_dry_run: Optional[str] = Header(None, alias="X-Dry-Run")
):
    # 0. Competition Dashboard Dry-Run Check
    if x_dry_run == "true":
        logger.info("Dry-Run detected. Returning mandatory mock response.")
        return GenerationResponse(
            video_url="https://example.com/test.mp4",
            subtitle_url="https://example.com/test.srt",
            supplementary_url=None,
            generation_time_seconds=0
        )

    run_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        logger.info(f"Starting generation for run_id: {run_id}")

        # 1. Parallel call M1 (Sourcing) and M2 (Persona)
        logger.info("Stage 1 & 2: Sourcing and Persona Parsing")
        m1_task = asyncio.create_task(m1.source(request_data.course_requirement))
        m2_task = asyncio.create_task(m2.parse(request_data.student_persona))
        
        fact_bundle, student_model = await asyncio.gather(m1_task, m2_task)

        # 3. Concept Planning
        logger.info("Stage 3: Concept Planning")
        concept_graph = await m3.plan(request_data.course_requirement, student_model)

        # 4. Script Generation
        logger.info("Stage 4: Script Generation")
        script = await m4.generate(concept_graph, student_model, fact_bundle)

        # 5. CIDPP Critic Review
        logger.info("Stage 5: CIDPP Critic Review")
        critic_scores = await m5.review(script, student_model)

        # 6. Multimodal Planning
        logger.info("Stage 6: Multimodal Planning")
        visual_plan = await m6.plan_visuals(script)

        # 7. Video & Subtitle Rendering
        logger.info("Stage 7: Video/Subtitle Rendering")
        render_results = await m7.render(visual_plan, script, run_id=run_id)
        
        video_filename = render_results.get("video", "error")
        subtitle_filename = render_results.get("subtitles", "error")

        # 8. Construct Public URLs
        base_url = str(request.base_url).rstrip("/")
        public_video_url = f"{base_url}/output/{video_filename}"
        public_subtitle_url = f"{base_url}/output/{subtitle_filename}"
        
        generation_time = int(time.time() - start_time)
        
        # 9. Feedback Logging
        logger.info(f"Stage 9: Logging results for {run_id}")
        run_data = {
            "request": request_data.dict(),
            "student_model": student_model.dict(),
            "concept_graph": concept_graph.dict(),
            "critic_scores": critic_scores.dict(),
            "video_url": public_video_url,
            "subtitle_url": public_subtitle_url,
            "generation_time_seconds": generation_time
        }
        await m8.log_run(run_id, run_data)

        return GenerationResponse(
            video_url=public_video_url,
            subtitle_url=public_subtitle_url,
            supplementary_url=fact_bundle.study_guide_url,
            generation_time_seconds=generation_time
        )

    except Exception as e:
        logger.exception(f"FATAL PIPELINE ERROR for run_id {run_id}: {str(e)}")
        # We still return a valid response object if possible, or raise
        raise HTTPException(status_code=500, detail=f"Internal Pipeline Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    if not GOOGLE_API_KEY:
        logger.warning("GOOGLE_API_KEY not found in environment. Real AI modules will fail.")
    uvicorn.run(app, host="0.0.0.0", port=8000)
