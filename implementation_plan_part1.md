# Agent Execution Plan — Part 1: Infrastructure Setup
## Teaching Monster v0.7.0 NLM Studio Integration

### CONTEXT: What we know from reading the codebase

- `requirements.txt` already has `notebooklm-py` (no `[browser]` extra, no `playwright`)
- `Dockerfile`: no Playwright install, no Chromium
- `docker-compose.yml`: service name is `app` (not `teaching-monster-app`), image tag `teachingmonsterai-app:0.6.0`
- `.env`: has `NOTEBOOKLM_AUTH_JSON` with full cookie JSON already present — this is the existing auth mechanism
- `modules/notebooklm_manager.py`: uses `NotebookLMClient.from_storage()` — reads `~/.notebooklm/storage_state.json`
- `modules/m1_sourcing.py`: already calls `notebooklm_manager` at Stage 0, stores `notebook_id` in `fact_bundle.metadata`
- `modules/m7_renderer.py`: already has `has_total_audio` path that muxes a single `script.total_audio_path` MP3
- `modules/m6_multimodal.py`: routes `gemini_infographic` (primary) → `pexels_broll` (fallback)

### WHAT ALREADY WORKS (do not break)
- NLM notebook creation + source injection (m1_sourcing.py Stage 0)
- NLM audio path in m7_renderer.py (`has_total_audio` branch)
- Gemini infographic → Pexels B-roll visual routing

### WHAT IS MISSING (what the agent must implement)
1. `notebooklm-py[browser]` + `playwright` not installed → Chromium auth refresh broken
2. No `scripts/nlm.py` CLI wrapper (robonuggets pattern)
3. No `scripts/refresh_auth.py` (headless cookie refresh)
4. No `modules/nlm_studio.py` (autonomous wrapper with preflight + timeouts)
5. No NLM slide generation integrated into M6
6. No NLM audio generation called from M1/M7 (the `total_audio_path` hook exists but nothing fills it)
7. No NLM quiz check in M5
8. No env vars: `NLM_SLIDES_ENABLED`, `NLM_AUDIO_ENABLED`, `NLM_SLIDE_TIMEOUT_S`, `NLM_AUDIO_TIMEOUT_S`
9. Docker volume not mounting `~/.notebooklm` for cookie persistence

---

## TASK 1: Update `requirements.txt`

**File:** `D:\My_Projects\TeachingMonsterAI\requirements.txt`

Replace line:
```
notebooklm-py
```
With:
```
notebooklm-py[browser]>=0.3.0
playwright>=1.40.0
```

---

## TASK 2: Update `Dockerfile`

**File:** `D:\My_Projects\TeachingMonsterAI\Dockerfile`

After the line:
```
RUN pip install --no-cache-dir -r requirements.txt
```

Add these two lines:
```dockerfile
# Install Playwright Chromium for NLM headless auth refresh (no manual login needed at runtime)
RUN playwright install chromium --with-deps
```

---

## TASK 3: Update `docker-compose.yml`

**File:** `D:\My_Projects\TeachingMonsterAI\docker-compose.yml`

In the `app:` service, under the existing `volumes:` block, add this line after the last existing volume entry:
```yaml
      - "${USERPROFILE}/.notebooklm:/root/.notebooklm:rw"
```

In the `app:` service, under the existing `environment:` block, add after the last existing environment entry:
```yaml
      - NLM_SLIDES_ENABLED=${NLM_SLIDES_ENABLED:-true}
      - NLM_AUDIO_ENABLED=${NLM_AUDIO_ENABLED:-true}
      - NLM_SLIDE_TIMEOUT_S=${NLM_SLIDE_TIMEOUT_S:-480}
      - NLM_AUDIO_TIMEOUT_S=${NLM_AUDIO_TIMEOUT_S:-600}
      - NLM_QUIZ_TIMEOUT_S=${NLM_QUIZ_TIMEOUT_S:-300}
      - PYTHONUTF8=1
```

Update image tag from `teachingmonsterai-app:0.6.0` to `teachingmonsterai-app:0.7.0`

---

## TASK 4: Update `.env`

**File:** `D:\My_Projects\TeachingMonsterAI\.env`

Add after the `INFOGRAPHIC_ENABLED` block:
```env
# ── NLM Studio Integration (v0.7.0) ─────────────────────────────────────────
# Set false to disable NLM and fall back to Gemini infographic + Cartesia TTS
NLM_SLIDES_ENABLED=true
NLM_AUDIO_ENABLED=true
NLM_SLIDE_TIMEOUT_S=480
NLM_AUDIO_TIMEOUT_S=600
NLM_QUIZ_TIMEOUT_S=300
```

---

## TASK 5: Create `scripts/nlm.py`

**File:** `D:\My_Projects\TeachingMonsterAI\scripts\nlm.py`

Copy EXACTLY from: https://raw.githubusercontent.com/robonuggets/notebooklm-skill/master/scripts/nlm.py

This file provides CLI: `login`, `auth-status`, `list`, `create`, `add-source`, `ask`, `generate-audio`, `generate-report`, `generate-quiz`, `artifacts`, `library-*`

---

## TASK 6: Create `scripts/refresh_auth.py`

**File:** `D:\My_Projects\TeachingMonsterAI\scripts\refresh_auth.py`

Copy EXACTLY from: https://raw.githubusercontent.com/robonuggets/notebooklm-skill/master/scripts/refresh_auth.py

This script silently refreshes NLM cookies using the persistent browser profile at `~/.notebooklm/browser_profile/`. No browser window, no human input required.
