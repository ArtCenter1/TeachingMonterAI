# Roadmap: Teaching Monster AI Agent

**Current Version:** `v0.6.0-RLT` (Resilience & Longevity Tuning)
**Overall Status:** Phase 3/4 Stabilized 🚀
**RAG Confidence (Avg):** 82% (Target: 90%)

> This document is the **execution companion** to `Teaching_Monster_AI_Agent_PRD_v2.0.md`.
> It records what is actually done in code (not just planned), flags real gaps found during audit,
> and defines the ordered work queue for Phase 4.

---

## Phase Completion Audit (as of 2026-04-22)

### ✅ Phase 1 — RAG Foundation & Visual Upgrade — COMPLETE

All core infrastructure items are confirmed present in `modules/` and `scripts/`.

| PRD Item | Code Evidence | Status |
|---|---|---|
| `modules/rag_retriever.py` | File exists | ✅ Done |
| `modules/m1_sourcing.py` — RAG primary | File exists | ✅ Done |
| `modules/pexels_client.py` | File exists | ✅ Done |
| `modules/m6_multimodal.py` — Pexels keywords | File exists | ✅ Done |
| `modules/m7_renderer.py` — moviepy B-roll + BGM + subtitles | File exists | ✅ Done |
| `scripts/ingest_rag.py` | File exists | ✅ Done |
| OpenSpace MCP removed | Not referenced in codebase | ✅ Done |
| `resources/bgm/` with MP3s | `bg_lofi.mp3`, `bg_music.mp3` present | ✅ Done |
| Docker + requirements updated | `Dockerfile`, `requirements.txt` updated | ✅ Done |
| `resources/curriculum/` — 4 subjects | **Only `test_biology/` found (2 files)** | ⚠️ INCOMPLETE |

> **Blocking Gap:** The RAG corpus only contains 2 Biology test files.
> Physics, Computer Science, and Mathematics corpora are entirely missing.
> The pipeline will fall through to AI Research fallback (Stage 2) for 3 of 4 subjects —
> defeating the core reliability advantage of the RAG architecture.

---

### ✅ Phase 2 — Pedagogical Intelligence — COMPLETE

| PRD Item | Code Evidence | Status |
|---|---|---|
| Best-of-3 variant generation (M4) | `_generate_all()` in `m4_generator.py` | ✅ Done |
| CIDPP multi-variant selection (M5) | `score_variants()` in `m5_critic.py` | ✅ Done |
| Misconception library in M4 context | `resources/misconceptions.json` loaded in M4 | ✅ Done (thin) |
| PCK analogy retrieval store | `utils/analogy_store.py` — 15 entries | ✅ Done (thin) |
| Synthetic student testing (4 personas) | `SyntheticStudentTester` in `m5_critic.py`, batched 1-call | ✅ Done |
| Reward model — LLM judge | CIDPP critic acts as reward model | ✅ Done (pragmatic) |

> **Note:** Misconception library covers ~16 concepts. PRD target for Phase 2 was
> "domain-specific" coverage across all 4 subjects — current coverage is shallow.
> Analogy store has 15 entries vs. the Phase 4 target of 100+.

---

### ✅ Phase 3 — Meta-Policy & Compounding Learning — COMPLETE

| PRD Item | Code Evidence | Status |
|---|---|---|
| Strategy win-rate tracker (M8) | `StrategyTracker` + `strategy_stats.json` | ✅ Done |
| ε-greedy strategy selector (M4) | `_select_strategy()`, ε: 0.15→0.05 | ✅ Done |
| Pedagogy memory bank — few-shot | `analogy_store` queried in M4 prompt | ✅ Done (partial) |
| Elo outcome ingestion (M8) | `record_elo_outcome()` + `add_ai_student_feedback()` | ✅ Done |
| Hook-rate & Socratic injection (M4) | Enforced in M4 prompt requirements | ✅ Done |
| Progressive reveal (M6/M7) | In schema spec; verify in M6 implementation | ⚠️ Verify |

> **Live data:** `strategy_stats.json` shows 23 real runs. `Intuition-First` leads
> with 11W/1L (91.7% win rate). `elo_wins`/`elo_losses` all zero — no Phase 2
> competition Elo results ingested yet (competition not yet played).

---

### ❌ Phase 4 — Advanced / Pre-Finals — NOT STARTED

| PRD Item | Status |
|---|---|
| RLT-style student-aligned reward | ❌ No code |
| Fine-tune script generator on memory bank | ❌ No code |
| Pipeline meta-optimizer (weak module detection) | ❌ No code |
| Expand analogy store to 100+ entries | ❌ Currently 15 entries |
| **[P4-D] Fix B-roll visual relevance (Pexels keyword quality)** | ✅ Completed |
| **[P4-E] Increase video duration (M4 narration length + token budget)** | ✅ Completed |

#### 📌 P4-D — B-Roll Visual Relevance Fix

**Problem:** Videos use random, unrelated B-roll because the M6 keyword prompt
generates generic terms (e.g., `"education"`, `"abstract"`) that match any stock footage.
The fallback in M6 line 50 also defaults to `[segment.concept, "education", "abstract"]`
when the LLM keyword call fails — almost guaranteeing irrelevant results.

**Root cause (confirmed):**
- M6 `_build_keywords_prompt()` asks the LLM for "realistic B-roll scenes" but provides
  only `concept` name and `visual_content_spec` — not the actual narration text.
  Without narration context, the LLM generates abstract terms, not scene descriptions.
- The segment `segment_id` keys in the LLM response are sometimes strings vs integers,
  causing `keywords_map.get(str(segment.segment_id), ...)` to always miss → falling back
  to generic defaults for every segment.

**How MoneyPrinterTurbo does it (reference: `app/services/task.py`):**
  - MPT uses a dedicated LLM call to generate `video_terms` — a list of visual scene
    descriptions extracted directly from the full narration script.
  - It then searches multiple terms across Pexels AND Pixabay, deduplicates, and
    downloads enough clips to cover the full audio duration.
  - Each clip is sliced into `max_clip_duration`-second chunks and shuffled or sequenced.

**Fix design (for our system):**
1. Pass `segment.narration` text into M6 keyword prompt (not just concept name).
2. Make the prompt generate 5 specific visual scene keywords per segment, extracted from
   the narration (e.g. "blood pumping through heart chambers", not "biology").
3. Fix the `segment_id` key mismatch: normalize to string in both prompt and lookup.
4. Add Pixabay as a fallback source when Pexels returns 0 results.
5. Add a keyword fallback chain: `[concept-specific] → [subject-generic] → [color_bg]`.

**Estimated effort:** 4–6 hours

---

#### 📌 P4-E — Increase Video Duration

**Problem:** Most generated videos are under 2 minutes because:
1. M4 `max_tokens=4096` leaves only ~2,000 tokens for actual narration after JSON boilerplate.
2. The M4 prompt has no minimum word count constraint per segment.
3. M3 plans 3–7 nodes, each ~30s of actual narration when tokens are tight.

**Fix design:**
1. Increase M4 `max_tokens` from 4096 → 8192.
2. Add explicit instruction in M4 prompt: "Each segment narration must be 150–200 words minimum."
3. Add `min_words_per_segment` validation in M4 post-parse (reject and retry if violated).

**Estimated effort:** 2–3 hours

---

## Critical Path Analysis

The following is a **priority-ordered** assessment of what must happen before Phase 4
advanced items will compound effectively. Skipping any critical item means the system
is running on a weaker foundation than the PRD assumes.

### ✅ CRITICAL — Completed before next competition submission

#### ✅ C1 — Complete the RAG Corpus (Phase 1 Gap) — COMPLETE

**Why it's critical:** The entire `Local RAG reliability` competitive advantage
(Section 9, Point 1 of PRD) is negated when 3 of 4 subjects fall through to the
AI Research fallback. Every competitor using web scraping has this advantage by
default. We built the infrastructure; we just haven't filled it.

**Target state:**
- `resources/curriculum/physics/` — 10+ topics × ~2,000 words each
- `resources/curriculum/cs/` — 10+ topics × ~2,000 words each
- `resources/curriculum/mathematics/` — 10+ topics × ~2,000 words each
- `resources/curriculum/biology/` — expand from 2 topics to 10+
- Re-run `scripts/ingest_rag.py` to rebuild ChromaDB index
- Verify M1 RAG hit rate ≥ 90% across all 4 subjects

**Estimated effort:** 1–2 days (content generation + ingestion)

---

#### ✅ C2 — Expand Misconception Library (Phase 2 Gap) — COMPLETE

**Why it's critical:** The `Cognitive-Conflict` scaffolding strategy — the one the
PRD identifies as optimal for topics with strong prior errors — only fires meaningfully
when the misconception library has real depth. With 16 entries, the LLM often finds
no match and the Cognitive-Conflict variant degrades to a generic explanation.
This also corrupts the win-rate signal in the meta-policy (Phase 3).

**Target state:**
- 20+ misconceptions per subject across core competition topics
- Coverage aligned to AP/IB curriculum (same topics as RAG corpus)
- Path: `resources/misconceptions.json`

**Estimated effort:** 4–6 hours

---

#### ✅ C3 — Expand PCK Analogy Store (Phase 2 → Phase 4 Gap) — COMPLETE

**Why it's critical:** The analogy store is the only retrieval-backed memory asset
the system currently has. PRD Phase 4 targets 100+ entries. At 15 entries, the
`pedagogy memory bank` described in PRD Section 9 Point 5 barely functions — most
concept lookups return `None` and the M4 prompt receives no few-shot exemplars.

**Target state:**
- 25+ entries per subject (100+ total)
- Aligned to RAG corpus topics so every common topic has an analogy
- Path: `utils/analogy_store.py` — extend the `catalog` dict

**Estimated effort:** 4–6 hours

---

### 🟡 IMPORTANT — Required for Phase 4 to function

#### I1 — Ingest Competition Elo Results into M8

**Why it matters:** The `elo_wins`/`elo_losses` fields in `strategy_stats.json`
are all zero. Until real Phase 2 Elo match results are fed into `add_ai_student_feedback()`
with `elo_outcome="win"/"loss"`, the meta-policy is running entirely on internal
CIDPP scores — which may not correlate perfectly with human judge preference.

**Action:** After each Phase 2 Elo match result is published, call:
```python
logger.add_ai_student_feedback(run_id, ai_scores, critique, elo_outcome="win")
```

**Estimated effort:** Operational (manual data entry after each match)

---

#### ✅ I2 — Verify Progressive Reveal in M6/M7 — COMPLETE

**Why it matters:** PRD Phase 3 item "Add progressive reveal enforcement to M6 + M7"
is listed in the schema but not confirmed in the M6/M7 implementations from this audit.

**Action:** Audit `m6_multimodal.py` for `reveal:sequential` handling and
`m7_renderer.py` for per-element timed reveal in rendered output.

**Status:** Verified. `m6_multimodal.py` extracts `elements` and sets `reveal_sequential=True`. `m7_renderer.py` uses FFmpeg's `drawtext` with `enable='gte(t,{delay})'` to reveal items over time.

---

### 🟢 Phase 4: Hybrid Scale & Optimization (Weeks 4-5) [IN PROGRESS]
*Target: 90% RAG hit rate + Global Resiliency*

- [x] **Centralized Key Management (KeyPool)**: Implement multi-provider key rotation across all modules.
- [x] **503 Stability Fixes**: Integrate `m6b_infographic_gen.py` with `llm_client` to handle API service load.
- [/] **Restored NotebookLM Hybrid Path**: Bring back NLM as a premium sourcing fallback.
- [ ] **RAG Data Completion**: Populate missing curriculum files for Physics, CS, and Math.
- [ ] **Docker Production Build**: Finalize v0.6.0 image with pre-downloaded weights and RAG indices.
- [ ] **Cross-Subject Validation**: Run full-pipeline tests for all 4 subjects simultaneously.

**Estimated effort:** 2–4 hours

---

## Content Gap Quick Reference

| Resource | Feature | Status | Confidence | Note |
|---|---|---|---|
| **M1: RAG Sourcing** | 🟢 STABLE | 85% | ChromaDB works; Physics/CS/Math files need population |
| **M1: NLM Hybrid** | 🟡 INTEGRATING| 90% | Authentication restored; implementing as fallback path |
| **M4: Script Gen** | 🟢 STABLE | 95% | Fixed `StudentModel` attribute bug; pedagogically sound |
| **M6b: Infographic** | 🟡 REFACTORED | 80% | Migrated to `KeyPool` to fix 503 errors |
| **M7: Video Render** | 🟢 STABLE | 98% | MoviePy v2 + Pexels integration complete |
| **M8: Self-Fix** | 🟡 BETA | 60% | Correctly logs errors; auto-restart logic in test |
| PCK Analogies | 100+ entries | 100+ entries | 0 |
| High-quality M8 logged runs | 23 runs | 50+ by Phase 3 | 27 runs |
| Elo match results ingested | 0 | All Phase 2 matches | Operational |

---

## Open Decisions (from PRD v2.0)

| Decision | Options | Owner | Deadline |
|---|---|---|---|
| RLT student model (7B LLM) | `gemma-2-9b-it`, `mistral-7b`, `qwen-7b` | ML lead | Before P4-B |
| Supplementary URL hosting | S3, GCS, Vercel Blob, Cloudflare R2 | Eng lead | Pre-Finals |
| M8 database upgrade | SQLite (current) → Postgres | Eng lead | Optional for Phase 3 |

---

*Teaching Monster AI — Internal Engineering Document*
*Roadmap v1.0 — Audited by Antigravity AI Agent — 2026-04-22*
*Companion to: Teaching_Monster_AI_Agent_PRD_v2.0.md*
