from __future__ import annotations
import json
import os
import time
from typing import List
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from loguru import logger

from keyrotator.pool import KeyPool
import httpx


class ReviveRequest(BaseModel):
    provider: str  # "gemini" or "openrouter"
    key_index: int  # 0-based index


def KeyRotatorRouter(pools: List[KeyPool]) -> APIRouter:
    """
    Factory function that returns a configured APIRouter.
    Mount with: app.include_router(KeyRotatorRouter([gemini_pool, openrouter_pool]), prefix="/dev")

    Exposes:
      GET  /dev/pool-status       → JSON status of all pools
      POST /dev/pool-status/revive → Manually revive a SPENT/DEAD key
      GET  /dev/pool-status/ui    → Self-contained HTML dashboard
    """
    router = APIRouter(tags=["dev-keypool"])
    pool_map = {p.provider: p for p in pools}

    async def _get_ngrok_url():
        """Attempt to fetch the public tunnel URL from the ngrok sidecar."""
        try:
            async with httpx.AsyncClient(timeout=0.5) as client:
                r = await client.get("http://ngrok:4040/api/tunnels")
                if r.status_code == 200:
                    data = r.json()
                    tunnels = data.get("tunnels", [])
                    if tunnels:
                        return tunnels[0].get("public_url")
        except Exception:
            pass
        return None

    @router.get("/pool-status")
    async def get_pool_status():
        return {
            "pools": [p.get_status() for p in pools],
            "public_url": await _get_ngrok_url(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    @router.post("/pool-status/revive")
    async def revive_key(body: ReviveRequest):
        pool = pool_map.get(body.provider)
        if pool is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Provider '{body.provider}' not found."},
            )
        success = pool.revive(body.key_index)
        if not success:
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid key index {body.key_index}"},
            )
        logger.info(
            f"[keyrotator] Revived {body.provider} key #{body.key_index} via dashboard"
        )
        return {
            "ok": True,
            "message": f"Key #{body.key_index} revived for {body.provider}",
        }

    @router.get("/pool-status/ui", response_class=HTMLResponse)
    async def get_pool_status_ui():
        status_data = [p.get_status() for p in pools]
        public_url = await _get_ngrok_url()
        contest_mode = os.getenv("CONTEST_MODE", "false").lower() == "true"
        status_json = json.dumps(
            {
                "pools": status_data,
                "public_url": public_url,
                "contest_mode": contest_mode,
            }
        )
        html = _render_dashboard(status_json)
        return HTMLResponse(content=html)

    return router


def _render_dashboard(initial_json: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KeyRotator — Teaching Monster</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0b0e14;
    --card: rgba(30, 41, 59, 0.7);
    --border: rgba(255, 255, 255, 0.1);
    --accent: #8b5cf6;
    --success: #10b981;
    --warning: #f59e0b;
    --error: #ef4444;
    --text: #f8fafc;
    --text-dim: #94a3b8;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }}
  body {{
    background: var(--bg);
    background-image: radial-gradient(circle at top right, #1e1b4b, transparent), radial-gradient(circle at bottom left, #1c1917, transparent);
    color: var(--text);
    padding: 32px;
    min-height: 100vh;
  }}

  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 32px;
  }}

  h1 {{ font-size: 1.5rem; font-weight: 700; display: flex; align-items: center; gap: 10px; }}
  h1 span {{ opacity: 0.5; font-size: 1rem; }}
  
  .controls {{ display: flex; gap: 12px; align-items: center; }}
  .refresh-badge {{
    background: var(--card);
    border: 1px solid var(--border);
    backdrop-filter: blur(8px);
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 0.75rem;
    color: var(--text-dim);
  }}

  .btn {{
    background: var(--accent);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .btn:hover {{ transform: translateY(-1px); filter: brightness(1.1); }}
  .btn:active {{ transform: translateY(0); }}
  .btn-secondary {{ background: var(--card); border: 1px solid var(--border); color: var(--text); }}

  /* ── Public URL Card ── */
  .endpoint-card {{
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(30, 41, 59, 0.7));
    border: 1px solid var(--accent);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    backdrop-filter: blur(12px);
  }}
  .endpoint-info label {{ font-size: 0.7rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; }}
  .endpoint-info .url {{ font-family: monospace; font-size: 1.1rem; color: var(--text); margin-top: 4px; display: block; }}

  /* ── Provider Section ── */
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(600px, 1fr)); gap: 24px; }}
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    backdrop-filter: blur(16px);
  }}

  .card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
  }}
  .provider-badge {{
    background: var(--accent);
    font-size: 0.75rem;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 6px;
    text-transform: uppercase;
  }}
  .health-stat {{ font-size: 0.87rem; color: var(--text-dim); }}

  /* ── Tables ── */
  table {{ width: 100%; border-collapse: collapse; font-size: 0.87rem; }}
  th {{ text-align: left; padding: 12px; color: var(--text-dim); font-weight: 500; border-bottom: 1px solid var(--border); }}
  td {{ padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.05); }}
  
  .badge {{
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
  }}
  .badge-HEALTHY {{ background: rgba(16, 185, 129, 0.2); color: var(--success); }}
  .badge-RATE_LIMITED {{ background: rgba(245, 158, 11, 0.2); color: var(--warning); }}
  .badge-SPENT, .badge-DEAD {{ background: rgba(239, 68, 68, 0.2); color: var(--error); }}

  /* ── History Scroll ── */
  .history-container {{
    margin-top: 24px;
    max-height: 300px;
    overflow-y: auto;
    border-top: 1px solid var(--border);
    padding-top: 16px;
  }}
  .history-item {{
    display: flex;
    gap: 12px;
    font-size: 0.75rem;
    padding: 6px 12px;
    border-radius: 6px;
    margin-bottom: 4px;
  }}
  .history-item:hover {{ background: rgba(255,255,255,0.02); }}
  .time {{ color: var(--text-dim); min-width: 60px; }}
  .event-status-OK {{ color: var(--success); font-weight: 600; }}
  .event-status-FAIL {{ color: var(--error); font-weight: 600; }}

  #toast {{
    position: fixed; bottom: 32px; left: 50%; transform: translateX(-50%);
    background: #1f2937; border: 1px solid #374151;
    color: white; padding: 12px 24px; border-radius: 12px;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
    opacity: 0; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    pointer-events: none; z-index: 1000;
  }}
  #toast.show {{ opacity: 1; transform: translateX(-50%) translateY(-10px); }}

  ::-webkit-scrollbar {{ width: 6px; }}
  ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 10px; }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>🔑 KeyRotator <span>/ teaching-monster v0.5.0</span></h1>
    <p style="font-size: 0.82rem; color: var(--text-dim); margin-top: 4px;">Dynamic API Quota Orchestration</p>
    <div id="contest-mode" style="margin-top: 8px; font-size: 0.9rem; font-weight: 600;"></div>
  </div>
  <div class="controls">
    <div class="refresh-badge" id="refresh-label">Next scan: 10s</div>
    <button class="btn" onclick="triggerPulse()">⚡ Pulse Test</button>
  </div>
</div>

<div class="endpoint-card">
  <div class="endpoint-info">
    <label>Public Ngrok API Endpoint</label>
    <span class="url" id="public-url">Detecting tunnel...</span>
  </div>
  <button class="btn btn-secondary" onclick="copyUrl()">Copy URL</button>
</div>

<div id="grid" class="grid"></div>

<div id="toast"></div>

<script>
let lastData = {initial_json};
const REFRESH_INTERVAL = 10;
let countdown = REFRESH_INTERVAL;

function render() {{
  const grid = document.getElementById("grid");
  const urlEl = document.getElementById("public-url");
  const contestEl = document.getElementById("contest-mode");

  if (lastData.contest_mode) {{
    contestEl.innerHTML = '<span style="color: #f59e0b;">🏆 CONTEST MODE ACTIVE</span> — Parallel processing enabled';
  }} else {{
    contestEl.innerHTML = '<span style="color: var(--text-dim);">🔧 DEV MODE</span> — Sequential processing';
  }}

  if (lastData.public_url) {{
    urlEl.textContent = lastData.public_url;
  }} else {{
    urlEl.textContent = "No active tunnel found";
    urlEl.style.color = "var(--error)";
  }}

  grid.innerHTML = lastData.pools.map(pool => {{
    const contestBadge = pool.is_contest_mode ? '<div class="badge" style="background:#f59e0b; color:#1e1b4b; margin-left:8px;">🏆 CONTEST</div>' : '';
    
    const rows = pool.keys.map(k => `
      <tr>
        <td style="color:var(--text-dim)">${{k.alias}}</td>
        <td><span class="badge badge-${{k.state}}">${{k.state.replace('_', ' ')}}</span></td>
        <td style="font-family:monospace; color:var(--warning)">${{k.ttl_seconds !== null ? k.ttl_seconds + 's' : '—'}}</td>
        <td>
           <div style="font-size:0.7rem; margin-bottom:4px; display:flex; justify-content:space-between">
             <span>RPM</span><span>${{k.rpm_current}}/${{k.rpm_limit}}</span>
           </div>
           <div style="height:4px; background:rgba(0,0,0,0.3); border-radius:2px; overflow:hidden">
             <div style="height:100%; width:${{Math.min(100, (k.rpm_current/k.rpm_limit)*100)}}%; background:${{k.rpm_current > k.rpm_limit * 0.8 ? 'var(--error)' : 'var(--success)'}}"></div>
           </div>
        </td>
        <td style="text-align:right">
          ${{k.state === 'SPENT' || k.state === 'DEAD' ? `<button class="btn btn-secondary" style="padding:4px 8px; font-size:0.65rem" onclick="revive('${{pool.provider}}', ${{k.index}})">Revive</button>` : '—'}}
        </td>
      </tr>
    `).join('');

    const historyHtml = pool.history.map(h => `
      <div class="history-item">
        <span class="time">${{h.time}}</span>
        <span class="badge" style="background:rgba(255,255,255,0.1); font-size:0.6rem; min-width:80px; text-align:center">${{h.alias}}</span>
        <span class="event-status-${{h.status}}">${{h.event}}</span>
        <span style="color:var(--text-dim); flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis">${{h.msg || ''}}</span>
      </div>
    `).join('');

    return `
      <div class="card">
        <div class="card-header">
          <div style="display:flex; align-items:center">
            <span class="provider-badge">${{pool.provider}}</span>
            ${{contestBadge}}
          </div>
          <span class="health-stat">${{pool.healthy_keys}}healthy / ${{pool.total_keys}} keys</span>
        </div>
        
        <div style="margin-bottom:20px;">
          <div style="height:8px; background:rgba(0,0,0,0.3); border-radius:4px; overflow:hidden">
            <div style="height:100%; width:${{pool.health_pct}}%; background:var(--accent); transition: width 0.5s ease;"></div>
          </div>
          <div style="font-size:0.75rem; color:var(--text-dim); margin-top:6px;">Overall Health: ${{pool.health_pct}}%</div>
        </div>

        <table>
          <thead><tr><th>Key</th><th>Status</th><th>TTL</th><th>Capacity</th><th style="text-align:right">Action</th></tr></thead>
          <tbody>${{rows}}</tbody>
        </table>

        <div class="history-container">
          <div style="font-size:0.75rem; font-weight:600; color:var(--text-dim); margin-bottom:12px; text-transform:uppercase; letter-spacing:0.04em">Live Activity Log</div>
          ${{historyHtml || '<div style="font-size:0.7rem; color:var(--text-dim)">No recent activity...</div>'}}
        </div>
      </div>
    `;
  }}).join('');
}}

async function refresh() {{
  try {{
    const r = await fetch("/dev/pool-status");
    lastData = await r.json();
    render();
    countdown = REFRESH_INTERVAL;
  }} catch(e) {{ console.error(e); }}
}}

async function revive(provider, index) {{
  try {{
    await fetch("/dev/pool-status/revive", {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{provider, key_index: index}})
    }});
    showToast(`Revived ${{provider}} key #${{index + 1}}`);
    refresh();
  }} catch(e) {{ showToast("Failed to revive"); }}
}}

async function triggerPulse() {{
  showToast("Sending Pulse request...");
  try {{
    const r = await fetch("/generate", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ 
        course_requirement: "Self-Diagnosis Pulse", 
        student_persona: "System Health Bot",
        model_override: "models/gemini-2.0-flash" 
      }})
    }});
    if (r.ok) showToast("✅ Pulse Received! Activity log will update.");
    else showToast("❌ Pulse failed (see activity log)");
    refresh();
  }} catch(e) {{ showToast("Connection error"); }}
}}

function copyUrl() {{
  const url = document.getElementById("public-url").textContent;
  navigator.clipboard.writeText(url);
  showToast("URL Copied to clipboard!");
}}

function showToast(msg) {{
  const t = document.getElementById("toast");
  t.textContent = msg; t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 3000);
}}

setInterval(() => {{
  countdown--;
  document.getElementById("refresh-label").textContent = `Next scan: ${{countdown}}s`;
  if (countdown <= 0) refresh();
}}, 1000);

render();
</script>
</body>
</html>"""
