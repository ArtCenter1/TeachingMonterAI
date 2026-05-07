---
name: teaching-monster-report
description: Retrieve and parse AI evaluation reports from the Teaching Monster contest platform (teaching.monster). Use when you need to check scores, feedback, or diagnostics for a submitted teaching video.
---

# teaching-monster-report

Retrieves the **AI Student 深度評測報告** (AI Student Deep Evaluation Report) from the Teaching Monster contest platform using browser-harness and the user's logged-in Chrome session.

## Prerequisites

- `browser-harness` daemon must be running (it auto-starts on first `browser-harness -c` call)
- User must be logged in to `teaching.monster` in their Chrome browser
- Target URL pattern: `https://teaching.monster/app/competitions/{competition_id}/manage`

## Report Structure

Each evaluation report contains 4 tabs:

| Tab | Content |
|-----|---------|
| 教學地圖 (Teaching Map) | Video content outline, topic segments, teaching mode (Mixed/Deductive/Inductive) |
| 教學診斷 (Teaching Diagnostics) | Specific issues found, numbered list of problems |
| 製作與影音分析 (Production & AV Analysis) | Voice quality, visual consistency audit |
| 學習體驗模擬 (Learning Experience Simulation) | Student engagement simulation results |

### Score Metrics (評分總覽)

| Metric | Chinese | Score Range | Meaning |
|--------|---------|-------------|---------|
| Accuracy | 正確性 | 1–5 | Factual correctness of content |
| Logic | 邏輯流暢 | 1–5 | Narrative/logical flow |
| Adaptability | 適配度 | 1–5 | Age/audience fit |
| Engagement | 吸引力 | 1–5 | Student engagement level |

## Usage

```bash
browser-harness -c '
# Step 1: Navigate to the competition manage page
new_tab("https://teaching.monster/app/competitions/1/manage")
wait_for_load()

# Step 2: Take a screenshot to see the list of submissions
path = capture_screenshot()
print("Page loaded:", page_info()["url"])

# Step 3: Find the target topic row (e.g., 向量/Vectors)
# The management panel shows a table with columns: 主題, 狀態, AI評測狀態, 操作
# Look for rows where AI評測狀態 is 已完成 (Completed)
# The report button is the bar-chart icon (📊) in the 操作 column

# Step 4: Click the report icon for your target topic
# Use coordinate click - take screenshot first to find the bar icon position
path = capture_screenshot()
# Identify the row and click the last icon in that row
click_at_xy(x, y)  # Replace with actual coords from screenshot

# Step 5: Wait for report modal to open
wait_for_load()
wait(1.0)

# Step 6: Capture the report
path = capture_screenshot()
print("Report captured:", path)

# Step 7: Read all 4 tabs
# Tab buttons are: 教學地圖, 教學診斷(N), 製作與影音分析, 學習體驗模擬
# Click each tab and screenshot
'
```

## Automated Full Report Retrieval Pattern

```bash
browser-harness -c '
import json

new_tab("https://teaching.monster/app/competitions/1/manage")
wait_for_load()
wait(2.0)

# Get all topic rows and their status
rows = js("""
  Array.from(document.querySelectorAll("table tbody tr, [class*=row]")).map(r => ({
    text: r.innerText,
    html: r.innerHTML.slice(0, 200)
  }))
""")
print(json.dumps(rows, ensure_ascii=False, indent=2))
'
```

## Known Page Structure (as of 2026-05)

### Competition Management Page
- URL: `https://teaching.monster/app/competitions/1/manage`
- Opens a modal titled: **生成控制面板** (Generation Control Panel)
- Model name shown at top: `TeachingMonsterAI_01`
- Table columns: 主題 | 狀態 | AI評測狀態 | 操作
- 操作 (Action) icons per row (left to right): ⚡ Generate | 👁 Preview | 📊 Report

### Report Modal
- Title: **AI Student 深度評測報告: {topic_name}**
- Scores shown in colored tiles (green=good, yellow=mid, red=low)
- Observation summary in English on the right side

## Known Issues & Workarounds

### Login Required
If the page redirects to a login page, stop and ask the user to log in manually. Do not type credentials.

```bash
browser-harness -c '
new_tab("https://teaching.monster/app/competitions/1/manage")
wait_for_load()
info = page_info()
if "login" in info["url"] or "auth" in info["url"]:
    print("BLOCKED: Please log in to teaching.monster first, then run again.")
else:
    print("Logged in:", info["url"])
'
```

### Report Not Yet Available
If AI評測狀態 shows 尚未評測 (Not yet evaluated), the report is not available. Only rows showing 已完成 (Completed) have a clickable report icon.

### Modal Detection
After clicking the report icon, wait for the modal overlay to appear before screenshotting:
```python
wait(1.5)  # Modal animation takes ~1s
path = capture_screenshot()
```

## Example: 向量 (Vectors) Report — Retrieved 2026-05-07

**Scores:**
- 正確性 (Accuracy): **1.9 / 5** 🔴 Low — Formula error detected (y2-x1 instead of y2-y1)
- 邏輯流暢 (Logic): **3.1 / 5** 🟡 Mid
- 適配度 (Adaptability): **1.1 / 5** 🔴 Low
- 吸引力 (Engagement): **1.0 / 5** 🔴 Low

**Observation Summary:**
> "The video provides a standard high-school level introduction to vectors, covering definitions, scalar comparisons, and representations. However, it contains a critical, repeated factual error in the formula for calculating vector components from coordinates (stating y2-x1 instead of y2-y1). Furthermore, the visual presentation is poor, relying on irrelevant AI-generated imagery and gibberish text that fails to support the instructional goals."

**Key Issues (教學診斷):**
1. Mathematical formula error: y2-x1 written instead of y2-y1
2. Visual/audio disconnect: visuals are irrelevant to narration
3. Infographic text is illegible/gibberish (AI-generated image artifacts)
4. Poor engagement — no interactivity or student-facing hooks
5. Audience fit is low — presentation not calibrated to target level

**製作與影音分析 (AV Analysis):**
- 敘事連貫性 (Vocal Consistency): High-quality TTS voice throughout ✅
- 視覺內容一致性: Visuals almost entirely disconnected from narration ❌
  - At 00:05: treasure hunt mentioned but screen shows cluttered infographic
  - At 03:30: vector subtraction explained while screen shows unrelated content

## Feedback Loop Integration

After retrieving a report, write key findings to `m8_feedback.json` to feed the pipeline's RLT (Reinforcement Learned Teacher) loop:

```python
import json, datetime, pathlib

feedback_path = pathlib.Path("D:/My_Projects/TeachingMonsterAI/m8_feedback.json")
report_data = {
    "timestamp": datetime.datetime.now().isoformat(),
    "topic": "向量",
    "competition_id": 1,
    "scores": {
        "accuracy": 1.9,
        "logic": 3.1,
        "adaptability": 1.1,
        "engagement": 1.0
    },
    "issues": [
        "Formula error: y2-x1 instead of y2-y1",
        "Visual/audio disconnect throughout",
        "Infographic gibberish text artifacts",
        "Low engagement — no student-facing hooks",
        "Poor audience calibration"
    ],
    "observation_summary": "Critical formula error + poor visual alignment. Needs regeneration."
}

existing = json.loads(feedback_path.read_text()) if feedback_path.exists() else []
if isinstance(existing, dict):
    existing = [existing]
existing.append(report_data)
feedback_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
print("Feedback written to m8_feedback.json")
```
