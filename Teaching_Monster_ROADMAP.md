# Teaching Monster AI — Engineering Roadmap
### Living Document · Companion to PRD v2.0

| Field | Value |
|---|---|
| Last Updated | 2026-04-22 |
| Current System Version | v0.5.0 |
| Pipeline Status | Phase 3 COMPLETE — Phase 4 NOT STARTED |
| Next Milestone | Phase 4-A: Curriculum Corpus Completion |

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

---

## Critical Path Analysis

The following is a **priority-ordered** assessment of what must happen before Phase 4
advanced items will compound effectively. Skipping any critical item means the system
is running on a weaker foundation than the PRD assumes.

### 🔴 CRITICAL — Must fix before next competition submission

#### C1 — Complete the RAG Corpus (Phase 1 Gap)

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

#### C2 — Expand Misconception Library (Phase 2 Gap)

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

#### C3 — Expand PCK Analogy Store (Phase 2 → Phase 4 Gap)

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

#### I2 — Verify Progressive Reveal in M6/M7

**Why it matters:** PRD Phase 3 item "Add progressive reveal enforcement to M6 + M7"
is listed in the schema but not confirmed in the M6/M7 implementations from this audit.

**Action:** Audit `m6_multimodal.py` for `reveal:sequential` handling and
`m7_renderer.py` for per-element timed reveal in rendered output.

**Estimated effort:** 2–4 hours

---

#### I3 — Multi-Subject Docker Build Validation

**Why it matters:** Phase 1's final verification item was "full Docker build + end-to-end
pipeline test on all 4 subjects." With the corpus missing for 3 subjects, this was
never fully passed. Must be completed before contest Phase 3 (Grand Final).

**Action:** After C1 is complete, run 4 end-to-end pipeline tests (one per subject)
inside Docker and confirm RAG hit rate ≥ 90%.

**Estimated effort:** 2–4 hours

---

### 🟢 PHASE 4 — Build after C1/C2/C3 are complete

#### P4-A — Pipeline Meta-Optimizer

**Goal:** Identify which module most frequently causes low CIDPP scores across M8
feedback history, then dynamically route those calls to a stronger/larger LLM model.

**Design:**
- Read `m8_feedback.json`, compute average CIDPP dimension scores per module stage
- If `integrity` is consistently lowest → promote M1 RAG sourcing budget
- If `clarity` is lowest → promote M5 critic revision loops
- Config: map module → model tier in `config/`
- Integrate into `main.py` pre-run model allocation

**Estimated effort:** 1–2 days

---

#### P4-B — RLT-Style Student-Aligned Reward

**Goal:** Replace CIDPP LLM judge as the sole reward signal with a student
comprehension measure: give the student model the key concept, then probe whether
it can reconstruct the correct answer after reading the script.

**Design:**
- Select a 7B LLM as the student comprehension evaluator (recommend: `gemma-2-9b-it` via OpenRouter)
- Post-M5: generate 3 comprehension probes per concept node
- Feed the selected script to the student LLM → measure correct answer log-probability
- Blend score: 0.6 × CIDPP + 0.4 × RLT-score → new selection criterion in M5

**Decision needed:** Which 7B model to use as student evaluator (see PRD Open Questions)

**Estimated effort:** 2–3 days

---

#### P4-C — Fine-Tune Script Generator on Pedagogy Memory Bank

**Goal:** Use M8's accumulated high-scoring lessons as positive few-shot examples
directly in M4's prompt, creating a compounding quality improvement loop.

**Design:**
- M8 query: retrieve top-5 scoring lessons by subject × level × strategy
- Inject as `EXEMPLARY LESSONS (Reference for quality and style):` block in M4 prompt
- Threshold: only inject lessons with CIDPP total ≥ 40/50
- Update query logic in `m4_generator.py`

**Pre-requisite:** ≥ 20 high-quality logged runs (currently have 23 — borderline usable)

**Estimated effort:** 1 day

---

## Recommended Execution Order

```
Week 1 (Pre-Grand Final Sprint):
  [C1] Complete RAG corpus — all 4 subjects        ← HIGHEST PRIORITY
  [C2] Expand misconception library                 ← Same sprint
  [C3] Expand analogy store to 100+ entries         ← Same sprint
  [I3] Run 4-subject Docker validation test         ← Gate for Grand Final readiness

Week 2 (Phase 4 Foundation):
  [I1] Ingest any available Elo match results
  [I2] Verify progressive reveal in M6/M7
  [P4-C] Few-shot injection from M8 memory bank     ← Lowest effort, high compounding value

Week 3 (Phase 4 Advanced):
  [P4-A] Pipeline meta-optimizer
  [P4-B] RLT student-aligned reward                 ← Needs model decision first
```

---

## Content Gap Quick Reference

| Resource | Current State | Target | Gap |
|---|---|---|---|
| RAG corpus — Biology | 2 topics | 10+ topics | 8 topics |
| RAG corpus — Physics | 0 topics | 10+ topics | 10 topics |
| RAG corpus — CS | 0 topics | 10+ topics | 10 topics |
| RAG corpus — Mathematics | 0 topics | 10+ topics | 10 topics |
| Misconceptions — all subjects | ~16 entries | 80+ entries | ~64 entries |
| PCK Analogies | 15 entries | 100+ entries | 85+ entries |
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
