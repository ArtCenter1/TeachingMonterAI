# 🎮 Teaching Monster AI Agent (v0.2.3)

> [!IMPORTANT]
> **🤖 FOR AI AGENTS / ASSISTANTS**
> Before taking any action, you MUST read **[ONBOARDING.md](file:///d:/My_Projects/TeachingMonsterAI/ONBOARDING.md)**. Use the `project_onboarding_check` skill to align with our pedagogical mission and 8-stage pipeline architecture.

---


[![Status](https://img.shields.io/badge/Status-Stabilized-success.svg)](https://teaching.monster)
[![Version](https://img.shields.io/badge/Version-0.2.0-blue.svg)](https://github.com/artcenter/TeachingMonsterAI)
[![Docker](https://img.shields.io/badge/Docker-Ready-0db7ed.svg)](https://www.docker.com/)

An autonomous pedagogical video generation system built for the **Teaching Monster Challenge**. This agent receives a topic and a student persona, then delivers a high-quality, grounded educational video in under 30 minutes with zero human intervention.

---

## 🌟 Key Features

- **Autonomous M1-M8 Pipeline**: From sourcing facts via NotebookLM to final FFmpeg rendering.
- **Pedagogical Intelligence**: Implements scaffolding strategies, misconception detection, and cognitive load optimization.
- **Gemini 2.0 Flash Integration**: High-speed, high-context reasoning for script generation and multimodal planning.
- **Neural TTS**: High-fidelity narration via Cartesia.
- **Docker-First Architecture**: Guaranteed reproducibility across any environment.

---

## 🏗️ System Architecture

The agent operates as a fully automated eight-stage pipeline, orchestrated by `main.py`.

```mermaid
graph TD
    API[POST /generate] --> M1[M1: Sourcing - NotebookLM]
    M1 --> M2[M2: Persona Parser]
    M2 --> M3[M3: Concept Planner]
    M3 --> M4[M4: Script Generator]
    M4 --> M5[M5: CIDPP Critic]
    M5 --> M6[M6: Multimodal Planner]
    M6 --> M7[M7: Video Renderer]
    M7 --> M8[M8: Feedback Logger]
    M8 --> URL[Output Video URL]
```

| Module | Name | Responsibility |
| :--- | :--- | :--- |
| **M1** | **Sourcing** | Extract grounded facts from NotebookLM & Web Search. |
| **M2** | **Persona Parser** | Infer learner state and ZPD (Zone of Proximal Development). |
| **M3** | **Concept Planner** | Sequence concepts into an optimal lesson arc. |
| **M4** | **Scriptwriter** | Generate pedagogical narration with visual cues. |
| **M5** | **Critic** | Score scripts on Accuracy, Logic, and Engagement. |
| **M6** | **MM Planner** | Map script segments to optimal visual representations. |
| **M7** | **Renderer** | Assemble TTS + visuals via FFmpeg into the final MP4. |
| **M8** | **Logger** | Record persistent errors and training signals. |
| **DASH** | **Mission Control** | Real-time observability and key quota management. |

---

## 🔍 Observability & Inspection

The system includes dedicated tools for monitoring pipeline health and API utilization in real-time.

### 🗝️ KeyRotator Dashboard (Mission Control)
### 📊 KeyRotator Dashboard
Real-time pool health, rate-limit tracking, and pipeline activity logging.

- **Access**: [http://localhost:8000/dev/pool-status/ui](http://localhost:8000/dev/pool-status/ui)
- **Features**:
    - **Live Public URL**: Automatically detects the current ngrok endpoint.
    - **Activity Log**: Tracks successes, 429 rate limits, and pool exhaustion events.
    - **Pulse Test**: Trigger a "heartbeat" to verify end-to-end connectivity.

![KeyRotator Dashboard Demo](docs/images/dashboard_demo.webp)

### 📚 API Documentation (Swagger)
Interactive API playground with automatic schema validation.

- **Access**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Usage**: Test the `POST /generate` endpoint with custom requirements.

![API Docs UI](docs/images/api_docs_ui.png)



---

## 🚀 Quick Start (Docker)

The fastest way to get the agent running is via Docker Compose.

### 1. Prerequisites
- Docker & Docker Compose installed.
- API Keys for: Google Gemini, Cartesia, and (optional) ngrok.

### 2. Configure Environment
Copy `.env.example` to `.env` (or update existing) and fill in your keys:
```bash
GOOGLE_API_KEY=your_key
CARTESIA_API_KEY=your_key
NGROK_AUTHTOKEN=your_token (optional for public tunnel)
```

### 3. Start the Pipeline
```bash
docker compose up -d --build
```
The API will be available at `http://localhost:8000`.

### 4. Trigger a Generation
```bash
curl -X POST http://localhost:8000/generate \
     -H "Content-Type: application/json" \
     -d '{"course_requirement": "Quantum Tunneling", "student_persona": "12-year old curios learner"}'
```

---

## 🛠️ Maintenance & Cleanup

The pipeline generates temporary image sequences and large Docker images. To keep your workspace clean:

- **Clean Temporary Files**: `Remove-Item -Path temp -Include *.png,*.raw -Recurse -Force`
- **Prune Old Images**: `docker image prune` (or follow instructions in [ONBOARDING.md](file:///d:/My_Projects/TeachingMonsterAI/ONBOARDING.md#6-maintenance--workspace-cleanup)).

---

## 📚 Documentation
- [**ONBOARDING.md**](file:///d:/My_Projects/TeachingMonsterAI/ONBOARDING.md): Detailed technical guide for developers.
- [**README-docker.md**](file:///d:/My_Projects/TeachingMonsterAI/README-docker.md): Granular Docker and ngrok networking setup.
- [**PHASE_4_PLAN.md**](file:///d:/My_Projects/TeachingMonsterAI/PHASE_4_PLAN.md): Roadmap for future pedagogical improvements.
- [**Mission Control**](http://localhost:8000/dev/pool-status/ui): Live Dashboard.
- [**API Docs**](http://localhost:8000/docs): Interactive API Documentation.

---
*Developed by Antigravity AI Agent for the Teaching Monster Challenge — April 2026*
