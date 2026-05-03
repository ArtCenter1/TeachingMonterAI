"""
nlm_studio.py — Autonomous NLM Studio wrapper for Teaching Monster v0.7.0

Design rules:
- Every public method returns None on failure (never raises to caller)
- Every NLM call wrapped in asyncio.wait_for with hard timeout
- preflight_check() called once at startup; sets NLM_AVAILABLE globally
- Headless cookie refresh via scripts/refresh_auth.py (no browser window)
"""

import os
import asyncio
import subprocess
import time
from typing import Optional, List, Dict, Any
from loguru import logger

# ── Global availability flag ────────────────────────────────────────────────
_NLM_AVAILABLE: bool = False

def is_available() -> bool:
    return _NLM_AVAILABLE

# ── Timeouts (read from env, with safe defaults) ────────────────────────────
def _slide_timeout() -> int:
    return int(os.getenv("NLM_SLIDE_TIMEOUT_S", "480"))

def _audio_timeout() -> int:
    return int(os.getenv("NLM_AUDIO_TIMEOUT_S", "600"))

def _quiz_timeout() -> int:
    return int(os.getenv("NLM_QUIZ_TIMEOUT_S", "300"))


# ── Auth helpers ─────────────────────────────────────────────────────────────

def _auth_file_path() -> str:
    return os.path.expanduser("~/.notebooklm/storage_state.json")


def _auth_age_hours() -> float:
    path = _auth_file_path()
    if not os.path.exists(path):
        return float("inf")
    return (time.time() - os.path.getmtime(path)) / 3600


def _run_refresh_auth() -> bool:
    """
    Run scripts/refresh_auth.py headlessly.
    Uses ~/.notebooklm/browser_profile/ to rotate tokens without a browser window.
    Returns True if refresh succeeded.
    """
    script = os.path.join(os.path.dirname(__file__), "..", "scripts", "refresh_auth.py")
    script = os.path.normpath(script)
    if not os.path.exists(script):
        logger.warning("NLM: refresh_auth.py not found. Skipping refresh.")
        return False
    try:
        import sys
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            logger.info("NLM: Cookie refresh succeeded.")
            return True
        else:
            logger.warning(f"NLM: Cookie refresh failed: {result.stderr[:300]}")
            return False
    except Exception as e:
        logger.warning(f"NLM: Cookie refresh exception: {e}")
        return False


async def preflight_check() -> bool:
    """
    Called once at pipeline startup.
    1. Check if NLM is enabled via env flag
    2. Check cookie age — if > 5 days, silently refresh via refresh_auth.py
    3. Test with a lightweight API call (notebooks.list)
    4. Set global _NLM_AVAILABLE flag
    Never raises. Returns True if NLM is usable.
    """
    global _NLM_AVAILABLE

    if os.getenv("NLM_SLIDES_ENABLED", "true").lower() != "true" and \
       os.getenv("NLM_AUDIO_ENABLED", "true").lower() != "true":
        logger.info("NLM: Disabled via env flags. Using Gemini/Cartesia fallback.")
        _NLM_AVAILABLE = False
        return False

    # Check and refresh cookies if stale (only if env var NOT set)
    if os.getenv("NOTEBOOKLM_AUTH_JSON"):
        logger.info("NLM: Using environment variable authentication. Skipping file-age check.")
    else:
        age = _auth_age_hours()
        logger.info(f"NLM: Auth cookie age: {age:.1f} hours")
        if age > 12:  # 12 hours
            logger.info("NLM: Cookies older than 12 hours. Running headless refresh...")
            _run_refresh_auth()

    # Test API connectivity
    try:
        from notebooklm import NotebookLMClient
        async with await NotebookLMClient.from_storage() as client:
            await asyncio.wait_for(client.notebooks.list(), timeout=30)
        logger.success("NLM: Preflight check passed. NLM Studio AVAILABLE.")
        _NLM_AVAILABLE = True
        return True
    except Exception as e:
        logger.warning(f"NLM: Preflight check failed ({type(e).__name__}): {e}. Attempting emergency refresh...")
        
        # If it failed, maybe the cookie expired prematurely. Try refreshing once.
        if not os.getenv("NOTEBOOKLM_AUTH_JSON"):
            refreshed = _run_refresh_auth()
            if refreshed:
                try:
                    async with await NotebookLMClient.from_storage() as client:
                        await asyncio.wait_for(client.notebooks.list(), timeout=30)
                    logger.success("NLM: Preflight check passed after emergency refresh. NLM Studio AVAILABLE.")
                    _NLM_AVAILABLE = True
                    return True
                except Exception as e2:
                    logger.warning(f"NLM: Preflight check still failed after refresh: {e2}. Using fallback pipeline.")
        
        _NLM_AVAILABLE = False
        return False


# ── Notebook management ──────────────────────────────────────────────────────

async def ensure_notebook(topic: str, domain: str) -> Optional[str]:
    """
    Create a new NLM notebook for this pipeline run.
    Returns notebook_id or None on failure.
    """
    if not _NLM_AVAILABLE:
        return None
    try:
        from notebooklm import NotebookLMClient
        async with await NotebookLMClient.from_storage() as client:
            title = f"Teaching Monster: {topic} ({domain})"
            nb = await asyncio.wait_for(
                client.notebooks.create(title=title), timeout=30
            )
            nb_id = getattr(nb, "id", None) or getattr(nb, "notebook_id", None)
            logger.info(f"NLM: Created notebook '{title}' id={nb_id}")
            return nb_id
    except Exception as e:
        logger.warning(f"NLM: ensure_notebook failed: {e}")
        return None


async def add_sources_to_notebook(notebook_id: str, texts: List[str]) -> None:
    """Inject curriculum text chunks as sources into the notebook."""
    if not _NLM_AVAILABLE or not notebook_id:
        return
    try:
        from notebooklm import NotebookLMClient
        async with await NotebookLMClient.from_storage() as client:
            for i, text in enumerate(texts[:5]):  # max 5 sources
                await asyncio.wait_for(
                    client.sources.add_text(notebook_id, f"Source {i+1}", text, wait=True),
                    timeout=60
                )
                logger.debug(f"NLM: Added source {i+1} to {notebook_id}")
    except Exception as e:
        logger.warning(f"NLM: add_sources failed: {e}")


# ── Slide generation ─────────────────────────────────────────────────────────

_SLIDE_PROMPT_TEMPLATE = """Create a 1-slide educational infographic for "{concept}".

Design: Dark navy background (#0a1628). TITLE: bold slab serif (Roboto Slab), color #00d4ff.
Body text: white (#f5f5f5). One key 3D diagram or labeled technical illustration.
Chalk-style dashed connector lines link elements to surrounding labels.
Dashed cyan border (#00d4ff). Every element is grounded in curriculum content.

Content to visualize:
{visual_content_spec}

CRITICAL: The infographic must accurately illustrate "{concept}" — no generic imagery.
"""


async def generate_slides(
    notebook_id: str,
    concept: str,
    segment_id: str,
    visual_content_spec: str,
    output_dir: str,
) -> Optional[str]:
    """
    Generate a slide PNG for one script segment using NLM Studio custom report.
    Returns local PNG path or None on failure/timeout.
    Fallback: Gemini infographic (handled by caller).
    """
    if not _NLM_AVAILABLE or not notebook_id:
        return None
    if os.getenv("NLM_SLIDES_ENABLED", "true").lower() != "true":
        return None

    os.makedirs(os.path.join(output_dir, "nlm_slides"), exist_ok=True)
    output_path = os.path.join(output_dir, "nlm_slides", f"slide_{segment_id}.png")

    prompt = _SLIDE_PROMPT_TEMPLATE.format(
        concept=concept,
        visual_content_spec=visual_content_spec[:800]
    )

    try:
        from notebooklm import NotebookLMClient
        from notebooklm.types import ReportFormat

        async with await NotebookLMClient.from_storage() as client:
            task = await asyncio.wait_for(
                client.artifacts.generate_report(
                    notebook_id,
                    report_format=ReportFormat("custom"),
                    custom_prompt=prompt,
                ),
                timeout=_slide_timeout()
            )
            task_id = getattr(task, "task_id", None) or getattr(task, "id", None)
            if task_id:
                await asyncio.wait_for(
                    client.artifacts.wait_for_completion(notebook_id, task_id),
                    timeout=_slide_timeout()
                )
                # Download the artifact image
                await asyncio.wait_for(
                    client.artifacts.download(notebook_id, task_id, output_path),
                    timeout=60
                )
                if os.path.exists(output_path):
                    logger.success(f"NLM: Slide generated → {output_path}")
                    return output_path
        return None
    except asyncio.TimeoutError:
        logger.warning(f"NLM: Slide generation timed out for segment {segment_id}. Using Gemini fallback.")
        return None
    except Exception as e:
        logger.warning(f"NLM: Slide generation failed for {segment_id}: {e}. Using Gemini fallback.")
        return None


# ── Audio generation ─────────────────────────────────────────────────────────

async def generate_audio(notebook_id: str, output_path: str) -> Optional[str]:
    """
    Generate NLM Deep Dive audio overview for the full lesson.
    Returns local MP3 path or None on failure/timeout.
    Fallback: Cartesia TTS per segment (handled by m7_renderer).
    """
    if not _NLM_AVAILABLE or not notebook_id:
        return None
    if os.getenv("NLM_AUDIO_ENABLED", "true").lower() != "true":
        return None

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        from notebooklm import NotebookLMClient
        from notebooklm import AudioFormat, AudioLength

        async with await NotebookLMClient.from_storage() as client:
            task = await asyncio.wait_for(
                client.artifacts.generate_audio(
                    notebook_id,
                    audio_format=AudioFormat.DEEP_DIVE,
                    audio_length=AudioLength.DEFAULT,
                ),
                timeout=60
            )
            task_id = getattr(task, "task_id", None) or getattr(task, "id", None)
            if task_id:
                await asyncio.wait_for(
                    client.artifacts.wait_for_completion(notebook_id, task_id),
                    timeout=_audio_timeout()
                )
                await asyncio.wait_for(
                    client.artifacts.download_audio(notebook_id, output_path),
                    timeout=120
                )
                if os.path.exists(output_path):
                    logger.success(f"NLM: Audio generated → {output_path}")
                    return output_path
        return None
    except asyncio.TimeoutError:
        logger.warning("NLM: Audio generation timed out. Falling back to Cartesia TTS.")
        return None
    except Exception as e:
        logger.warning(f"NLM: Audio generation failed: {e}. Falling back to Cartesia TTS.")
        return None


# ── Quiz generation ──────────────────────────────────────────────────────────

async def generate_quiz(notebook_id: str) -> List[Dict[str, Any]]:
    """
    Generate a quiz from notebook sources.
    Returns list of {question, answer} dicts or [] on failure.
    Used by M5 critic as advisory coverage check only.
    """
    if not _NLM_AVAILABLE or not notebook_id:
        return []

    try:
        from notebooklm import NotebookLMClient

        async with await NotebookLMClient.from_storage() as client:
            task = await asyncio.wait_for(
                client.artifacts.generate_quiz(
                    notebook_id,
                    difficulty="MEDIUM",
                    quantity="STANDARD",
                ),
                timeout=60
            )
            task_id = getattr(task, "task_id", None) or getattr(task, "id", None)
            if task_id:
                await asyncio.wait_for(
                    client.artifacts.wait_for_completion(notebook_id, task_id),
                    timeout=_quiz_timeout()
                )
                artifacts = await asyncio.wait_for(
                    client.artifacts.list(notebook_id),
                    timeout=30
                )
                # Parse quiz text from most recent artifact
                for a in reversed(artifacts):
                    a_type = str(getattr(a, "type", "")).lower()
                    if "quiz" in a_type:
                        text = getattr(a, "text", "") or getattr(a, "content", "")
                        return _parse_quiz_text(text)
        return []
    except asyncio.TimeoutError:
        logger.warning("NLM: Quiz generation timed out. Skipping quiz check.")
        return []
    except Exception as e:
        logger.warning(f"NLM: Quiz generation failed: {e}. Skipping quiz check.")
        return []


def _parse_quiz_text(text: str) -> List[Dict[str, Any]]:
    """Parse Q&A pairs from NLM quiz artifact text."""
    results = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    current_q = None
    for line in lines:
        if line.lower().startswith("q:") or (line.endswith("?") and len(line) > 10):
            current_q = line.lstrip("Qq:").strip()
        elif line.lower().startswith("a:") and current_q:
            results.append({
                "question": current_q,
                "answer": line.lstrip("Aa:").strip()
            })
            current_q = None
    return results
