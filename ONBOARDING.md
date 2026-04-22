# Teaching Monster AI — v2.0 Onboarding & Development Guide (RAG Edition)

Welcome to the **Teaching Monster AI Agent** project. This document is designed for AI agents and developers to understand the high-performance, local-first RAG architecture of v2.0.

## 1. Project Mission
The goal is to build an autonomous pedagogical video generation system that is **domain-agnostic** and **zero-hallucination**. It takes a topic and a student persona, queries a local knowledge base, and delivers a visually rich educational video in under 30 minutes.

## 2. System Architecture (The M1-M8 Pipeline)

The system is organized into 8 modules, coordinated by `main.py`.

| Module | Name | Responsibility | Current Implementation |
| :--- | :--- | :--- | :--- |
| **M1** | Sourcing | Fact retrieval | **Local RAG (ChromaDB)** → AI Research Fallback |
| **M2** | Persona Parser | Learner modeling | Infer ZPD, language level, and learning style |
| **M3** | Planner | Lesson logic | Build prerequisite dependency graph |
| **M4** | Generator | Narrative writing | 3 script variants in parallel (Gemini 2.0) |
| **M5** | Critic | Best-of-N selection | CIDPP scoring rubric + Synthetic Student Test |
| **M6** | Multimodal | Asset planning | Pexels video search keyword generation |
| **M7** | Renderer | Final composition | **MoviePy** + B-roll + TTS + Karaoke Subs + BGM |
| **M8** | Logger | Observability | Persistent run data + win-rate strategy tracking |

## 3. The RAG Infrastructure

In v2.0, the system is **local-first**. All factual grounding comes from a persistent ChromaDB store.

### Configuration (`config/domains.yaml`)
Determines which subjects the agent knows. Each domain has a list of topics.

### Ingestion (`scripts/ingest_rag.py`)
- Reads curriculum files from `resources/curriculum/`.
- If a topic is missing, it auto-generates a high-quality pedagogical summary via LLM.
- Chunks and embeds content into **ChromaDB** using `all-MiniLM-L6-v2`.

### Retrieval (`modules/rag_retriever.py`)
Provides sub-second, semantic retrieval of facts. This replaces the brittle NotebookLM API from v1.0.

## 4. Development Workflow

1.  **Configure Domains**: Run `python scripts/setup_domains.py` to set up your subjects.
2.  **Build Docker**: `docker compose up -d --build`. The build process includes build-time ingestion.
3.  **Monitor Logs**: Always check `pipeline.log` and `m8_errors.json`.

## 5. Visual Rendering (The "Wow" Factor)

M7 uses **MoviePy** for professional composition:
- **B-roll**: Automatically downloaded from Pexels based on M6 keywords.
- **Fallbacks**: If no video is found, uses generated slides with a Ken Burns zoom effect.
- **Vertical Format**: Renders in 9:16 (1080x1920) for modern mobile/competition displays.
- **Audio Mixing**: Overlays Cartesia TTS with auto-looped BGM from `resources/bgm/`.

## 6. Maintenance & Workspace Cleanup

### Clear Temporary Data
The pipeline generates temporary audio, video, and frames.
```powershell
# PowerShell
Remove-Item -Path temp -Include *.mp4,*.wav,*.png,*.raw -Recurse -Force
```

### Reset Knowledge Base
To force a full re-ingestion:
```powershell
Remove-Item -Path temp/chroma_db -Recurse -Force
```

---
*Updated for v2.0 RAG Branch — April 2026*
