"""
modules/mcp_client.py
─────────────────────
OpenSpace MCP Streamable HTTP client for TeachingMonsterAI.

Protocol (confirmed from live probe of openspace-evolution-engine container):
 • POST /mcp  Accept: application/json, text/event-stream
   → Response header: Mcp-Session-Id: <id>
   → Response body:   event: message\\ndata: {json-rpc-payload}
 • All subsequent calls: POST /mcp + Mcp-Session-Id header
 • Notification (fire-and-forget): POST without expecting a data response

Available tools (as of 2026-04-11, OpenSpace v1.27.0):
  execute_task  search_skills  fix_skill  upload_skill
"""

import json
import logging
import os
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

# Container-to-container URL when both services run in the same Docker network.
# Override with OPENSPACE_MCP_URL=http://localhost:8888/mcp for host-side testing.
_DEFAULT_MCP_URL = "http://openspace-evolution-engine:8081/mcp"
OPENSPACE_MCP_URL = os.getenv("OPENSPACE_MCP_URL", _DEFAULT_MCP_URL)

_POST_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Host": "localhost:8081",
}


def _parse_sse_data(text: str) -> dict:
    """
    Extract the JSON payload from an SSE response body.

    The engine returns:
        event: message\\r\\n
        data: {…json…}\\r\\n
        \\r\\n
    """
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            try:
                return json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ValueError(f"SSE data line is not valid JSON: {payload!r}") from exc
    raise ValueError(f"No 'data:' line found in SSE response:\\n{text[:400]}")


class OpenSpaceMCPClient:
    """
    Async client for the OpenSpace MCP Streamable HTTP transport.

    Usage
    -----
    Each public method opens its own aiohttp session and manages a fresh
    MCP session (initialize → use → done). This keeps the client stateless
    and safe for concurrent pipeline calls.

    Example
    -------
    >>> client = OpenSpaceMCPClient()
    >>> reachable = await client.health_check()
    >>> result = await client.execute_task("Research Newton's Laws …")
    """

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or OPENSPACE_MCP_URL

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _post(
        self,
        session: aiohttp.ClientSession,
        payload: dict,
        session_id: str | None = None,
        timeout: float = 30.0,
    ) -> tuple[dict | None, str | None]:
        """
        POST a JSON-RPC 2.0 payload to /mcp.

        Returns (parsed_data, Mcp-Session-Id).
        For notification calls (no 'id' in payload) the response body may be
        empty; we return (None, session_id) in that case.
        """
        headers = dict(_POST_HEADERS)
        if session_id:
            headers["Mcp-Session-Id"] = session_id

        async with session.post(
            self.base_url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            resp.raise_for_status()
            new_sid = resp.headers.get("Mcp-Session-Id", session_id)
            text = await resp.text()

        if not text.strip():
            return None, new_sid

        try:
            data = _parse_sse_data(text)
        except ValueError:
            # Some transports return plain JSON on notifications
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                return None, new_sid

        if "error" in data:
            err = data["error"]
            raise RuntimeError(
                f"OpenSpace JSON-RPC error {err.get('code')}: {err.get('message')}"
            )
        return data, new_sid

    async def _init_session(self, session: aiohttp.ClientSession) -> str:
        """
        Perform the MCP handshake and return the session ID.

        Steps:
          1. POST initialize  → server returns capabilities + Mcp-Session-Id
          2. POST notifications/initialized  (fire-and-forget)
        """
        data, sid = await self._post(
            session,
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "TeachingMonsterAI",
                        "version": "0.3.0",
                    },
                },
            },
        )
        if not sid:
            raise RuntimeError("OpenSpace did not return a session ID")

        # Fire-and-forget notification — ignore response body
        await self._post(
            session,
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            session_id=sid,
        )
        logger.debug("OpenSpace session initialised: %s", sid)
        return sid

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Return True if the OpenSpace engine is reachable and accepts sessions."""
        try:
            async with aiohttp.ClientSession() as session:
                sid = await self._init_session(session)
                return bool(sid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenSpace health check failed: %s", exc)
            return False

    async def list_tools(self) -> list[str]:
        """Return the names of all tools exposed by the OpenSpace engine."""
        async with aiohttp.ClientSession() as session:
            sid = await self._init_session(session)
            data, _ = await self._post(
                session,
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                session_id=sid,
            )
        tools = data.get("result", {}).get("tools", []) if data else []
        return [t["name"] for t in tools]

    async def execute_task(
        self,
        task: str,
        max_iterations: int = 20,
        search_scope: str = "local",
    ) -> str:
        """
        Delegate a task to OpenSpace's full grounding engine.

        OpenSpace will:
          • Search local skill registry (and cloud if search_scope="all")
          • Auto-discover and invoke matching skills (e.g. notebooklm, pedagogical_critic)
          • Return the result as plain text

        Parameters
        ----------
        task : str
            Natural-language task description.
        max_iterations : int
            Maximum agent iterations (default 20).  Use 5–10 for critic tasks,
            10–20 for sourcing tasks.  Per OpenSpace docs, caller timeout ≥ 600s.
        search_scope : str
            "local"  — local SkillRegistry only (faster, no cloud API key needed).
            "all"    — local + cloud community skills.

        Returns
        -------
        str
            The concatenated text content from all result content blocks.

        Raises
        ------
        RuntimeError
            If OpenSpace returns a JSON-RPC error.
        """
        async with aiohttp.ClientSession() as session:
            sid = await self._init_session(session)
            data, _ = await self._post(
                session,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "execute_task",
                        "arguments": {
                            "task": task,
                            "max_iterations": max_iterations,
                            "search_scope": search_scope,
                        },
                    },
                },
                session_id=sid,
                timeout=600.0,  # OpenSpace docs recommend ≥ 600s timeout
            )

        result = data.get("result", {}) if data else {}
        contents = result.get("content", [])
        text_parts = [c["text"] for c in contents if c.get("type") == "text" and c.get("text")]
        return "\n".join(text_parts)

    async def search_skills(self, query: str, limit: int = 10) -> list[dict]:
        """
        Search the OpenSpace skill registry (local + cloud).

        Returns a list of skill dicts with keys: name, description, source.
        """
        async with aiohttp.ClientSession() as session:
            sid = await self._init_session(session)
            data, _ = await self._post(
                session,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "search_skills",
                        "arguments": {
                            "query": query,
                            "limit": limit,
                            "source": "local",
                        },
                    },
                },
                session_id=sid,
                timeout=30.0,
            )
        result = data.get("result", {}) if data else {}
        contents = result.get("content", [])
        # OpenSpace returns skills as text; try to parse as JSON
        for c in contents:
            if c.get("type") == "text":
                try:
                    return json.loads(c["text"])
                except (json.JSONDecodeError, TypeError):
                    pass
        return []
