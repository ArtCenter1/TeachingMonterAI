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
*Created by Antigravity AI Agent — April 2026*
