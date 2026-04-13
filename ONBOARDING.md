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
