# Teaching Monster AI Agent — PRD v2.0  CONFIDENTIAL

## PRODUCT REQUIREMENTS DOCUMENT

### Teaching Monster AI Agent
### Autonomous Pedagogical Video Generation System

| Field | Value |
|---|---|
| Version | 2.2 — NLM Studio Integration |
| Previous Version | 2.1 — Visual Pipeline & Hybrid RAG |
| Status | Pre-Execution Planning (v0.7.0) |
| Date | April 2026 |
| Competition | Teaching Monster Challenge — teaching.monster |
| Team Size | 3–6 engineers |
| Deadline | 30-min end-to-end video generation |

> **CONFIDENTIAL — INTERNAL USE ONLY**

---

## Changelog from v1.0

| Section | Change | Reason |
|---|---|---|
| M1 — Sourcing | **Hybrid RAG & NotebookLM** | Restored NotebookLM as a premium high-fidelity path alongside Local RAG (ChromaDB) for maximum reliability and quality. |
| M6 — Multimodal Planner | Added **Subject-Aware Aesthetics** | Biological subjects now trigger the 'Nature' style (parchment/botanical) to improve visual accuracy vs. dark blueprint. |
| M7 — Video Renderer | **Full rewrite** using **moviepy v2 + Pexels B-roll + karaoke subtitles + BGM** | Visual pipeline verified and stable in v0.6.0. |
| Roadmap | Phases 1–4 updated to reflect v0.6.0 stabilization and completion of foundation phases. | |
| **v2.2 — M6 NLM Slide Deck** | **NLM-generated slides replace Pexels B-roll as primary visual source** | Pexels clips are contextually inaccurate; NLM slides are sourced from curriculum content. |
| **v2.2 — M7 NLM Audio Path** | **NLM Audio Overview (Deep Dive) replaces Cartesia TTS as primary narration path** | NLM produces natural two-voice pedagogical dialogue; significantly higher quality than single-voice TTS. |
| **v2.2 — M5 NLM Quiz** | **NLM Quiz/Study Guide as supplementary synthetic student test** | Replaces pure LLM-prompted personas with quiz grounded in actual curriculum sources. |

---

## 1. Product Overview

### 1.1 Purpose

This document specifies the full engineering requirements for the Teaching Monster AI Agent — an autonomous system that receives a JSON API request containing a course topic and student persona, and returns a complete educational video URL within 30 minutes, with zero human intervention.

The agent is designed to compete in and win the Teaching Monster Challenge (teaching.monster), evaluating AI-generated teaching videos for secondary education subjects across **physics, biology, computer science, and mathematics**.

### 1.2 The Core Differentiator

Most competing teams will build video generators. The winning team builds a system that learns what better teaching means.

**Key insight:** Video quality is table stakes. The differentiator is **Pedagogical Content Knowledge (PCK)** — the ability to understand how humans learn, not just what is factually correct. The agent must reason about scaffolding, misconceptions, cognitive load, and adaptive explanation style.

**v2.0 additional differentiator:** The visual presentation layer is now a first-class competitive advantage. Human-judge Elo Arena (Phase 2) compares videos side-by-side. Dynamic B-roll video + styled karaoke subtitles + background music beats static slides in perceived production quality.

### 1.3 Competition Structure

| Phase | Objective | Evaluation Mechanism |
|---|---|---|
| Phase 1 — Warm-up | API integration & pipeline validation | Automated AI Student scoring on 4 criteria |
| Phase 2 — Preliminary | Human Arena head-to-head | Elo ranking by real student pairwise preference |
| Phase 3 — Grand Final | High-difficulty 30-min sprints | Expert review by professors and teachers |
| Phase 4 — Workshop | Architecture sharing | Official rankings and award presentation |

### 1.4 Judging Criteria (All Phases)

| Criterion | Definition | Agent Capability Required |
|---|---|---|
| Accuracy | Zero hallucinations; every fact verifiable | RAG-grounded facts from pre-seeded AP/IB curriculum corpus |
| Logic & Flow | Scaffolding from simple → complex; smooth narrative bridges | Concept dependency graph; prerequisite sequencing |
| Adaptability | True personalisation to student persona | Persona parser; ZPD-driven lesson arc |
| Engagement | Vivid storytelling, Socratic questions, synced multimodal elements | B-roll video, styled subtitles, BGM, curiosity hooks |

---

## 2. System Architecture

### 2.1 High-Level Pipeline

The agent operates as a fully automated multi-stage pipeline. No human is in the loop at any point between API request and video URL delivery.

```
API Input
  → M1 [RAG Sourcing: ChromaDB → AI Research → Web Search fallback]
  → M2 [Persona Parser]
  → M3 [Concept Planner]
  → M4 [Script Generator (Best-of-3)]
  → M5 [CIDPP Critic + Revision Loop]
  → M6 [Multimodal Planner + Pexels Keyword Generation]
  → M7 [Video Renderer: Pexels B-roll + Cartesia TTS + Subtitles + BGM]
  → M8 [Feedback Logger]
  → Output URL
```

### 2.2 API Contract

**Request:**
```json
POST /generate
{
  "course_requirement": "Self-Attention Mechanism",
  "student_persona": "High schooler, no calculus"
}
```

**Response:**
```json
{
  "video_url": "https://...",
  "supplementary_url": "https://...",
  "generation_time_seconds": 1247
}
```

**Hard Constraints:**
- Total generation time: ≤ 1800 seconds (30 minutes)
- Zero human intervention between request and response
- Video language: English
- Video length: ≤ 30 minutes
- Must be fully reproducible in Docker

### 2.3 Module Map

| Module | Primary Responsibility | Key Output | v0.7.0 NLM Upgrade |
|---|---|---|---|
| **M1** — RAG Sourcing | Query local ChromaDB → AI Research → Web Search | Cited content bundle (JSON) | NLM notebook created; sources injected from curriculum |
| **M2** — Persona Parser | Infer learner state from `student_persona` string | Student model object | Unchanged |
| **M3** — Concept Planner | Build prerequisite dependency graph, sequence lesson arc | Ordered concept graph (JSON) | NLM Study Guide used to seed concept graph |
| **M4** — Script Generator | Write pedagogical narration (3 variants) | Annotated script (Markdown) | Unchanged |
| **M5** — CIDPP Critic | Score and select the best script variant | Rubric scores + revision instructions | NLM Quiz validates script coverage |
| **M6** — MM Planner | Map segments to visual type + NLM slide keywords | Visual plan (JSON) | **NLM Slide Deck is primary visual source (replaces Pexels B-roll)** |
| **M7** — Video Renderer | Assemble slides + NLM audio + subtitles + BGM | `video_url` string | **NLM Audio Overview is primary narration path (replaces Cartesia TTS)** |
| **M8** — Feedback Logger | Record all inputs, decisions, scores, and outcomes | Logged run record | Unchanged |

---

## 3. Five Capability Layers

*(Unchanged from v1.0 — these govern the pedagogical intelligence of M2–M5)*

### Layer 1 — Pedagogical Intelligence

**1a. Misconception Detection**
Before writing any script, the agent retrieves a domain-specific misconception library:
- Physics: force vs. momentum, weight vs. mass, current vs. voltage
- Biology: evolution is goal-directed, genes are switched on/off permanently
- CS: recursion = infinite loop, arrays are the only data structure
- Mathematics: correlation implies causation, division always makes smaller

**1b. Scaffolding Strategy Selection**
- Example → generalization (concrete learners, younger audiences)
- Intuition → formula → application (IB/AP students)
- Misconception → correction → reconstruction (topics with strong prior errors)
- Story → formalization (engagement-first personas)

**1c. Cognitive Load Optimization**

| Parameter | Target Range | Enforcement |
|---|---|---|
| Concept density | ≤ 2 new concepts per 3 minutes | Critic flags violations |
| Equation-to-analogy ratio | ≤ 1:2 for non-calculus personas | Persona parser sets ceiling |
| Average sentence length | ≤ 18 words for age < 16 | Script post-processor trims |
| Quiz/check frequency | 1 check per 4–5 minutes | Planner enforces checkpoints |

**1d. Explanation Style Adaptation**
Persona strings like `"High schooler, no calculus"` imply: comfort with algebra, unfamiliarity with limits/derivatives. The persona parser extracts these implied constraints.

### Layer 2 — Student Modeling

```json
{
  "level": "IB | AP | high_school | middle_school",
  "knowledge_embedding": [...],
  "misconception_risk": {...},
  "cognitive_load_budget": 0.0,
  "modality_preference": "visual | verbal | mixed",
  "abstraction_tolerance": 0.0
}
```

**Synthetic Student Testing:** 4 synthetic personas tested against the draft script before committing to video:
- Persona A: Confused visual learner
- Persona B: Math-anxious student
- Persona C: High-performing abstract thinker
- Persona D: Low prior knowledge, high curiosity

### Layer 3 — Teaching Strategy Learning Loop

- AI Student scores → structured critique per dimension
- Elo outcomes → win/loss per match, strategy tracking
- Meta-policy: wins by (strategy × level × subject), ε-greedy exploration (ε=0.15 → 0.05)
- Pedagogy memory bank: top-scoring lessons as few-shot examples in M4

### Layer 4 — Multimodal Instruction Generation (Updated v2.0)

**Visual Representation Selector** (policy table, unchanged):

| Concept Type | Optimal Representation | Trigger |
|---|---|---|
| Geometric / spatial | Animation (motion graphics) | shape, area, volume, rotation, vector |
| Symbolic mathematics | Step-by-step derivation overlay | Equation ratio > threshold |
| Algorithm / process | Flowchart animation | steps, loop, if, repeat, sequence |
| Physics phenomena | Simulation with labelled parameters | Physics subject + dynamic concept |
| Biology structure | Labeled diagram with callout highlights | Anatomy, cell, molecule, organism |
| **Natural/Biological** | **Nature Style (Parchment/Botanical)** | **Subject: Biology, Taxonomy, Ecology** |
| Abstract concept | Spatial metaphor animation | No physical referent |
| Analogy | Side-by-side split-screen | Script contains "think of it like..." |

**v2.0 Addition — Pexels B-roll Enrichment:**
Each visual plan entry now additionally includes `search_keywords: List[str]` — 2-3 Pexels search terms generated by the LLM to find contextually relevant stock video. The video renderer uses these to fetch dynamic B-roll that plays behind the narration.

**PCK Analogy Retrieval Store (unchanged):**
- Recursion (CS, beginner) → Russian nesting dolls; mirrors facing each other
- Conservation of momentum (Physics) → billiard balls; ice skater pulling arms in
- DNA transcription (Biology) → photocopying a blueprint
- Derivative (Maths, no calculus) → speedometer vs. odometer
- Self-attention (CS/ML, high school) → highlighting every word and asking which words help understand this one

### Layer 5 — Self-Improving Evaluation System

CIDPP Rubric (unchanged):

| Dimension | Definition | Minimum Threshold |
|---|---|---|
| Clarity | Logical flow, understandable language | 7/10 — rewrite flagged segments |
| Integrity | Factual accuracy, no hallucinations | 9/10 — re-verify sources |
| Depth | Nuanced explanations, addresses misconceptions | 7/10 — insert concept layer |
| Practicality | Concrete examples, worked problems | 7/10 — add examples |
| Pertinence | Alignment with student persona | 8/10 — persona re-alignment pass |

---

## 4. Hybrid RAG & NotebookLM Architecture

### 4.1 Motivation for Hybrid Approach

In v1.0, M1 used Google NotebookLM exclusively. While high-quality, session fragility led to a shift toward Local RAG in v2.0. We have now stabilized the pipeline to support a **Hybrid Architecture**:

1. **Local RAG (Reliability)**: ChromaDB-backed local storage for zero-dependency baseline sourcing.
2. **NotebookLM (Premium)**: Optional, high-fidelity path for generating advanced scripts and study guides when session state is valid.

### 4.2 Local RAG Stack

| Component | Technology | Notes |
|---|---|---|
| Vector store | ChromaDB (SQLite backend) | Persistent at `temp/chroma_db/`; committed to Docker image |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` | ~90MB; CPU-only; pre-downloaded at Docker build time |
| Corpus | AP/IB curriculum text (4 subjects) | Stored in `resources/curriculum/`; commited to repo |
| Chunking | 400-token overlapping windows | With subject + level metadata tags |
| Query latency | < 2 seconds | Offline; no network request |

### 4.3 Subject Corpus Coverage

| Subject | Primary Sources | Estimated Corpus Size |
|---|---|---|
| Physics | AP Physics 1/2/C CED, IB Physics guide, mechanics + E&M + waves | ~3,000 words per major topic |
| Biology | AP Biology CED, IB Biology, cell/genetics/evolution/ecology | ~3,000 words per major topic |
| Computer Science | IB CS guide, CS50 transcripts, algorithms + data structures + OOP | ~3,000 words per major topic |
| Mathematics | AP Calculus AB/BC, IB Math AA, statistics + algebra + calculus | ~3,000 words per major topic |

### 4.4 M1 Sourcing Chain (v2.0)

```
Stage 1: Local RAG query (ChromaDB) — target < 2s, offline
  ↓ (if insufficient results)
Stage 2: AI Research fallback (LLM with pedagogical expert prompt) — target < 30s
  ↓ (optional premium path)
Stage 4: NotebookLM Sourcing (for high-fidelity audio/guides) — target < 90s
  ↓ (if explicitly needed for citations)
Stage 3: Web Search fallback (Google Custom Search) — target < 60s
```

> **Key change from v1.0:** NotebookLM is no longer in the chain. The local RAG provides equivalent (or better) fact retrieval for the fixed subject domains without any external dependency.

### 4.5 Supplementary URL

The `supplementary_url` response field (originally generated by NotebookLM's study guide feature) will now be generated by the LLM as a structured HTML study guide and hosted on the same CDN as the video.

### 4.6 Integrity Guarantee

The CIDPP critic's Integrity dimension (minimum 9/10) remains the final safety net. Every factual claim in the script must be traceable to a source retrieved in M1 (RAG chunk ID, or AI research with explicit reasoning).

---

## 5. Module Specifications (v2.0)

### M1 — Local RAG Sourcing Module

| Property | Specification | Notes |
|---|---|---|
| Primary path | ChromaDB local query | No network; < 2s |
| Stage 2 fallback | AI Research (LLM pedagogical expert) | < 30s |
| Stage 3 fallback | Web Search (Google Custom Search) | < 60s |
| Timeout budget | 90 seconds maximum (same as v1.0) | |
| Output format | `{facts: [{claim, citation, confidence}]}` | Same schema as v1.0 |
| Minimum citations | ≥ 3 unique source citations per concept node | RAG chunk IDs count as citations |

### M2 — Persona Parser *(Unchanged)*

| Property | Specification |
|---|---|
| Input | `student_persona` string (free text) |
| Output | `student_model` JSON object |
| Inference method | LLM structured output, Temperature: 0 |
| Validation | All fields present; level must be one of 4 enum values |

### M3 — Concept Planner *(Unchanged)*

| Property | Specification |
|---|---|
| Input | `course_requirement` + `student_model` + cited content bundle |
| Output | Ordered concept graph: `[{concept, prerequisites, misconceptions, visual_type, duration_minutes}]` |
| Duration constraint | Total ≤ 25 minutes (5-min buffer for video assembly) |

### M4 — Script Generator *(Unchanged)*

| Property | Specification |
|---|---|
| Input | Concept graph + student_model + cited facts + PCK analogies |
| Output | Annotated script: narration text + `[VISUAL: type, content]` cue markers |
| N variants | 3 variants using 3 different scaffolding strategies |
| Hook requirement | First 60 seconds must contain curiosity trigger |

### M5 — CIDPP Critic Agent *(Unchanged)*

| Property | Specification |
|---|---|
| Input | 3 script variants + student_model |
| Output | Selected script + CIDPP scores + revision log |
| Max revision loops | 3 loops maximum per variant |

### M6 — Multimodal Planner *(Updated v2.0)*

| Property | Specification | Notes |
|---|---|---|
| Input | Approved script + concept graph | From M5 + M3 |
| Output | Visual plan: `[{segment_id, visual_type, content_spec, search_keywords, fallback_slide_path, duration_seconds}]` | `search_keywords` is new in v2.0 |
| Representation policy | Must follow visual selector table (Layer 4) | |
| Pexels keywords | LLM-generated 2-3 terms per segment | Semantically matched to educational content |
| Progressive reveal | Diagrams with > 3 elements annotated as `reveal:sequential` | |

### M7 — Video Renderer *(Fully Updated v2.0)*

| Property | Specification | Notes |
|---|---|---|
| Input | Approved script + visual plan | From M5 + M6 |
| Output | `video_url`, `supplementary_url` | Publicly accessible |
| TTS | Cartesia Neural TTS; ≤ 150 WPM for complex segments | Unchanged |
| Video background | Pexels B-roll (primary) → Ken Burns static image (fallback) | New in v2.0 |
| Subtitles | moviepy `SubtitlesClip` + `TextClip`; white text + black stroke; bottom position | New in v2.0 |
| BGM | Royalty-free MP3 from `resources/bgm/`; volume 0.12; looped; fade-out | New in v2.0 |
| Transitions | Random shuffle: fade_in / fade_out / slide_in / slide_out per clip | New in v2.0 |
| Concatenation | FFmpeg concat demuxer (not moviepy re-encode) | Avoids quality loss |
| NLM independence | Must not call any external sourcing APIs at render time | Unchanged |

### M8 — Feedback Logger *(Unchanged)*

| Property | Specification |
|---|---|
| Records per run | concept, student_level, subject, strategy_used, CIDPP_scores, video_url, outcome |
| Retention | All runs retained; append-only |
| Accessible to | M4 (pedagogy memory bank), M5 (reward model) |

---

## 6. Capability Roadmap (v2.2 — NLM Studio Edition)

> **Strategic Decision:** NotebookLM Studio outputs (slides, audio, quiz, study guide) are the highest-leverage upgrade available at zero additional cost. We integrate NLM Studio **before** pedagogical intelligence upgrades because it directly fixes the two most visible contest weaknesses: inaccurate visuals and robotic TTS voice.

---

### Phase 1 — RAG Foundation & Visual Upgrade ✅ COMPLETE (v0.6.0)

**Goal:** Replace all fragile external dependencies and close the visual quality gap.

- [x] Implement `modules/rag_retriever.py` (ChromaDB + sentence-transformers)
- [x] Create `resources/curriculum/` subject corpus (4 subjects)
- [x] Implement `scripts/ingest_rag.py` (build-time corpus ingestion)
- [x] Rewrite `modules/m1_sourcing.py` — Hybrid RAG + NLM path
- [x] Implement `modules/pexels_client.py` (Pexels search + download + local cache)
- [x] Upgrade `modules/m6_multimodal.py` — Subject-aware styles (nature/blueprint/sketchbook)
- [x] Rewrite `modules/m7_renderer.py` — FFmpeg B-roll + subtitles + BGM pipeline
- [x] Remove OpenSpace MCP
- [x] Update `Dockerfile` to v0.6.0
- [x] Full pipeline test on Biology/Taxonomy (Subject-Aware Visuals Verified)

---

### Phase 2 — NLM Studio Visual & Audio Upgrade 🎯 NEXT (v0.7.0)

**Goal:** Fix the #1 and #2 competition weaknesses — contextually inaccurate visuals and robotic TTS narration — using NotebookLM Studio outputs as primary sources.

**Why Phase 2 before Phase 3 (Pedagogical Intelligence)?**
- Pexels B-roll inaccuracy is immediately visible to human judges in Phase 2 (Elo Arena)
- NLM Audio Overview produces natural two-voice pedagogical dialogue vs. single-voice Cartesia TTS
- NLM slides are grounded in the same curriculum sources as the script — guaranteed visual accuracy
- All of this is **zero additional cost** (9 Gemini keys via KeyRotator already support free NLM)
- Implementation is **2–3 days** vs. weeks for reward model training

**Sub-phase 2A — NLM Skill Integration (Pre-requisite)**

| Task | File | Notes |
|---|---|---|
| Install `notebooklm-py[browser]` | `requirements.txt` | Use pinned release tag |
| Install Playwright Chromium | `Dockerfile` | `playwright install chromium` |
| Copy `scripts/nlm.py` from robonuggets/notebooklm-skill | `scripts/nlm.py` | CLI wrapper for all NLM operations |
| Copy `scripts/refresh_auth.py` from robonuggets/notebooklm-skill | `scripts/refresh_auth.py` | Headless cookie refresh |
| One-time login | manual | `python scripts/nlm.py login` — saves cookies to `~/.notebooklm/` |
| Mount cookie volume in Docker | `docker-compose.yml` | `~/.notebooklm:/root/.notebooklm` |
| Add `NLM_ENABLED=true` env var | `.env` + `docker-compose.yml` | Feature flag for NLM path |

**Sub-phase 2B — NLM Slide Deck as M6 Primary Visual (fixes inaccurate B-roll)**

| Task | File | Notes |
|---|---|---|
| Create `modules/nlm_studio.py` | NEW | Thin async wrapper around `scripts/nlm.py` CLI |
| Add `generate_slides(notebook_id, concept, style)` method | `nlm_studio.py` | Uses `generate-report --format CUSTOM --prompt SLIDE_PROMPT` |
| Define Teaching Monster slide prompt template | `nlm_studio.py` | Blackboard style: `#1a1a2e` bg, `#00d4ff` accent (matches blueprint style) |
| Integrate NLM slides into M6 visual plan | `modules/m6_multimodal.py` | New visual_type: `nlm_slide`; call `nlm_studio.generate_slides()` |
| Integrate NLM slide PNGs into M7 renderer | `modules/m7_renderer.py` | Feed slide images into `_render_infographic_segment()` (Ken Burns) |
| Fallback: keep Gemini infographic / Pexels | `modules/m7_renderer.py` | If NLM fails → M6B Gemini infographic → Pexels B-roll |

**Sub-phase 2C — NLM Audio Overview as M7 Primary Narration (fixes robotic TTS)**

| Task | File | Notes |
|---|---|---|
| Add `generate_audio(notebook_id, output_path)` to `nlm_studio.py` | `nlm_studio.py` | Uses `generate-audio --format DEEP_DIVE --output path.mp3` |
| Add NLM audio path to M7 renderer | `modules/m7_renderer.py` | If `NLM_AUDIO_ENABLED=true`: call NLM audio, download MP3, use as narration track |
| Sync NLM audio with slide images | `modules/m7_renderer.py` | Split NLM audio by segment duration; map to slide images |
| Fallback: keep Cartesia TTS | `modules/m7_renderer.py` | If NLM audio fails → Cartesia pool |

**Sub-phase 2D — NLM Quiz as M5 Supplementary Test**

| Task | File | Notes |
|---|---|---|
| Add `generate_quiz(notebook_id)` to `nlm_studio.py` | `nlm_studio.py` | Uses `generate-quiz --difficulty MEDIUM --quantity STANDARD` |
| Add NLM quiz check to M5 critic | `modules/m5_critic.py` | Post-script check: NLM quiz pass rate < 70% → flag for revision |

**Deliverable:** A pipeline run where NLM-generated slides and audio are the primary outputs, with full fallback chain. Verification: watch output video — visual should match narration topic exactly.

---

### Phase 3 — Pedagogical Intelligence (v0.8.0)

**Goal:** Activate reward model and Best-of-3 selection to maximize CIDPP scores.

- Add Best-of-3 script variant generation to M4
- Train initial LLM reward model on first 20 AI Student critique records from Phase 1 submissions
- Implement CIDPP multi-variant selection in M5
- Add misconception library (domain-specific, all 4 subjects) into M4 context
- Add PCK analogy retrieval store (seed 20+ entries per subject)
- Add NLM Study Guide as seed for M3 concept graph (replaces pure LLM-generated graph)
- Expand RAG corpus from Phase 1 Integrity failures

---

### Phase 4 — Meta-Policy & Self-Improvement (v0.9.0)

**Goal:** Build the self-improving loop that compounds advantage over the competition.

- Implement strategy win-rate tracker in M8 (strategy × level × subject)
- Implement ε-greedy strategy selector using accumulated meta-policy in M4
- Add pedagogy memory bank queries (top-2 few-shot examples per concept × level)
- Ingest Phase 2 Elo outcomes into M8 reward model
- Add progressive reveal enforcement to M6 + M7
- Implement RLT-style student-aligned reward (student model log-probability)
- Expand analogy store to 100+ entries across all subjects and levels

---

## 7. Evaluation Metrics

### 7.1 Internal Quality Metrics

| Internal Metric | Competition Dimension | Measurement Method |
|---|---|---|
| CIDPP Integrity score | Accuracy | Critic LLM judge; RAG citation verification |
| CIDPP Clarity score | Logic & Flow | Critic LLM judge; concept dependency graph |
| CIDPP Pertinence score | Adaptability | Critic LLM judge; persona vocabulary match |
| Hook rate flag | Engagement | First-60-second curiosity trigger presence check |
| Concept density | Logic & Flow | Count from concept graph + script length |
| Equation-to-analogy ratio | Adaptability | Count per concept segment |
| Synthetic student gap count | All four | Count of flags across 4 synthetic personas |
| Reward model score | All four | LLM judge CIDPP aggregate on selected script |

### 7.2 Competition Outcome Metrics

| Metric | Target | Tracking Cadence |
|---|---|---|
| AI Student score (Phase 1) | ≥ 8.0 / 10.0 average | After every Phase 1 submission |
| Elo win rate (Phase 2) | ≥ 60% across all matches | After each Phase 2 match |
| Strategy win rate delta | Winning strategy ≥ 10pp above losing strategy after 20 runs | Weekly |
| Pedagogy memory bank size | ≥ 50 high-quality exemplars by Phase 3 | Weekly |
| Generation time p95 | ≤ 1700 seconds | Every run |
| M1 RAG hit rate | ≥ 90% of sourcing from local RAG (not fallback) | Every run |

---

## 8. Technical Stack and Constraints (v2.0)

### 8.1 Required Tools

| Tool | Role | Required |
|---|---|---|
| ChromaDB | Local vector store for RAG | Yes — `all-MiniLM-L6-v2`, CPU-only |
| sentence-transformers | Local embedding model | Yes — CPU-only |
| notebooklm-py | NLM Studio API (slides, audio, quiz) | Yes (v0.7.0+) — `pip install notebooklm-py[browser]` |
| Playwright Chromium | NLM authentication browser | Yes (v0.7.0+) — one-time login, cookies persisted |
| Pexels API | B-roll fallback video sourcing | Fallback — `PEXELS_API_KEY` in `.env` |
| Cartesia API | TTS narration fallback | Fallback — `CARTESIA_API_KEY` in `.env` |
| moviepy v2 | Video compositing (slides + subtitles + BGM) | Yes |
| FFmpeg | Video encoding and concatenation | Yes — system-installed in Docker |
| Google LLM API | M2–M5 reasoning modules (9-key pool) | Yes — `GOOGLE_API_KEY_POOL` in `.env` |
| Web Search API | Stage 3 M1 fallback only | Optional — `SEARCH_API_KEY` in `.env` |

> **Restored in v2.2:** `notebooklm-py` — used via `robonuggets/notebooklm-skill` CLI pattern for slides, audio, and quiz. Auth cookies persisted via Docker volume mount.
> **Removed from v1.0:** NotebookLM MCP, OpenSpace MCP

### 8.2 Performance Constraints (Unchanged)

| Constraint | Limit | Engineering Approach |
|---|---|---|
| Total end-to-end time | ≤ 1800 seconds | Parallelise M1 + M2 + M3 where possible |
| M1 sourcing (RAG) | < 2 seconds | Local ChromaDB; no network |
| M1 sourcing (AI fallback) | < 30 seconds | Cap with timeout |
| M4 script generation (per variant) | ≤ 120 seconds | Cap at 3 variants |
| M5 critic + revision loops | ≤ 3 loops, ≤ 180 seconds total | Hard loop limit |
| M7 video rendering + upload | ≤ 900 seconds (15 minutes) | Pexels download cached; parallel Cartesia |
| Memory bank query latency | ≤ 2 seconds | Pre-computed embeddings |

### 8.3 Reproducibility Requirement (Unchanged)

- Entire pipeline runs in Docker with a single command
- All external API keys injected via environment variables (never hardcoded)
- M8 feedback log volume-mounted (persistent across container restarts)
- **RAG corpus and ChromaDB index baked into Docker image** (build-time ingestion)
- **Embedding model pre-downloaded at Docker build time** (fully offline at inference)

### 8.4 Failure Modes and Mitigations (Updated v2.0)

| Failure Mode | Impact | Mitigation |
|---|---|---|
| RAG returns insufficient results | Low-quality sourcing | Auto-fallback to AI Research (Stage 2) |
| Pexels API unavailable | No B-roll video | Fallback to Ken Burns static slide (existing SlideGenerator) |
| Pexels video download timeout | Missing clip | Use fallback slide; log for post-run analysis |
| Script generation exceeds time budget | Pipeline stalls | Hard timeout per M4 call; single-variant fallback |
| CIDPP critic infinite revision loop | Pipeline stalls | Hard cap: 3 loops maximum |
| Video rendering failure | No output URL | Retry once; return partial output with error flag |

---

## 9. Competitive Advantages (v2.0)

1. **Local RAG reliability** (high leverage): Zero external dependency in the 30-minute window. Every competitor using live NotebookLM/web scraping is one expired cookie away from a failed submission.

2. **Visual quality via B-roll + moviepy** (high leverage for Phase 2): Human judges respond to production quality. Dynamic video backgrounds + styled karaoke subtitles + background music = perceived premium quality. Borrowed and adapted from MoneyPrinterTurbo production patterns.

3. **RLT-style student-aligned reward** (highest leverage, Phase 3+): Teacher reward = student comprehension gain. First-mover advantage in competition context.

4. **Persona-conditional PCK retrieval** (medium leverage, low effort): Compounding knowledge base of expert analogies indexed by concept × learner level.

5. **Pedagogy memory bank** (low effort, high compounding value): By Phase 3, the agent generates lessons as variations on its own best prior work.

---

## 10. Open Questions (v2.0)

| Question | Options | Status |
|---|---|---|
| RAG corpus depth? | Start with curated summaries (~2k words/topic) or ingest full-length PDFs? | Decision: summaries first, expand based on Phase 1 Integrity failures |
| Video aspect ratio? | 16:9 landscape (educational) or 9:16 portrait (TikTok-style)? | Default 16:9; PRD specifies ≤ 30 min video |
| BGM selection? | Static royalty-free MP3s in repo, or dynamic fetch from Pixabay audio? | Decision: 3 static MP3s committed to `resources/bgm/` |
| Supplementary URL hosting? | S3, GCS, Vercel Blob, Cloudflare R2 | Engineering lead — pre-finals |
| M8 database? | SQLite (current), Postgres (scalable) | Current SQLite sufficient through Phase 2 |
| RLT student model? | Which 7B LLM as the comprehension evaluator? | ML lead — Phase 3 planning |

---

## 11. Glossary

| Term | Definition |
|---|---|
| PCK | Pedagogical Content Knowledge — knowing how to teach a subject, not just knowing the subject |
| CIDPP | Clarity, Integrity, Depth, Practicality, Pertinence — the 5-dimension rubric used by the CIDPP critic (M5) |
| ZPD | Zone of Proximal Development — the range just above what a student can do alone; the optimal teaching target |
| RLT | Reinforcement Learned Teacher — a training paradigm where the teacher's reward is the student's comprehension gain |
| Elo | The pairwise ranking system used in Phase 2 to rank agent outputs based on student preference |
| RAG | Retrieval-Augmented Generation — querying a local vector store to ground LLM outputs in curated facts |
| ChromaDB | Open-source local vector database used for the M1 RAG corpus |
| sentence-transformers | HuggingFace library providing CPU-efficient text embedding for semantic search |
| Pexels | Free stock video API used to source B-roll video footage for the M7 renderer |
| MoneyPrinterTurbo | Open-source short video generation reference (harry0703/MoneyPrinterTurbo) whose video assembly patterns inform our M7 renderer |
| Best-of-N | Generating N script variants and selecting the one with the highest CIDPP reward model score |
| Meta-policy | Learned policy for selecting scaffolding strategies based on accumulated win-rate data per (strategy, level, subject) |
| Pedagogy memory bank | Retrieval store of highest-scoring past lessons used as few-shot examples in M4 |
| Ken Burns effect | Slow zoom/pan animation applied to static images to create motion in the absence of B-roll video |
| BGM | Background Music — low-volume royalty-free audio looped beneath narration to improve perceived production quality |
| NLM Studio | NotebookLM Studio — v2.2 primary visual and audio source. Generates slides (via custom focus prompt), Audio Overview (Deep Dive podcast), Quiz, and Study Guide. Accessed via `notebooklm-py` library using `robonuggets/notebooklm-skill` CLI pattern. |
| NLM | NotebookLM — Restored as hybrid premium path in v2.0 for high-fidelity sourcing and study guides. |
| MCP (OpenSpace) | OpenSpace Model Context Protocol — Removed in v2.0 to simplify local pipeline. |

---

*teaching.monster — Internal Engineering Document*  
*PRD v2.2 — Updated by Antigravity AI Agent — April 2026 (NLM Studio Integration)*  
*Supersedes: Teaching_Monster_AI_Agent_PRD_v1.0.txt*
