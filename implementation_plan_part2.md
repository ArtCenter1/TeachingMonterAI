# Agent Execution Plan — Part 2: Core Module Implementation
## Teaching Monster v0.7.0 NLM Studio Integration

---

## TASK 7: Create `modules/nlm_studio.py`

**File:** `D:\My_Projects\TeachingMonsterAI\modules\nlm_studio.py`

Create this file in full:

```python
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
        result = subprocess.run(
            ["python", script],
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

    # Check and refresh cookies if stale
    age = _auth_age_hours()
    logger.info(f"NLM: Auth cookie age: {age:.1f} hours")
    if age > 120:  # 5 days
        logger.info("NLM: Cookies stale (>5 days). Running headless refresh...")
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
        logger.warning(f"NLM: Preflight check failed ({type(e).__name__}): {e}. Using fallback pipeline.")
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
```

---

## TASK 8: Modify `modules/m1_sourcing.py`

**File:** `D:\My_Projects\TeachingMonsterAI\modules\m1_sourcing.py`

### Change 1: Add import at top (after existing imports)
Add after `from .notebooklm_manager import notebooklm_manager`:
```python
from . import nlm_studio
```

### Change 2: Replace Stage 0 NLM block

Find this block (lines ~102-124):
```python
        # Stage 0: Attempt NotebookLM Sourcing (New Primary Path)
        domain = self._get_domain_for_topic(topic) or "General"
        try:
            logger.info("Attempting NotebookLM sourcing...")
            
            # 1. Create Notebook
            notebook_id = await notebooklm_manager.create_notebook_for_topic(topic, domain)
            if notebook_id:
                # 2. Upload initial context (Local RAG chunks + Web Search snippets)
                # This provides NotebookLM with enough base context to "research" properly
                rag_chunks = retriever.retrieve(topic, domain=domain, n_results=5)
                await notebooklm_manager.add_sources(notebook_id, rag_chunks)
                
                # 3. Get Facts
                facts = await notebooklm_manager.ask_for_structured_facts(notebook_id, topic)
                if facts:
                    logger.info(f"NotebookLM sourcing successful: {len(facts)} facts retrieved")
                    fact_bundle = FactBundle(facts=facts)
                    # Attach notebook_id and subject to fact_bundle for later modules
                    fact_bundle.metadata = {"notebook_id": notebook_id, "subject": domain}
                    return await self._verify_and_enhance_facts(fact_bundle, topic)
        except Exception as e:
            logger.error(f"NotebookLM sourcing failed: {str(e)}")
```

Replace with:
```python
        # Stage 0: Attempt NotebookLM Sourcing (Primary Path)
        domain = self._get_domain_for_topic(topic) or "General"
        notebook_id = None
        try:
            logger.info("Attempting NotebookLM sourcing...")
            
            # 1. Create Notebook via nlm_studio (autonomous, with preflight)
            notebook_id = await nlm_studio.ensure_notebook(topic, domain)
            if not notebook_id:
                # Try legacy manager as backup
                notebook_id = await notebooklm_manager.create_notebook_for_topic(topic, domain)

            if notebook_id:
                # 2. Upload RAG chunks as sources
                rag_chunks = retriever.retrieve(topic, domain=domain, n_results=5)
                await nlm_studio.add_sources_to_notebook(notebook_id, rag_chunks)
                await notebooklm_manager.add_sources(notebook_id, rag_chunks)
                
                # 3. Get Facts from NLM chat
                facts = await notebooklm_manager.ask_for_structured_facts(notebook_id, topic)
                if facts:
                    logger.info(f"NotebookLM sourcing successful: {len(facts)} facts retrieved")
                    fact_bundle = FactBundle(facts=facts)
                    fact_bundle.metadata = {"notebook_id": notebook_id, "subject": domain}
                    return await self._verify_and_enhance_facts(fact_bundle, topic)
        except Exception as e:
            logger.error(f"NotebookLM sourcing failed: {str(e)}")
```

---

## TASK 9: Modify `modules/m6_multimodal.py`

**File:** `D:\My_Projects\TeachingMonsterAI\modules\m6_multimodal.py`

### Change 1: Add import at top
After `from .m6b_infographic_gen import InfographicGenerator`, add:
```python
from . import nlm_studio
```

### Change 2: Replace `plan_visuals` method body

In the `plan_visuals` method, after the line:
```python
        infographic_map = await self.infographic_gen.generate_all(
            script.segments, subject=subject
        )
```

Add this block (before the `for i, segment in enumerate` loop):
```python
        # Get notebook_id from script metadata (set by M1)
        notebook_id = getattr(script, "notebook_id", None)
        nlm_slide_map: dict = {}
        
        # Pre-generate NLM slides concurrently if available
        if notebook_id and nlm_studio.is_available():
            logger.info("M6: Pre-generating NLM slides for all segments...")
            slide_tasks = [
                nlm_studio.generate_slides(
                    notebook_id=notebook_id,
                    concept=seg.concept,
                    segment_id=str(seg.segment_id),
                    visual_content_spec=seg.visual_content_spec,
                    output_dir=self.output_dir,
                )
                for seg in script.segments
            ]
            slide_results = await asyncio.gather(*slide_tasks, return_exceptions=True)
            for seg, result in zip(script.segments, slide_results):
                if isinstance(result, str) and result:
                    nlm_slide_map[str(seg.segment_id)] = result
            logger.info(f"M6: NLM slides generated: {len(nlm_slide_map)}/{len(script.segments)}")
```

### Change 3: Update visual routing in the for loop

Find:
```python
            infographic_path = infographic_map.get(seg_id_str)
            # FORCE infographic if it was successfully generated, regardless of type
            use_infographic = (infographic_path is not None)

            if use_infographic:
                visual_source = "gemini_infographic"
```

Replace with:
```python
            # Priority: NLM slide → Gemini infographic → Pexels B-roll
            nlm_slide_path = nlm_slide_map.get(seg_id_str)
            infographic_path = infographic_map.get(seg_id_str)

            if nlm_slide_path:
                visual_source = "nlm_slide"
                logger.info(f"M6: Seg {seg_id_str} → NLM slide")
            elif infographic_path is not None:
                visual_source = "gemini_infographic"
```

### Change 4: Add `nlm_slide_path` to visual plan dict

Find:
```python
            visual_plan.append({
                "segment_id": segment.segment_id,
                "visual_type": visual_type,
                "visual_source": visual_source,          # NEW: routing flag
                "infographic_path": infographic_path,    # NEW: path to AI image (or None)
```

Replace with:
```python
            visual_plan.append({
                "segment_id": segment.segment_id,
                "visual_type": visual_type,
                "visual_source": visual_source,
                "nlm_slide_path": nlm_slide_path,        # NLM slide PNG (highest priority)
                "infographic_path": infographic_path,    # Gemini infographic (fallback 1)
```

---

## TASK 10: Modify `modules/m7_renderer.py`

**File:** `D:\My_Projects\TeachingMonsterAI\modules\m7_renderer.py`

### Change 1: Add import at top
After `from .m6c_avatar_gen import get_avatar_compositor`, add:
```python
from . import nlm_studio
```

### Change 2: Update visual routing in `render()` method

Find:
```python
            visual_source = visual.get("visual_source", "pexels_broll")

            if visual_source == "gemini_infographic":
                infographic_path = visual.get("infographic_path")
                if infographic_path and os.path.exists(infographic_path):
                    logger.info(f"M7: Segment {i} → AI infographic")
                    self._render_infographic_segment(
```

Replace with:
```python
            visual_source = visual.get("visual_source", "pexels_broll")

            # NLM slide takes priority over Gemini infographic
            if visual_source == "nlm_slide":
                nlm_slide_path = visual.get("nlm_slide_path")
                if nlm_slide_path and os.path.exists(nlm_slide_path):
                    logger.info(f"M7: Segment {i} → NLM slide")
                    self._render_infographic_segment(
                        infographic_path=nlm_slide_path,
                        audio_path=audio_path,
                        duration=duration,
                        caption=caption,
                        visual=visual,
                        output_path=seg_raw,
                        step=i,
                    )
                else:
                    logger.warning(f"M7: NLM slide missing for seg {i}, fallback to Gemini infographic")
                    infographic_path = visual.get("infographic_path")
                    if infographic_path and os.path.exists(infographic_path):
                        self._render_infographic_segment(
                            infographic_path=infographic_path,
                            audio_path=audio_path,
                            duration=duration,
                            caption=caption,
                            visual=visual,
                            output_path=seg_raw,
                            step=i,
                        )
                    else:
                        broll_path = self._source_visual_path(visual, run_video_dir, i)
                        self._render_segment(
                            broll_path=broll_path, audio_path=audio_path,
                            duration=duration, caption=caption,
                            visual=visual, output_path=seg_raw, step=i,
                        )
            elif visual_source == "gemini_infographic":
                infographic_path = visual.get("infographic_path")
                if infographic_path and os.path.exists(infographic_path):
                    logger.info(f"M7: Segment {i} → AI infographic")
                    self._render_infographic_segment(
```

---

## TASK 11: Modify `modules/m5_critic.py`

**File:** `D:\My_Projects\TeachingMonsterAI\modules\m5_critic.py`

### Change 1: Add import
At top, after `from loguru import logger`, add:
```python
from . import nlm_studio
```

### Change 2: Add NLM quiz check at end of `score_variants` method

Find the return statement at the end of `score_variants` (after `scored_data.sort`):
```python
        best_variant = scored_data[0]["script"]
```

Add before that line:
```python
        # NLM Quiz cross-check (advisory — never blocks video generation)
        notebook_id = getattr(scripts[0], "notebook_id", None)
        if notebook_id and nlm_studio.is_available():
            try:
                quiz_items = await nlm_studio.generate_quiz(notebook_id)
                if quiz_items:
                    logger.info(f"M5: NLM quiz generated {len(quiz_items)} Q&As for coverage check")
                    # Log quiz stats — future: compare against script terms for gap detection
                    scored_data[0]["nlm_quiz_count"] = len(quiz_items)
            except Exception as e:
                logger.warning(f"M5: NLM quiz check failed (non-blocking): {e}")
```

---

## TASK 12: Modify `main.py` — Add NLM preflight at startup

**File:** `D:\My_Projects\TeachingMonsterAI\main.py`

### Change 1: Add import
Find the existing imports block. Add after the other module imports:
```python
from modules import nlm_studio
```

### Change 2: Add preflight call in startup event

Find the `@app.on_event("startup")` handler or the FastAPI startup logic.
Add the preflight call:
```python
@app.on_event("startup")
async def startup_event():
    logger.info("Teaching Monster v0.7.0 starting up...")
    # NLM Studio preflight — sets global availability flag (silent, no human needed)
    nlm_available = await nlm_studio.preflight_check()
    logger.info(f"NLM Studio: {'AVAILABLE' if nlm_available else 'UNAVAILABLE (fallback mode)'}")
```

If a startup handler already exists, just add the two NLM lines into it.

### Change 3: Pass notebook_id through pipeline

In the `generate` endpoint (or wherever M1 → M6 → M7 are chained), after M1 returns `fact_bundle`:
```python
    # Pass notebook_id from M1 result to script object for M6/M7
    notebook_id = fact_bundle.metadata.get("notebook_id") if fact_bundle.metadata else None
    if notebook_id:
        # Trigger NLM audio generation early (parallel with M4/M5)
        audio_output_path = f"temp/audio/{run_id}/nlm_overview.mp3"
        nlm_audio_task = asyncio.create_task(
            nlm_studio.generate_audio(notebook_id, audio_output_path)
        )
```

Then after M5 selects best script, before calling M7:
```python
    # Attach NLM artifacts to script object for M7
    if notebook_id:
        selected_script.notebook_id = notebook_id
        # Await audio task (started in parallel with M4/M5)
        nlm_audio_path = await nlm_audio_task
        if nlm_audio_path:
            selected_script.total_audio_path = nlm_audio_path
            logger.info(f"M7 will use NLM audio: {nlm_audio_path}")
```

---

## TASK 13: One-Time Pre-Contest Auth Setup (Human Step)

Run on dev machine BEFORE contest starts:

```powershell
# In project root (NOT inside Docker)
cd D:\My_Projects\TeachingMonsterAI

# Install notebooklm-py with browser extra
pip install "notebooklm-py[browser]>=0.3.0"
playwright install chromium

# Login (opens browser window — ONE TIME ONLY)
python scripts/nlm.py login

# Verify
python scripts/nlm.py auth-status
python scripts/nlm.py list

# Verify cookie file exists
Get-Item "$env:USERPROFILE\.notebooklm\storage_state.json"

# Start Docker (volume mount shares cookies with container)
docker compose up -d --build

# Verify inside container
docker exec teaching-monster-app python scripts/nlm.py auth-status
docker exec teaching-monster-app python scripts/nlm.py list
```

If all pass → NLM ready for autonomous contest operation.
If Docker step fails → set `NLM_SLIDES_ENABLED=false` and `NLM_AUDIO_ENABLED=false` in `.env` → pipeline falls back to Gemini + Cartesia (proven v0.6.0 behavior).

---

## TASK 14: Verification Tests

After all code changes and Docker rebuild:

```powershell
# Test 1: Auth check inside container
docker exec teaching-monster-app python -c "
import asyncio
from modules import nlm_studio
result = asyncio.run(nlm_studio.preflight_check())
print('NLM Available:', result)
"

# Test 2: Full pipeline with NLM enabled
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "Newton Laws of Motion", "student_persona": "high school student", "subject": "Physics"}'

# Expected: response contains video_url
# Expected logs: "NLM: Slide generated", "NLM: Audio generated" OR fallback messages
# Expected: video background shows Physics diagram (not random Pexels stock)

# Test 3: Fallback (disable NLM, verify pipeline still works)
# Set NLM_SLIDES_ENABLED=false NLM_AUDIO_ENABLED=false in .env, restart container
# Run same curl — should still produce video via Gemini + Cartesia
```
