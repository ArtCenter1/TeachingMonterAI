# Teaching Monster AI Onboarding & Development Guide

Welcome to the **Teaching Monster AI Agent** project. This document is designed to help new AI agents and developers understand the architecture, the 8-module pipeline, and how to rapidly debug errors during development.

## 1. Project Mission
The goal is to build an autonomous pedagogical video generation system for the **Teaching Monster Challenge**. It takes a topic and a student persona and delivers a high-quality educational video without human intervention.

## 2. System Architecture (The M1-M8 Pipeline)

The system is organized into 8 distinct modules, orchestrated by `main.py`.

| Module | Name | Responsibility | File Path |
| :--- | :--- | :--- | :--- |
| **M1** | Sourcing | Extract grounded facts from NotebookLM/Web. | `modules/m1_sourcing.py` |
| **M2** | Persona Parser | Create a structured Model of the Learner. | `modules/m2_persona.py` |
| **M3** | Concept Planner | Sequence the lesson into a dependency graph. | `modules/m3_planner.py` |
| **M4** | Script Generator | Write the pedagogical narration (3 variants). | `modules/m4_generator.py` |
| **M5** | Critic | Score and select the best script variant. | `modules/m5_critic.py` |
| **M6** | MM Planner | Map script segments to visual representations. | `modules/m6_multimodal.py` |
| **M7** | Renderer | Assemble TTS and visuals into the final video. | `modules/m7_renderer.py` |
| **M8** | Logger | Record successful runs and persistent errors. | `modules/m8_logger.py` |

## 3. The Debugging Toolkit (Fixing "Nagging Errors")

If you see an **ERROR** on the competition dashboard or during a test run, follow this priority list to diagnose it instantly:

### Priority 1: `m8_errors.json` (Structured Failure Log)
This file is your best friend. Every pipeline crash is logged here with:
- **`failed_stage`**: Tells you exactly which module (e.g., `m5_critic`) blew up.
- **`error_type`**: The Python exception class.
- **`traceback`**: The full stack trace for deep diagnosis.
- **`request`**: The original `GenerationRequest` data needed to reproduce the bug.

> [!TIP]
> **Always check `m8_errors.json` first.** It filters out the noise and zooms in on why the pipeline failed.

### Priority 2: `pipeline.log` (Granular Execution)
If the error is silent or related to performance/latency, check `pipeline.log`. It contains detailed info logs about every step taken by the modules.

### Priority 3: `m8_feedback.json` (Pedagogical Performance)
Check this if the video generated successfully but the **Scores** are low. It contains the CIDPP rubric scores and the critic's revision notes.

## 4. Development Workflow

1.  **Add/Modify Modules**: Most work happens in `modules/`. Keep them independent.
2.  **Update Orchestration**: If you add a new sub-stage, update the `current_stage` variable in `main.py` so that errors are correctly categorized in `m8_errors.json`.
3.  **Local Testing**:
    ```powershell
    .venv\Scripts\python.exe main.py
    ```
    Then use `test_generate.py` or a tool like Postman to hit `POST /generate`.

## 5. Key Dependencies
- **FastAPI**: The API layer.
- **Loguru**: Enhanced logging.
- **OpenRouter/Google Generative AI**: LLM backend.
- **FFmpeg**: Required on the system for video rendering.

---
## 6. Maintenance & Workspace Cleanup

The pipeline generates several gigabytes of temporary data (Docker images, PCM audio, and frame sequences). To maintain a fast development cycle, run the following cleanup commands regularly:

### A. Purge Stale Docker Images
Each new version tag (e.g., `0.1.4`) creates a large image (~1.5GB). Delete unused tags to free disk space:
```powershell
# List images to find old tags
docker images "teachingmonsterai-app"
# Delete specific old tags
docker rmi teachingmonsterai-app:0.1.0 teachingmonsterai-app:0.1.1
```

### B. Clear Temporary Pipeline Artifacts
Rendered PNG frames and raw audio in `temp/` persist after failure. Clear them manually or via the cleanup script:
```powershell
# PowerShell: Delete frames, audio, and raw data
Remove-Item -Path temp -Include *.png,*.raw,*.wav,*.mp3 -Recurse -Force
```

### C. Persistent Error Reset
If `m8_errors.json` becomes too large or contains irrelevant historical data, you can reset it by simply deleting the file:
```powershell
Remove-Item m8_errors.json
```

---
## 7. Repository Structure & Global Services

To keep the `TeachingMonsterAI` repository clean and focused solely on the generation pipeline, the following structural rules are strictly enforced:

### A. OpenSpace Integration is Global
This project leverages a **global** OpenSpace server (located at `D:\My_Projects\openspace\`) for development skills and autonomous evolution.
- **MCP Only**: The local project only contains the MCP client configuration in `.env`.
- **No Local Server**: Do **not** define an `openspace-server` service in the local `docker-compose.yml`. The server runs directly on the host machine.
- **Networking**: The `app` container connects to the global server via `http://host.docker.internal:8081/mcp`. Ensure the global server is running before attempting to use OpenSpace skills.

### B. Local Testing & Debug Scripts
Do not commit ad-hoc test scripts to the remote repository. 
- All temporary Python scripts used for testing triggers, listing models, and quick API requests must be kept in the **`temp/local_tests/`** directory.
- This directory, along with major local logs (`pipeline.log`, `docker_debug.log`, `m8_errors.json`, `m8_feedback.json`), is excluded via `.gitignore` or safely untracked to prevent cluttering the Git history.
- Existing debug scripts include `test_generate.py`, `test_m8.py`, and `trigger_gen.py`. Look for them in `temp/local_tests/` before creating a new script.

---
*Created by Antigravity AI Agent — April 2026*

---

## Dev Key Pool — Adding Your API Key

The project uses a **rotating key pool** during development so the team never hits a single key's quota. Each developer adds their own key to the pool.

### Step 1 — Get your keys
- **Gemini:** https://aistudio.google.com/app/apikey → Create a free key
- **OpenRouter:** https://openrouter.ai/settings/keys → Create a free key

### Step 2 — Add to `.env`
Open `.env` and replace one of the `FILL_KEY_N` placeholders with your key:

```dotenv
GOOGLE_API_KEY_POOL=AIzaSyYOURKEY,AIzaSyTEAMMATEKEY,...
OPENROUTER_API_KEY_POOL=sk-or-YOURKEY,sk-or-TEAMMATEKEY,...
```

### Step 3 — Restart the container
```bash
docker compose up -d app
```

### Step 4 — Monitor pool health
Open the dashboard: http://localhost:8000/dev/pool-status/ui

- 🟢 HEALTHY — key is working
- 🟠 RATE LIMITED — hit per-minute limit, auto-recovers in 60s
- 🔴 SPENT — hit daily spend cap, owner must raise billing limit then click **[Revive]**

> **Never commit `.env` to git.** It's already in `.gitignore`. Share keys privately with your team lead.

---
## 8. NotebookLM Integration (M1 Sourcing)

This section is the **permanent reference** for NotebookLM in this project. Read it once, follow the steps, and never revisit from scratch.

### What NotebookLM Does in This Pipeline
Module M1 (`modules/m1_sourcing.py`) queries **Google NotebookLM** to retrieve grounded, citable educational facts for a given topic. It is **Stage 1** in the sourcing chain:

```
NotebookLM  →  (fallback) Google Custom Search  →  (fallback) Gemini AI Research
```

The library used is [`notebooklm-py`](https://github.com/teng-lin/notebooklm-py) — an unofficial but stable Python API (v0.3.4+, 10k⭐).

### The Auth Model — Read This First
NotebookLM uses **Google OAuth browser cookies**, not an API key. The flow is:
1. You log in once via a real browser on your host machine.
2. The library saves your session cookies to `~/.notebooklm/profiles/default/storage_state.json`.
3. You paste that file's contents into `NOTEBOOKLM_AUTH_JSON` in `.env`.
4. The Docker container reads `NOTEBOOKLM_AUTH_JSON` automatically — **no browser needed inside Docker**.

> [!IMPORTANT]
> Sessions expire roughly every **2 weeks**. When M1 logs `"NotebookLM auth error"`, it's time to re-run Step 3 below and refresh the `.env` value.

---

### One-Time Host Setup (Windows PowerShell)

**Step 1 — Install the package WITH browser support (host only, for login):**
```powershell
pip install "notebooklm-py[browser]"
playwright install chromium
```
> If `playwright install chromium` fails with `TypeError: onExit is not a function`, update Node.js to v18+ first.

**Step 2 — Authenticate (opens a real browser window):**
```powershell
notebooklm login
```
Sign in with your Google account. Close the browser when prompted. Verify it worked:
```powershell
notebooklm list      # Should show "Authenticated as: your@gmail.com"
```

**Step 3 — Export the auth cookie and add it to `.env`:**
```powershell
# Get the auth JSON (will be a long JSON string)
$authJson = Get-Content "$env:USERPROFILE\.notebooklm\profiles\default\storage_state.json" -Raw

# Print it (copy the output manually, or use the command below to write to a temp file)
Write-Host $authJson
```
Copy that entire JSON string. Open `.env` and paste it as the value of `NOTEBOOKLM_AUTH_JSON`:
```dotenv
NOTEBOOKLM_AUTH_JSON={"cookies":[{"name":"SID","value":"..."},...]}
```
> **Important:** The JSON must be on a **single line** in `.env` (no newlines inside the value).

**Step 4 — Rebuild the container so it picks up the new env:**
```powershell
docker compose up -d --build app
```

**Step 5 — Verify M1 is using NotebookLM:**
```powershell
# Trigger the pipeline and watch the log
docker compose logs -f app | Select-String "NotebookLM"
```
You should see:
```
INFO | NotebookLM native library detected
INFO | Querying NotebookLM for facts on: <topic>
INFO | NotebookLM sourcing successful
```

---

### Runtime Architecture (No Browser in Docker)

Inside the Docker container, `notebooklm-py` is installed **without** browser support:
```
requirements.txt → notebooklm-py   (no [browser] extra)
```
This is intentional — `playwright` is heavyweight and not needed at runtime. Only `notebooklm login` needs the browser, and that runs on the host, not in Docker.

The auth flow at runtime:
```
Docker container starts
  ↓
m1_sourcing.py → NotebookLMClient.from_storage()
  ↓
Library reads NOTEBOOKLM_AUTH_JSON env var
  ↓
Authenticates via cached Google cookies (no browser)
  ↓
Calls NotebookLM API over HTTPS
```

---

### How M1 Uses the Library

The implementation in `modules/m1_sourcing.py → _notebooklm_library_source()` does:

1. **Finds or creates** a persistent `"TeachingMonster_Sourcing"` notebook in your Google NotebookLM account.
2. If the notebook is **new**, seeds it with a Wikipedia article about the topic (non-blocking, `wait=False`).
3. Calls `client.chat.ask(nb.id, query)` to get grounded educational facts.
4. Returns the answer as a `FactBundle` with `confidence=0.92` and citation `"Google NotebookLM"`.

The notebook is **reused** across runs — it accumulates sources over time and becomes a richer knowledge base.

---

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `"NotebookLM native library not found"` in logs | `notebooklm-py` not installed in container | Run `docker compose up -d --build app` |
| `"NotebookLM auth error"` in logs | Cookies expired or `NOTEBOOKLM_AUTH_JSON` empty | Re-run Steps 2–4 above |
| `"NotebookLM returned an empty answer"` | Notebook has no sources yet | First run seeds Wikipedia; wait 30s and retry |
| M1 falls through to web search | Any exception in NotebookLM path | Normal fallback; check `pipeline.log` for root cause |
| `playwright install` fails | Node.js < 18 | `winget install OpenJS.NodeJS.LTS` and retry |
| JSON parse error for `NOTEBOOKLM_AUTH_JSON` | Newlines in `.env` value | Ensure the JSON is on a single line with no line breaks |

### Session Renewal Checklist (every ~2 weeks)
- [ ] Run `notebooklm login` on host
- [ ] Run `notebooklm list` to verify
- [ ] Copy new `storage_state.json` contents into `.env → NOTEBOOKLM_AUTH_JSON`
- [ ] Run `docker compose up -d app` (no rebuild needed, just env reload)
- [ ] Check `docker compose logs app | Select-String "NotebookLM"` shows success

---
*Section 8 added by Antigravity AI Agent — April 2026*

