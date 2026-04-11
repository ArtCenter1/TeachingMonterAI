from __future__ import annotations
import json
import time
from typing import List
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from loguru import logger

from keyrotator.pool import KeyPool


class ReviveRequest(BaseModel):
    provider: str    # "gemini" or "openrouter"
    key_index: int   # 0-based index


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

    @router.get("/pool-status")
    async def get_pool_status():
        return {
            "pools":     [p.get_status() for p in pools],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    @router.post("/pool-status/revive")
    async def revive_key(body: ReviveRequest):
        pool = pool_map.get(body.provider)
        if pool is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Provider '{body.provider}' not found."}
            )
        success = pool.revive(body.key_index)
        if not success:
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid key index {body.key_index}"}
            )
        logger.info(f"[keyrotator] Revived {body.provider} key #{body.key_index} via dashboard")
        return {"ok": True, "message": f"Key #{body.key_index} revived for {body.provider}"}

    @router.get("/pool-status/ui", response_class=HTMLResponse)
    async def get_pool_status_ui():
        status_data = [p.get_status() for p in pools]
        status_json = json.dumps(status_data)
        html = _render_dashboard(status_json)
        return HTMLResponse(content=html)

    return router


def _render_dashboard(status_json: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>API Key Pool Status</title>
<style>
  /* ── Reset + Base ── */
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #0f1117;
    color: #e2e8f0;
    padding: 24px;
    min-height: 100vh;
  }}
  h1 {{ font-size: 1.4rem; font-weight: 700; margin-bottom: 4px; }}
  .subtitle {{ font-size: 0.8rem; color: #64748b; margin-bottom: 24px; }}
  .refresh-badge {{
    display: inline-block;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 0.75rem;
    color: #94a3b8;
    float: right;
  }}

  /* ── Provider Card ── */
  .provider-card {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
  }}
  .provider-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }}
  .provider-name {{
    font-size: 1rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #7c3aed;
  }}
  .health-summary {{ font-size: 0.82rem; color: #94a3b8; }}

  /* ── Health Bar ── */
  .health-bar-wrapper {{ margin-bottom: 16px; }}
  .health-bar-track {{
    background: #0f1117;
    border-radius: 999px;
    height: 10px;
    overflow: hidden;
    margin-bottom: 4px;
  }}
  .health-bar-fill {{
    height: 100%;
    border-radius: 999px;
    transition: width 0.5s ease;
  }}
  .health-bar-label {{ font-size: 0.75rem; color: #64748b; }}

  /* ── Key Table ── */
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{
    text-align: left;
    padding: 6px 10px;
    color: #64748b;
    border-bottom: 1px solid #334155;
    font-weight: 500;
  }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #1e293b; }}
  tr:last-child td {{ border-bottom: none; }}

  /* ── State Badges ── */
  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
  }}
  .badge-HEALTHY      {{ background: #14532d; color: #4ade80; }}
  .badge-RATE_LIMITED {{ background: #451a03; color: #fb923c; }}
  .badge-SPENT        {{ background: #450a0a; color: #f87171; }}
  .badge-DEAD         {{ background: #1c1917; color: #78716c; }}

  /* ── Revive Button ── */
  .revive-btn {{
    background: #312e81;
    color: #a5b4fc;
    border: 1px solid #4338ca;
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 0.72rem;
    cursor: pointer;
    transition: background 0.2s;
  }}
  .revive-btn:hover {{ background: #3730a3; }}
  .revive-btn:disabled {{ opacity: 0.4; cursor: not-allowed; }}

  /* ── Countdown chip ── */
  .ttl {{ color: #fb923c; font-size: 0.75rem; }}

  /* ── Toast ── */
  #toast {{
    position: fixed; bottom: 24px; right: 24px;
    background: #1e293b; border: 1px solid #334155;
    border-radius: 10px; padding: 12px 20px;
    font-size: 0.82rem; color: #e2e8f0;
    opacity: 0; transition: opacity 0.3s;
    pointer-events: none;
  }}
  #toast.show {{ opacity: 1; }}
</style>
</head>
<body>

<div>
  <span class="refresh-badge" id="refresh-label">Auto-refresh: 10s</span>
  <h1>🔑 API Key Pool Status</h1>
  <div class="subtitle">Teaching Monster AI — Development Key Rotator</div>
</div>

<div id="pools-container"></div>
<div id="toast"></div>

<script>
const INITIAL_DATA = {status_json};
const REFRESH_INTERVAL = 10;
let countdown = REFRESH_INTERVAL;

function healthColor(pct) {{
  if (pct >= 75) return "#4ade80";
  if (pct >= 40) return "#fb923c";
  return "#f87171";
}}

function renderPool(pool) {{
  const color = healthColor(pool.health_pct);
  const pct = pool.health_pct;
  const keysHtml = pool.keys.map(k => {{
    const stateLabel = k.state.replace("_", " ");
    const ttlHtml = k.ttl_seconds != null
      ? `<span class="ttl">${{k.ttl_seconds}}s</span>`
      : (k.state === "RATE_LIMITED" ? '<span class="ttl">expiring</span>' : "—");

    const canRevive = (k.state === "SPENT" || k.state === "DEAD");
    const reviveHtml = canRevive
      ? `<button class="revive-btn" onclick="revive('${{pool.provider}}', ${{k.index}}, this)">Revive</button>`
      : "—";

    return `<tr>
      <td style="color:#94a3b8">${{k.alias}}</td>
      <td><span class="badge badge-${{k.state}}">${{stateLabel}}</span></td>
      <td>${{ttlHtml}}</td>
      <td style="color:#4ade80">✓ ${{k.total_success}}</td>
      <td style="color:#f87171">✗ ${{k.total_fail}}</td>
      <td>${{reviveHtml}}</td>
    </tr>`;
  }}).join("");

  return `
  <div class="provider-card">
    <div class="provider-header">
      <div class="provider-name">${{pool.provider}}</div>
      <div class="health-summary">${{pool.healthy_keys}} / ${{pool.total_keys}} keys healthy</div>
    </div>
    <div class="health-bar-wrapper">
      <div class="health-bar-track">
        <div class="health-bar-fill" style="width:${{pct}}%; background:${{color}}"></div>
      </div>
      <div class="health-bar-label">${{pct}}% healthy</div>
    </div>
    <table>
      <thead>
        <tr>
          <th>Key</th><th>State</th><th>TTL</th><th>✓ OK</th><th>✗ Fail</th><th>Action</th>
        </tr>
      </thead>
      <tbody>${{keysHtml}}</tbody>
    </table>
  </div>`;
}}

function renderAll(data) {{
  document.getElementById("pools-container").innerHTML = data.map(renderPool).join("");
}}

async function revive(provider, keyIndex, btn) {{
  btn.disabled = true;
  try {{
    const resp = await fetch("/dev/pool-status/revive", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ provider, key_index: keyIndex }})
    }});
    const data = await resp.json();
    showToast(data.message || data.error || "Done");
    await refresh();
  }} catch(e) {{
    showToast("Error: " + e.message);
    btn.disabled = false;
  }}
}}

async function refresh() {{
  try {{
    const resp = await fetch("/dev/pool-status");
    const json = await resp.json();
    renderAll(json.pools);
    countdown = REFRESH_INTERVAL;
  }} catch(e) {{
    console.error("Refresh failed:", e);
  }}
}}

function showToast(msg) {{
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 3000);
}}

// Initial render
renderAll(INITIAL_DATA);

// Countdown + auto-refresh
setInterval(() => {{
  countdown--;
  document.getElementById("refresh-label").textContent = `Auto-refresh: ${{countdown}}s`;
  if (countdown <= 0) refresh();
}}, 1000);
</script>
</body>
</html>"""
