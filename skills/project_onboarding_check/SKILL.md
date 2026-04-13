---
name: project_onboarding_check
description: Mandatory procedure for AI agents initializing a session in the TeachingMonsterAI repository. Ensures goal alignment and architecture awareness.
---

# Project Onboarding Check

This skill identifies the mission and development protocols for the Teaching Monster AI project. It should be used by any AI agent during session initialization or when asked "What is this project about?".

## Verification Steps

1. **Locate Documentation**: Locate and read the mission statement in [ONBOARDING.md](file:///d:/My_Projects/TeachingMonsterAI/ONBOARDING.md).
2. **Understand Pipeline**: Verify you understand the 8-module pipeline (M1-M8) described in Section 2 of the onboarding guide.
3. **Check for "Nagging Errors"**: Search the root directory for `m8_errors.json`. If it exists, prioritize fixing recorded failures.
4. **Pedagogical Alignment**: Ensure any code change respects the learner persona and pedagogical goals defined in the project PRD.

## Common Knowledge
- **Environment**: Docker (Linux). Avoid pathing assumptions (always check platform).
- **Core Library**: `notebooklm-py` is used for M1 sourcing.
- **Model Standard**: Use standard Gemini identifiers (e.g., `gemini-1.5-flash-002`) and prefer OpenRouter for `free` tier fallback.

---
*By using this skill, the agent confirms they have consulted the official developer documentation and are ready to maintain the project's pedagogical standards.*
