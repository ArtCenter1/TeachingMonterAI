import time
import uuid
import asyncio
import os
import json

# ── Pillow ≥10 compatibility: ANTIALIAS was removed, MoviePy still uses it ──
try:
    from PIL import Image as _PILImage
    if not hasattr(_PILImage, "ANTIALIAS"):
        _PILImage.ANTIALIAS = _PILImage.LANCZOS
except ImportError:
    pass

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional
from loguru import logger

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

logger.add("pipeline.log", rotation="10 MB")

from modules.schemas import GenerationRequest, GenerationResponse, AIStudentFeedback
from modules.m1_sourcing import SourcingModule
from modules.m2_persona import PersonaParser
from modules.m3_planner import ConceptPlanner
from modules.m4_generator import ScriptGenerator
from modules.m5_critic import CIDPPCritic
from modules.m6_multimodal import MultimodalPlanner
from modules.m7_renderer import VideoRenderer
from modules.m8_logger import FeedbackLogger, ErrorLogger
from keyrotator import KeyPool, KeyRotatorRouter
from modules.llm_client import get_gemini_pool, get_router_pool


app = FastAPI(title="Teaching Monster AI Agent API", version="0.4.2")

_gemini_pool = get_gemini_pool()
_openrouter_pool = get_router_pool()
app.include_router(KeyRotatorRouter([_gemini_pool, _openrouter_pool]), prefix="/dev")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/output", StaticFiles(directory="temp/output"), name="output")

m1 = SourcingModule()
m2 = PersonaParser()
m3 = ConceptPlanner()
m4 = ScriptGenerator()
m5 = CIDPPCritic()
m6 = MultimodalPlanner()
m7 = VideoRenderer()
m8 = FeedbackLogger()
err_log = ErrorLogger()


@app.get("/health")
@app.head("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def read_root():
    return {"message": "Teaching Monster AI Agent is running. Use /generate for API requests."}


@app.post("/")
async def root_post_proxy(
    request_data: GenerationRequest,
    request: Request,
    x_dry_run: Optional[str] = Header(None, alias="X-Dry-Run"),
):
    """Proxy root POST to /generate. Streaming keeps ngrok alive."""
    return StreamingResponse(
        _run_pipeline_and_stream(request_data, request, x_dry_run),
        media_type="application/json",
    )



async def _run_pipeline_and_stream(request_data, request, x_dry_run):
    """
    Generator that keeps the HTTP connection alive through ngrok by sending
    whitespace bytes every 15 seconds while the pipeline runs.

    ERR_NGROK_3004 root cause: ngrok closes connections that send NO bytes
    for >30s. Fix: begin the chunked response immediately (headers are flushed
    by the first yield), then heartbeat whitespace keeps TCP alive.
    The contest site reads the final JSON line as the real response body.

    Per contest rules: the video file must exist when we return video_url.
    We DO NOT return early — the full pipeline completes before yielding the URL.
    """
    # Dry-run shortcut
    if x_dry_run == "true":
        logger.info("Dry-Run detected. Returning mandatory mock response.")
        payload = GenerationResponse(
            video_url="https://example.com/test.mp4",
            subtitle_url="https://example.com/test.srt",
            supplementary_url=None,
            generation_time_seconds=0,
        ).model_dump_json()
        yield payload
        return

    run_id = str(uuid.uuid4())
    start_time = time.time()
    current_stage = "startup"

    async def pipeline_task():
        nonlocal current_stage
        try:
            logger.info(f"Starting generation for run_id: {run_id}")

            current_stage = "m1_sourcing"
            logger.info("Stage 1: Sourcing")
            fact_bundle = await m1.source(
                request_data.course_requirement,
                search_cx=request_data.search_cx,
                search_api_key=request_data.search_api_key,
            )
            await asyncio.sleep(1)

            current_stage = "m2_persona"
            logger.info("Stage 2: Persona Parsing")
            student_model = await m2.parse(
                request_data.student_persona, model_override=request_data.model_override
            )
            logger.info(f"[HEARTBEAT] {run_id} | M1+M2 complete | Facts: {len(fact_bundle.facts)}")

            current_stage = "m3_planner"
            logger.info("Stage 3: Concept Planning")
            concept_graph = await m3.plan(
                request_data.course_requirement, student_model,
                model_override=request_data.model_override,
            )
            logger.info(f"[HEARTBEAT] {run_id} | M3 complete | Nodes: {len(concept_graph.nodes)}")

            current_stage = "m4_generator"
            logger.info("Stage 4: Multi-Variant Script Generation")
            scripts = await m4.generate_variants(
                concept_graph, student_model, fact_bundle,
                model_override=request_data.model_override,
            )
            logger.info(f"[HEARTBEAT] {run_id} | M4 complete | Variants: {len(scripts)}")

            current_stage = "m5_critic"
            logger.info("Stage 5: CIDPP Critic Selection")
            script, selection_log = await m5.score_variants(
                scripts, student_model, model_override=request_data.model_override
            )
            logger.info(f"[HEARTBEAT] {run_id} | M5 complete | Selected: {script.title}")

            current_stage = "m6_multimodal"
            logger.info("Stage 6: Multimodal Planning")
            visual_plan = await m6.plan_visuals(script)
            logger.info(f"[HEARTBEAT] {run_id} | M6 complete")

            # M7 — must complete BEFORE returning video_url (contest rules)
            current_stage = "m7_renderer"
            logger.info("Stage 7: Video/Subtitle Rendering")
            render_results = await m7.render(visual_plan, script, run_id=run_id)
            logger.info(f"[HEARTBEAT] {run_id} | M7 complete")

            video_filename = render_results.get("video", "error")
            subtitle_filename = render_results.get("subtitles", "error")

            base_url = str(request.base_url).rstrip("/")
            public_video_url = f"{base_url}/output/{video_filename}"
            public_subtitle_url = f"{base_url}/output/{subtitle_filename}"
            generation_time = int(time.time() - start_time)

            current_stage = "m8_logger"
            run_data = {
                "request": request_data.model_dump(),
                "student_model": student_model.model_dump(),
                "concept_graph": concept_graph.model_dump(),
                "selected_strategy": script.scaffolding_strategy,
                "video_url": public_video_url,
                "subtitle_url": public_subtitle_url,
                "generation_time_seconds": generation_time,
            }
            await m8.log_run(run_id, run_data, selection_log=selection_log)

            logger.success(f"Pipeline complete for {run_id} in {generation_time}s")
            return GenerationResponse(
                video_url=public_video_url,
                subtitle_url=public_subtitle_url,
                supplementary_url=fact_bundle.study_guide_url,
                generation_time_seconds=generation_time,
            )

        except Exception as e:
            logger.exception(f"FATAL PIPELINE ERROR for {run_id} at [{current_stage}]: {e}")
            err_log.log_error(
                run_id=run_id, exc=e,
                request_data=request_data.model_dump(),
                failed_stage=current_stage,
            )
            return None  # signal error to outer generator

    # Run pipeline as asyncio task so we can heartbeat concurrently
    task = asyncio.create_task(pipeline_task())

    # Yield whitespace every 15s to keep the ngrok TCP connection alive.
    # The contest site must tolerate leading whitespace before the JSON body
    # (all HTTP clients do — whitespace outside JSON is ignored).
    while not task.done():
        yield " "
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=15)
        except asyncio.TimeoutError:
            pass  # still running — loop and yield another heartbeat
        except Exception:
            break

    result = task.result()
    if result is None:
        # Pipeline failed — yield a JSON error body
        error_body = json.dumps({"detail": f"Pipeline failed at [{current_stage}]"})
        yield error_body
    else:
        yield result.model_dump_json()


@app.post("/generate")
async def generate_video(
    request_data: GenerationRequest,
    request: Request,
    x_dry_run: Optional[str] = Header(None, alias="X-Dry-Run"),
):
    """Streaming response: keeps ngrok connection alive with whitespace heartbeats."""
    return StreamingResponse(
        _run_pipeline_and_stream(request_data, request, x_dry_run),
        media_type="application/json",
    )


@app.post("/feedback/ai-student")
async def submit_ai_student_feedback(feedback: AIStudentFeedback):
    success = m8.add_ai_student_feedback(
        run_id=feedback.run_id,
        ai_student_scores=feedback.ai_student_scores,
        critique_text=feedback.critique_text,
        elo_outcome=feedback.elo_outcome,
    )
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Run ID {feedback.run_id} not found in feedback logs.",
        )
    logger.info(f"AI Student feedback ingested for run_id: {feedback.run_id}")
    return {"status": "feedback ingested"}


@app.get("/dev/strategy-stats")
def get_strategy_stats():
    return {
        "stats": m8.strategy_tracker.get_full_stats(),
        "win_rates": m8.strategy_tracker.get_win_rates(),
    }


if __name__ == "__main__":
    import uvicorn
    if not GOOGLE_API_KEY:
        logger.warning("GOOGLE_API_KEY not found. Real AI modules will fail.")
    uvicorn.run(app, host="0.0.0.0", port=8000)
