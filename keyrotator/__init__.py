"""
keyrotator — Plug-and-play API key rotation for FastAPI projects.

Usage:
    from keyrotator import KeyPool, KeyRotatorRouter, AllKeysExhaustedError

    gemini_pool  = KeyPool("gemini",     keys=["key1", "key2", ...])
    router_pool  = KeyPool("openrouter", keys=["sk-or-...", ...])

    app.include_router(
        KeyRotatorRouter([gemini_pool, router_pool]),
        prefix="/dev"
    )
"""
from keyrotator.pool import KeyPool, KeyEntry, KeyState, AllKeysExhaustedError
from keyrotator.router import KeyRotatorRouter

__all__ = ["KeyPool", "KeyEntry", "KeyState", "AllKeysExhaustedError", "KeyRotatorRouter"]
