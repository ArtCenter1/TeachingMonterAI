"""
M6B InfographicGen — Gemini Native Image Generation for Script-Aligned Visuals

Replaces generic Pexels B-roll with dynamically generated, narration-accurate
educational infographics using gemini-2.5-flash-image.

Architecture:
  generate_segment_infographic(segment, style) → PNG path
  InfographicGenerator.generate_all(script) → list of (segment_id, path)

Models used (in priority order, all from GOOGLE_API_KEY_POOL):
  1. gemini-2.5-flash-image   (free tier, fast)
  2. gemini-2.0-flash-exp     (fallback if image model unavailable)

Style options:
  blueprint   — Dark navy + white/cyan technical diagram  (STEM, CS, Physics)
  sketchbook  — Hand-drawn on cream background            (Biology, History)
  clean_slide — White bg + colorful icons, Kurzgesagt-   (Math, General)
  illustrated — Full illustrated scene with characters   (Social Science)
"""

import os
import time
import random
import asyncio
from typing import Optional
from loguru import logger

# ── Google GenAI SDK ────────────────────────────────────────────────────────

def _get_google_key() -> Optional[str]:
    """Pull a random key from GOOGLE_API_KEY_POOL, falling back to GOOGLE_API_KEY."""
    pool_raw = os.getenv("GOOGLE_API_KEY_POOL", "").strip()
    if pool_raw:
        keys = [k.strip() for k in pool_raw.split(",") if k.strip()]
        if keys:
            return random.choice(keys)
    return os.getenv("GOOGLE_API_KEY", "").strip() or None


def _make_genai_client():
    """Create a google.genai Client instance with a valid API key."""
    from google import genai
    key = _get_google_key()
    if not key:
        raise RuntimeError("No GOOGLE_API_KEY / GOOGLE_API_KEY_POOL configured.")
    return genai.Client(api_key=key)


# ── Style prompt templates ──────────────────────────────────────────────────

_STYLE_PROMPTS = {
    "blueprint": (
        "Style: dark navy blueprint background (#0a1628), white fine-line diagrams, "
        "cyan accent labels (#00d4ff), amber highlight text (#ffa500). "
        "Technical, precise, like an engineering schematic or 3Blue1Brown visualization. "
        "Use clean arrows, boxes, and callout labels. Dark background is mandatory."
    ),
    "sketchbook": (
        "Style: warm cream/ivory background, dark ink hand-drawn diagrams, "
        "subtle watercolor accent fills (muted greens, blues, oranges). "
        "Looks like a scientist's illustrated notebook page. "
        "Include subtle ruled lines in the background."
    ),
    "clean_slide": (
        "Style: clean white background, colorful flat-design icons and shapes, "
        "bold sans-serif typography in multiple colors. "
        "Inspired by Kurzgesagt infographics. Vibrant and modern."
    ),
    "illustrated": (
        "Style: friendly illustrated scene, soft gradient background, "
        "cartoon characters or objects demonstrating the concept. "
        "Warm, approachable, educational. Like a children's science book spread."
    ),
}

# Visual type → default style mapping
_TYPE_TO_STYLE = {
    "diagram":   "blueprint",
    "concept":   "blueprint",
    "data":      "clean_slide",
    "slide":     "clean_slide",
    "action":    "illustrated",
    "demo":      "sketchbook",
    "real_world": "illustrated",
}


def _select_style(visual_type: str, subject: Optional[str] = None) -> str:
    """Pick style based on visual_type; optionally refine by subject."""
    env_style = os.getenv("INFOGRAPHIC_STYLE", "").strip().lower()
    if env_style and env_style in _STYLE_PROMPTS:
        return env_style

    # Subject-level override
    if subject:
        subject_lower = subject.lower()
        if any(s in subject_lower for s in ["biology", "history", "anatomy"]):
            return "sketchbook"
        if any(s in subject_lower for s in ["math", "statistics", "economics"]):
            return "clean_slide"

    return _TYPE_TO_STYLE.get(visual_type, "blueprint")


# ── Prompt builder ──────────────────────────────────────────────────────────

def _build_prompt(concept: str, narration: str, visual_content_spec: str,
                  visual_type: str, style: str) -> str:
    """Construct a rich infographic generation prompt from segment data."""
    style_desc = _STYLE_PROMPTS.get(style, _STYLE_PROMPTS["blueprint"])
    narration_excerpt = narration[:400] if narration else ""

    return f"""Create a 16:9 widescreen educational infographic slide (1920×1080 resolution).

TOPIC: {concept}
KEY CONCEPT TO VISUALIZE: {visual_content_spec}
NARRATION CONTEXT: "{narration_excerpt}"

{style_desc}

MANDATORY RULES — follow exactly:
1. Diagram the concept directly — NO generic stock photo backgrounds.
2. Include 3–5 bold key terms as labeled callouts with arrows.
3. Show data flow, causality, or process steps where relevant.
4. All text must be large enough to read at 1080p (minimum 28pt equivalent).
5. Keep the composition clean — no clutter, no unnecessary decorations.
6. DO NOT include the word "infographic" or "slide" in the image.
7. Aspect ratio MUST be 16:9 (landscape), filling the entire frame.

The infographic should make a student immediately understand the concept in 5 seconds of viewing.
Think: What would a skilled science communicator draw on a whiteboard to explain this?
"""


# ── Core generator ──────────────────────────────────────────────────────────

class InfographicGenerator:
    """
    Generates educational infographic PNGs for video segments using Gemini image API.
    Falls back to None (triggering Pexels B-roll fallback) on API failure.
    """

    # Primary model — free tier, handles infographics well
    PRIMARY_MODEL = "gemini-2.5-flash-preview-05-20"
    # Fallback — older flash image model
    FALLBACK_MODEL = "gemini-2.0-flash-exp"

    def __init__(self, output_dir: str = "temp/visuals/infographics"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self._enabled = os.getenv("INFOGRAPHIC_ENABLED", "true").lower() == "true"
        logger.info(
            f"[M6B] InfographicGenerator initialized. "
            f"Enabled={self._enabled}, output={self.output_dir}"
        )

    async def generate_segment_infographic(
        self,
        segment_id: str,
        concept: str,
        narration: str,
        visual_content_spec: str,
        visual_type: str = "concept",
        subject: Optional[str] = None,
        force_style: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate a single infographic PNG for a lesson segment.

        Returns:
            Path to the saved PNG, or None if generation failed.
        """
        if not self._enabled:
            logger.debug(f"[M6B] Infographic disabled via env — skipping {segment_id}")
            return None

        out_path = os.path.join(self.output_dir, f"infographic_{segment_id}.png")
        if os.path.exists(out_path):
            logger.debug(f"[M6B] Cache hit for {segment_id}")
            return out_path

        style = force_style or _select_style(visual_type, subject)
        prompt = _build_prompt(concept, narration, visual_content_spec, visual_type, style)

        logger.info(f"[M6B] Generating infographic for '{concept}' (style={style})")
        t0 = time.time()

        for model in [self.PRIMARY_MODEL, self.FALLBACK_MODEL]:
            try:
                result = await asyncio.to_thread(
                    self._call_gemini_image, prompt, model, out_path
                )
                if result:
                    elapsed = time.time() - t0
                    logger.success(
                        f"[M6B] ✓ Infographic ready: {out_path} ({elapsed:.1f}s, model={model})"
                    )
                    return out_path
            except Exception as e:
                logger.warning(f"[M6B] Model {model} failed for {segment_id}: {e}")
                await asyncio.sleep(2)  # brief backoff before fallback model

        logger.error(f"[M6B] All models failed for segment {segment_id} — using B-roll fallback")
        return None

    def _call_gemini_image(self, prompt: str, model: str, out_path: str) -> bool:
        """
        Synchronous Gemini image API call (run in thread via asyncio.to_thread).
        Returns True on success, raises on failure.
        """
        from google import genai
        from google.genai import types

        client = _make_genai_client()

        response = client.models.generate_content(
            model=model,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        saved = False
        for part in response.parts:
            if part.inline_data is not None:
                # Save the image bytes
                img_data = part.inline_data.data
                if isinstance(img_data, str):
                    import base64
                    img_data = base64.b64decode(img_data)
                with open(out_path, "wb") as f:
                    f.write(img_data)
                saved = True
                break
            elif part.text:
                logger.debug(f"[M6B] Model text response: {part.text[:200]}")

        if not saved:
            raise RuntimeError("Gemini returned no image data in response")
        return True

    async def generate_all(
        self,
        segments,  # list of ScriptSegment-like objects
        subject: Optional[str] = None,
    ) -> dict:
        """
        Generate infographics for all segments concurrently (with rate-limit semaphore).

        Returns:
            dict mapping segment_id → PNG path (or None if failed)
        """
        # Limit concurrent Gemini image calls to avoid quota exhaustion
        sem = asyncio.Semaphore(3)

        async def _gen_one(seg) -> tuple:
            async with sem:
                path = await self.generate_segment_infographic(
                    segment_id=str(seg.segment_id),
                    concept=seg.concept,
                    narration=seg.narration,
                    visual_content_spec=seg.visual_content_spec,
                    visual_type=getattr(seg, "visual_type", "concept"),
                    subject=subject,
                )
                # Small stagger to respect per-minute quota
                await asyncio.sleep(1)
                return (str(seg.segment_id), path)

        tasks = [_gen_one(seg) for seg in segments]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"[M6B] Gather exception: {r}")
            else:
                seg_id, path = r
                output[seg_id] = path

        success = sum(1 for v in output.values() if v is not None)
        logger.info(f"[M6B] Infographic generation complete: {success}/{len(segments)} succeeded")
        return output
