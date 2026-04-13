# AI Agent Instructions: Teaching Monster AI

Welcome, AI Agent. This project follows a strict 8-module pedagogical video generation pipeline.

## 🛠️ Mandatory Procedures
1. **Consult Onboarding First**: Before every task, you MUST read [ONBOARDING.md](file:///d:/My_Projects/TeachingMonsterAI/ONBOARDING.md). It defines the system architecture and the mission goals.
2. **Check for Errors**: Always verify if `m8_errors.json` exists. If the pipeline fails, detailed tracebacks are stored there.
3. **Environment**: This project runs in Docker. Always verify changes by checking container logs: `docker logs -f teaching-monster-app`.

## 🏗️ Project Architecture
- **M1-M8 Pipeline**: Orchestrated by [main.py](file:///d:/My_Projects/TeachingMonsterAI/main.py).
- **Modules**: Located in `modules/`. Keep them functional and independent.
- **Skills**: Reuse or evolve skills in the `skills/` directory via the OpenSpace MCP.

## 💻 Core Commands
- **Build/Run**: `docker-compose up --build -d`
- **Logs**: `docker logs teaching-monster-app --tail 100`
- **Shell**: `docker exec -it teaching-monster-app bash`
- **Local Test**: `.venv\Scripts\python.exe main.py`

---
*If you are unsure of the logic, consult the "Mission" section in ONBOARDING.md. Every change must improve pedagogical quality or pipeline stability.*
