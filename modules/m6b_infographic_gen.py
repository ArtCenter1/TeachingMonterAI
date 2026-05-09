"""
M6B InfographicGen — Gemini Native Image Generation for Script-Aligned Visuals

Replaces generic Pexels B-roll with dynamically generated, narration-accurate
educational infographics using stable Gemini models.

Architecture:
  generate_segment_infographic(segment, style) → PNG path
  InfographicGenerator.generate_all(script) → list of (segment_id, path)

Models used (in priority order, all from GOOGLE_API_KEY_POOL):
  1. gemini-2.0-flash       (free tier, experimental)
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

from modules.llm_client import get_gemini_pool
from keyrotator.pool import KeyPool, KeyState


# ── Style prompt templates ──────────────────────────────────────────────────

_STYLE_PROMPTS = {
    "blueprint": (
        "Style: dark navy blueprint background (#0a1628), white fine-line diagrams, "
        "cyan accent labels (#00d4ff), amber highlight text (#ffa500). "
        "Technical, precise, like an engineering schematic or 3Blue1Brown visualization. "
        "Use clean arrows, boxes, and callout labels. Dark background is mandatory."
    ),
    "nature": (
        "Style: warm cream or parchment paper background (#fdf5e6), high-quality botanical "
        "and scientific illustrations. Realistic but stylized drawings (like a modern naturalist's "
        "field guide). Earthy palette: olive green, terracotta, soft browns. "
        "Clean, elegant serif labels. Organic, high-fidelity, no messy lines."
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

def _select_style(visual_type: str, subject: Optional[str] = None) -> str:
    """Pick style based on visual_type; optionally refine by subject."""
    env_style = os.getenv("INFOGRAPHIC_STYLE", "").strip().lower()
    if env_style and env_style in _STYLE_PROMPTS:
        return env_style

    # Subject-based overrides (Highest Priority)
    if subject:
        subject_lower = subject.lower()
        if any(s in subject_lower for s in ["biology", "nature", "environment", "taxonomy", "anatomy", "evolution", "biodiversity"]):
            return "nature"
        if any(s in subject_lower for s in ["history", "archaeology", "social"]):
            return "sketchbook"
        if any(s in subject_lower for s in ["math", "statistics", "economics", "physics", "logic"]):
            return "clean_slide"
        if any(s in subject_lower for s in ["computer", "engineering", "tech", "coding", "robot"]):
            return "blueprint"

    # Type-based defaults
    vt = str(visual_type).lower().strip()
    if any(t in vt for t in ["diagram", "concept", "map"]):
        return "blueprint"
    if any(t in vt for t in ["story", "lesson", "intro"]):
        return "illustrated"
    if any(t in vt for t in ["data", "chart", "slide"]):
        return "clean_slide"
        
    return "blueprint"  # Default


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

INSTRUCTIONS:
1. FOCUS: The image must precisely illustrate the KEY CONCEPT using the requested style.
2. TEXT USAGE — CRITICAL RULE:
   Keep text EXTREMELY minimal to avoid AI generation artifacts. 
   ONLY use text for essential mathematical labels (e.g., "f(x)", "f'(x) = 0", "Max", "Min"). 
   Do NOT generate sentences, paragraphs, or long titles. 
   Render any requested math symbols EXACTLY as requested without typos.
3. QUALITY: Ensure the diagram is technically accurate to the subject matter.
4. COMPOSITION: Centered layout with clear margins. Professional educational graphics only.
5. NO PHOTOREALISM: Stick strictly to the specified illustration style. NO generic stock photos.
6. CLARITY: The graphic should make a student immediately understand the concept in 5 seconds.
"""


# ── Core generator ──────────────────────────────────────────────────────────

class InfographicGenerator:
    """
    Generates educational infographic PNGs for video segments using Gemini image API.
    Falls back to None (triggering Pexels B-roll fallback) on API failure.
    """

    # Primary model — "Nano Banana Pro" for high-quality infographics and diagrams
    PRIMARY_MODEL = "gemini-2.0-flash-preview-image-generation"
    # Fallback — "Nano Banana 2" 
    FALLBACK_MODEL = "gemini-2.0-flash-exp"

    def __init__(self, output_dir: str = "temp/visuals/infographics"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self._enabled = os.getenv("INFOGRAPHIC_ENABLED", "true").lower() == "true"
        self.pool = get_gemini_pool()
        logger.info(
            f"[M6B] InfographicGenerator initialized. "
            f"Enabled={self._enabled}, output={self.output_dir}, keys={self.pool.get_status()['total_keys']}"
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

        # Try models in sequence
        for model in [self.PRIMARY_MODEL, self.FALLBACK_MODEL, "pollinations"]:
            # Retry each model up to 3 times with different keys
            for attempt in range(3):
                entry = None
                try:
                    if model == "pollinations":
                        logger.info(f"[M6B] Attempting free Pollinations.ai fallback for '{concept}'")
                        result = await asyncio.to_thread(self._call_pollinations_image, prompt, out_path)
                    else:
                        entry = self.pool.get_key()
                        if not entry:
                            logger.error("[M6B] No Gemini keys available in pool")
                            break
                        
                        result = await asyncio.to_thread(
                            self._call_gemini_image, prompt, model, out_path, entry.key
                        )

                    if result:
                        if entry:
                            self.pool.report_success(entry)
                        elapsed = time.time() - t0
                        logger.success(
                            f"[M6B] ✓ Infographic ready: {out_path} ({elapsed:.1f}s, model={model})"
                        )
                        return out_path
                except Exception as e:
                    err_msg = str(e).lower()
                    
                    # Handle pool rotation for Gemini errors
                    if entry and model != "pollinations":
                        code = 500
                        if "429" in err_msg: code = 429
                        elif "503" in err_msg or "service unavailable" in err_msg or "high demand" in err_msg:
                            code = 503
                        elif "403" in err_msg: code = 403
                        elif "402" in err_msg: code = 402
                        
                        if code in (429, 503, 403, 402):
                            self.pool.report_error(entry, code, str(e))
                            logger.warning(f"[M6B] Gemini {code} for {model} (attempt {attempt+1}), rotating key...")
                            await asyncio.sleep(2 * (attempt + 1))
                            continue

                    logger.warning(f"[M6B] Model {model} failed for {segment_id} on attempt {attempt+1}: {e}")
                    if attempt < 2:
                        await asyncio.sleep(1)
                    else:
                        break # Go to next model

        logger.error(f"[M6B] All models/attempts failed for segment {segment_id} — using B-roll fallback")
        return None

    def _call_gemini_image(self, prompt: str, model: str, out_path: str, api_key: str) -> bool:
        """
        Synchronous Gemini image API call (run in thread via asyncio.to_thread).
        Returns True on success, raises on failure.
        """
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key)

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

    def _call_pollinations_image(self, prompt: str, out_path: str) -> bool:
        """
        Fallback to free, auth-less Pollinations API when Gemini quota is exhausted.
        This ensures the pipeline remains autonomous even on a 100% free setup.
        """
        import urllib.request
        import urllib.parse
        
        # Pollinations uses the prompt in the URL path. 
        # We cap the prompt length to avoid URL-too-long errors.
        encoded_prompt = urllib.parse.quote(prompt[:1000])
        
        # Request 16:9 1080p resolution matching our contest requirements
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1920&height=1080&nologo=true"
        
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 TeachingMonsterAI'}
        )
        with urllib.request.urlopen(req, timeout=45) as response:
            if response.status == 200:
                with open(out_path, "wb") as f:
                    f.write(response.read())
                return True
            else:
                raise RuntimeError(f"Pollinations API failed with status {response.status}")

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
