# Implementation Plan: Phase 4 - Part 2 (Synthetic Students & Analogy Retrieval)

Following the success of the A/B selection framework, we will now implement the next layer of the **Pedagogical Intelligence** stack as defined in the PRD.

## Proposed Changes

### 0. Fix LLM Router (Blocker)
We encountered an `HTTP 400` error because `google/gemini-2.0-flash-exp:free` was being routed to the Google SDK instead of OpenRouter.
- Update `llm_client.py` to allow `google/` models to go to OpenRouter if they have the `:free` suffix or if OpenRouter is preferred.
- Ensure `system_instruction` handling in `_call_gemini_sdk` is robust against `None`.

### 1. Synthetic Student Testing (M5 Enhancement)
Already partially implemented, but needs:
- Robust error handling for the parallel persona calls.
- Integration test to ensure the "winning" script actually gets modified if the students find major gaps.
- **Cost Optimization**: Per user request, these 4 parallel calls will use a **free/cheap model** (e.g., `google/gemini-2.0-flash-exp:free` via OpenRouter) to minimize development costs.
- **Personas**:
    - **Persona A**: Confused visual learner (needs diagrams before words).
    - **Persona B**: Math-anxious student (flags equations without analogies).
    - **Persona C**: High-performing abstract thinker (flags oversimplification).
    - **Persona D**: Low prior knowledge, high curiosity (flags missing prerequisites).

**Logic**: If the personas collectively flag > 2 significant gaps, the script triggers one final revision pass in the CIDPP loop.

### 2. PCK Analogy Retrieval Store (M4 Enhancement)
We will move from purely "generated" analogies to a **retrieval-augmented store** of expert pedagogical moves (PRD 4).
- **Seeds**:
    - CS: Recursion → Russian nesting dolls
    - Physics: Conservation of momentum → Billiard balls / Ice skater
    - Biology: DNA transcription → Photocopying a blueprint
    - Maths: Derivative (no calc) → Speedometer vs. Odometer
    - ML: Self-attention → Word highlighting context
- **Retrieval**: The `ScriptGenerator` will query this store at the start of each concept node to ground its explanation in proven metaphors.

### 3. Environment & Meta-Policy
- **.env Update**: Add `SYNTHETIC_STUDENT_MODEL` to allow toggling between free and premium models.
- **FeedbackLogger (M8)**: Update to compute and report strategy win rates categorized by `student_level` and `subject`.

## Proposed Files

### [NEW] [analogy_store.py](file:///D:/My_Projects/TeachingMonsterAI/utils/analogy_store.py)
A lightweight retrieval utility managing the curated PCK (Pedagogical Content Knowledge) analogies.

### [MODIFY] [m5_critic.py](file:///D:/My_Projects/TeachingMonsterAI/modules/m5_critic.py)
- Integrate `SyntheticStudentTester` class.
- Update `score_variants` to include the synthetic student pass as a final filter.

### [MODIFY] [m4_generator.py](file:///D:/My_Projects/TeachingMonsterAI/modules/m4_generator.py)
- Update `generate_variants` to query `AnalogyStore` for each concept segment.

## Verification Plan

### Automated Verification
- Run a concept like "Conservation of Momentum" for a "Middle School" persona.
- Verify that the billiard ball analogy is retrieved and used in the script.
- Verify that the `m8_feedback.json` logs reports from all 4 synthetic student personas.
- Check that `SYNTHETIC_STUDENT_MODEL` is correctly picked up from `.env`.

---
## User Review Required

> [!IMPORTANT]
> The Synthetic Student Test adds 4 parallel LLM calls to the pipeline. By using a **free model** from OpenRouter (e.g. Gemini 2.0 Flash Exp), we mitigate the cost, but latency will still increase (approx. +15-20s). Is this acceptable?
