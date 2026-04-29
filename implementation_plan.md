# Teaching Monster v0.7.0 — Implementation Plan
## Phase 2: NLM Studio Visual & Audio Integration
## REVISED: Fully Autonomous Operation (No Human Intervention During Contest)

> **Status: AWAITING USER APPROVAL**
> Author: Antigravity AI Agent | April 2026

---

## Critical Constraint: Fully Autonomous Pipeline

> [!IMPORTANT]
> Teaching Monster runs **inside Docker as a standalone autonomous agent** during the contest.
> No IDE, no terminal, no human can intervene once the contest starts.
> Every step in the NLM integration must be **pre-configured, pre-authenticated, and self-healing**.

**This changes the integration model fundamentally:**

| What the plan said | What it must be |
|---|---|
| `python scripts/nlm.py login` (manual browser sign-in) | ❌ Impossible during contest |
| Headless cookie refresh when needed | ✅ Must run at pipeline startup automatically |
| NLM fails → human checks logs | ❌ Impossible |
| NLM fails → automatic fallback to Gemini/Cartesia | ✅ Required — pipeline must always produce output |

---

## Two-Phase Auth Strategy

### Phase A — Pre-Contest Setup (ONE TIME, on dev machine, before contest)

This is the **only human action** required. Done once, stored persistently.

```powershell
# 1. On your dev machine (not Docker), install and login
pip install "notebooklm-py[browser]"
playwright install chromium

# 2. Login interactively (opens browser, you sign in to Google)
python scripts/nlm.py login
# → saves cookies to C:\Users\artce\.notebooklm\storage_state.json

# 3. Check auth is fresh
python scripts/nlm.py auth-status
# → should say "Auth looks fresh"

# 4. Verify it works end-to-end
python scripts/nlm.py create "Teaching Monster Test"
python scripts/nlm.py list
```

The cookie file at `~/.notebooklm/storage_state.json` is then **mounted into Docker as a volume** — it persists across all container restarts and contest runs.

### Phase B — Autonomous Operation (During Contest, Zero Human Touch)

At pipeline startup, `modules/nlm_studio.py` performs a **silent auth preflight**:

```python
async def preflight_check() -> bool:
    """Called once at pipeline start. Returns True if NLM is usable."""
    # 1. Check cookie file exists and age < 7 days
    # 2. Try a lightweight API call (client.notebooks.list())
    # 3. If it fails → set NLM_AVAILABLE = False globally
    # 4. Log result → pipeline uses fallback chain automatically
    # Never raises, never blocks, never requires human input
```

If `preflight_check()` returns `False`, the pipeline **silently degrades**:
- M6 visuals → Gemini infographic (M6B) → Pexels B-roll (existing, tested, reliable)
- M7 narration → Cartesia TTS (existing, tested, reliable)

The video is still generated. The contest submission never fails.

---

## Architecture: Autonomous Visual & Audio Pipeline (v0.7.0)

```
Pipeline Start
    ↓
nlm_studio.preflight_check()           ← silent, no human needed
    ↓ NLM_AVAILABLE = True/False
    ↓
M1: RAG sourcing (ChromaDB, always)
    + if NLM_AVAILABLE: create notebook, inject curriculum as text sources
    ↓
M3: Concept graph
    + if NLM_AVAILABLE: NLM Study Guide seeds concept graph (parallel, with 5-min timeout)
    ↓
M4: Script generation (3 variants)
    ↓
M5: CIDPP critic selects best script
    + if NLM_AVAILABLE: NLM Quiz cross-checks coverage (parallel, advisory only)
    ↓
M6: Visual plan
    → For each segment:
       [Primary]   nlm_studio.generate_slides(concept)  → PNG (8-min timeout)
       [Fallback1] Gemini image generation (M6B)         → PNG
       [Fallback2] Pexels B-roll                         → MP4 clip
       [Fallback3] Color background with text            → solid color
    ↓
M7: Video renderer
    [Primary]   NLM Audio Overview MP3               (10-min timeout)
                → split by segment duration ratios
                → combine with slides (Ken Burns) + subtitles + BGM
    [Fallback]  Cartesia TTS per segment              (existing, tested)
                → combine with slides (Ken Burns) + subtitles + BGM
    ↓
M8: Log run record
    ↓
Contest submission ← always reached, always has a video URL
```

---

## File Changes

### [NEW] `modules/nlm_studio.py` — Autonomous NLM Wrapper

Full async wrapper with:
- `preflight_check()` — silent auth validation at startup:
  1. Check `~/.notebooklm/storage_state.json` age
  2. If cookies > 5 days old → silently run `python scripts/refresh_auth.py` (headless, no browser window — uses the persistent `browser_profile/` to rotate tokens automatically)
  3. Try a lightweight `client.notebooks.list()` call to confirm auth works
  4. If all fails → `NLM_AVAILABLE = False`; pipeline degrades gracefully to Gemini/Cartesia
- `ensure_notebook(topic, domain)` — create/reuse notebook per run
- `generate_slides(notebook_id, concept, segment_id)` — slide PNG with timeout
- `generate_audio(notebook_id, output_path)` — deep-dive MP3 with timeout
- `generate_quiz(notebook_id)` — quiz Q&A list with timeout
- All methods: `try/except → log error → return None` (never raise to caller)
- All methods: hard `asyncio.wait_for(..., timeout=N)` — never block the pipeline

**Key design principle:**
```python
# Every NLM call follows this pattern:
try:
    result = await asyncio.wait_for(
        _do_nlm_operation(...),
        timeout=NLM_SLIDE_TIMEOUT_S  # 480s default
    )
    return result
except (asyncio.TimeoutError, Exception) as e:
    logger.warning(f"NLM unavailable ({type(e).__name__}): {e}. Using fallback.")
    return None  # caller checks for None and uses fallback
```

### [MODIFY] `requirements.txt`
```diff
+notebooklm-py[browser]>=0.3.0
+playwright>=1.40.0
```

### [MODIFY] `Dockerfile`
```dockerfile
# After pip install -r requirements.txt:
RUN playwright install chromium --with-deps
# Pre-download so there's no network call at contest runtime
```

### [MODIFY] `docker-compose.yml`
```yaml
services:
  teaching-monster-app:
    volumes:
      # Mount full NLM profile directory — MUST be read-write so refresh_auth.py
      # can silently update cookies without any human interaction.
      # The browser_profile/ subdirectory is what keeps Google sessions alive long-term.
      - "${USERPROFILE}/.notebooklm:/root/.notebooklm:rw"
    environment:
      - NLM_ENABLED=${NLM_ENABLED:-true}
      - NLM_SLIDE_TIMEOUT_S=${NLM_SLIDE_TIMEOUT_S:-480}
      - NLM_AUDIO_TIMEOUT_S=${NLM_AUDIO_TIMEOUT_S:-600}
      - NLM_QUIZ_TIMEOUT_S=${NLM_QUIZ_TIMEOUT_S:-300}
      - PYTHONUTF8=1  # Required for Windows NLM output encoding
```

### [MODIFY] `.env`
```env
NLM_ENABLED=true
NLM_SLIDE_TIMEOUT_S=480
NLM_AUDIO_TIMEOUT_S=600
NLM_QUIZ_TIMEOUT_S=300
```

### [MODIFY] `modules/m1_sourcing.py`
- After RAG sourcing succeeds: call `nlm_studio.ensure_notebook(topic, domain)`
- Store `notebook_id` in the sourcing result for downstream modules
- If NLM fails → `notebook_id = None`; all downstream NLM steps skip gracefully

### [MODIFY] `modules/m6_multimodal.py`
- Add `nlm_slide` as top-priority visual type in visual selector logic
- If `notebook_id` is None → skip NLM, go straight to Gemini infographic
- If NLM slide times out → log warning, use Gemini infographic (no crash)

### [MODIFY] `modules/m7_renderer.py`
- Add NLM audio path **above** Cartesia TTS in narration selection
- If `NLM_AUDIO_ENABLED` and `notebook_id` exists:
  - Call `nlm_studio.generate_audio()` with `NLM_AUDIO_TIMEOUT_S` timeout
  - On success: use NLM MP3 as narration base, split by segment ratios
  - On failure/timeout: fall through to Cartesia TTS (no changes to existing path)

### [MODIFY] `modules/m5_critic.py`
- After CIDPP selection, if `notebook_id` exists:
  - Call `nlm_studio.generate_quiz()` (advisory, max 300s timeout)
  - Log quiz pass rate to M8 run record
  - If pass rate < 70%: append coverage warning to revision instructions
  - Never blocks script selection; quiz check runs in background

### [MODIFY] `main.py`
- At startup: call `await nlm_studio.preflight_check()`
- Log NLM availability status
- Pass `nlm_available` flag through pipeline context

---

## Time Budget (Autonomous Mode, Worst Case)

| Step | Time (NLM active) | Time (NLM failed → fallback) |
|---|---|---|
| M1 RAG + NLM notebook | ~5s | ~2s |
| M2–M4 Script Gen | ~3–4 min | ~3–4 min |
| M5 CIDPP + NLM Quiz (parallel) | ~3–4 min | ~2–3 min |
| M6 NLM Slides (all segments, concurrent) | ~5–8 min | ~2–3 min (Gemini infographic) |
| M7 NLM Audio | ~5–8 min | ~3–5 min (Cartesia TTS) |
| M7 Video Assembly | ~5–10 min | ~5–10 min |
| **Total worst case** | **~25–28 min** | **~15–20 min** |

> [!WARNING]
> NLM slides and audio **may run concurrently** where possible to stay within the 30-min limit.
> NLM audio generation should start at M1 (notebook ready) and complete by the time M7 starts.
> NLM slides should be generated in parallel with M4/M5 (after notebook is created).

---

## Startup Checklist (Pre-Contest, Dev Machine Only)

Run these **before** the contest window opens. Takes ~5 minutes.

```powershell
# 1. Confirm cookies exist and are fresh
python scripts/nlm.py auth-status

# 2. If expired (> 7 days old), refresh:
python scripts/refresh_auth.py
# If that fails:
python scripts/nlm.py login   # interactive, open browser

# 3. Smoke test end-to-end (outside Docker):
python scripts/nlm.py create "Pre-contest Smoke Test"
python scripts/nlm.py list

# 4. Start Docker with volume mount (cookies shared with container):
docker compose up -d

# 5. Smoke test inside Docker:
docker exec teaching-monster-app python scripts/nlm.py auth-status
docker exec teaching-monster-app python scripts/nlm.py list
```

If Step 5 passes → NLM is ready. If it fails → set `NLM_ENABLED=false` in `.env` and the pipeline runs entirely on Gemini + Cartesia (v0.6.0 behavior, proven to work).

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| NLM cookies expire mid-contest | Low (valid 7–30 days) | High | Refresh day before; fallback chain always produces output |
| NLM slide generation > 8 min | Medium | Medium | Hard timeout → Gemini infographic fallback |
| NLM audio > 10 min | Low | High | Hard timeout → Cartesia TTS fallback; narration quality slightly lower |
| NLM API rate limit (free tier) | Medium | Medium | One notebook per run; 9 Gemini keys spread load via KeyRotator |
| Docker volume mount fails on Windows | Low | High | Test volume mount in pre-contest checklist; hard-code fallback path |
| `notebooklm-py` library breaking change | Low | High | Pin to specific release tag in `requirements.txt` |

---

## What Does NOT Change

- `modules/m1_sourcing.py` RAG logic (ChromaDB) — untouched
- `modules/m7_renderer.py` FFmpeg assembly path — untouched
- Cartesia TTS integration — untouched, remains as fallback
- Pexels B-roll integration — untouched, remains as fallback
- Contest submission endpoint — untouched
- The 30-minute hard deadline enforcement in `main.py` — untouched

---

*Teaching Monster AI — v0.7.0 Implementation Plan (Autonomous Edition)*
*Status: AWAITING USER APPROVAL before execution*
*April 2026*
