import os
import time
import asyncio
from typing import Optional, List, Dict, Any
from google import genai
from google.genai import types as genai_types
from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from loguru import logger

from keyrotator.pool import KeyPool, KeyState, AllKeysExhaustedError
from keyrotator.providers import gemini as gemini_provider
from keyrotator.providers import openrouter as openrouter_provider
from keyrotator.providers import xai as xai_provider
from keyrotator.providers import kilo as kilo_provider

# Per-pool rate limit locks — Gemini and OpenRouter have independent quotas.
# With 9 Gemini keys @ 15 RPM each = 135 RPM effective = 1 call per 0.44s.
# We stay conservative at 2.1s spacing per pool (not per key) to avoid burst issues.
# OpenRouter free tier: ~10 RPM per key = 90 RPM with 9 keys → 4.2s spacing.
global_gemini_lock = asyncio.Lock()
global_router_lock = asyncio.Lock()
global_last_gemini_time = 0.0
global_last_router_time = 0.0
# Legacy alias kept for any external references
global_llm_lock = global_gemini_lock
global_last_llm_time = 0.0


def _parse_pool(pool_env: str, single_key_env: str) -> list[str]:
    """
    Returns a list of keys from pool_env (comma-separated).
    Falls back to single_key_env if pool_env is not set or empty.
    """
    pool_raw = os.getenv(pool_env, "").strip()
    if pool_raw:
        return [k.strip() for k in pool_raw.split(",") if k.strip()]
    single = os.getenv(single_key_env, "").strip()
    return [single] if single else []


# Shared global pools to ensure unified state across the entire process
_gemini_pool: Optional[KeyPool] = None
_router_pool: Optional[KeyPool] = None
_xai_pool: Optional[KeyPool] = None
_kilo_pool: Optional[KeyPool] = None


def get_gemini_pool() -> KeyPool:
    global _gemini_pool
    if _gemini_pool is None:
        keys = _parse_pool("GOOGLE_API_KEY_POOL", "GOOGLE_API_KEY")
        _gemini_pool = KeyPool("gemini", keys)
    return _gemini_pool


def get_router_pool() -> KeyPool:
    global _router_pool
    if _router_pool is None:
        keys = _parse_pool("OPENROUTER_API_KEY_POOL", "OPENROUTER_API_KEY")
        _router_pool = KeyPool("openrouter", keys)
    return _router_pool


def get_xai_pool() -> KeyPool:
    global _xai_pool
    if _xai_pool is None:
        keys = _parse_pool("XAI_API_KEY_POOL", "XAI_API_KEY")
        _xai_pool = KeyPool("xai", keys)
    return _xai_pool


def get_kilo_pool() -> KeyPool:
    global _kilo_pool
    if _kilo_pool is None:
        keys = _parse_pool("KILO_API_KEY_POOL", "KILO_API_KEY")
        _kilo_pool = KeyPool("kilo", keys)
    return _kilo_pool


class LLMClient:
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

        # Primary & Fallback model names
        self.primary_model = os.getenv("PRIMARY_MODEL", "models/gemini-2.0-flash")
        self.fallback_model = os.getenv("FALLBACK_MODEL", "models/gemini-1.5-flash")
        # FIX: Last resort must be a live model — 1.5-flash is the most reliable free-tier option
        self.gemini_last_resort = "models/gemini-1.5-flash"

        # Use shared pools
        self.gemini_pool = get_gemini_pool()
        self.router_pool = get_router_pool()
        self.xai_pool = get_xai_pool()
        self.kilo_pool = get_kilo_pool()

        # Proactive discovery cache
        self._discovered_models = []
        self._last_discovery_time = 0
        self._avoid_models = {}  # model_name -> expiration_timestamp

        logger.info(
            f"LLMClient ready (Shared State) | gemini: {len(self.gemini_pool._entries)} keys "
            f"| openrouter: {len(self.router_pool._entries)} keys "
            f"| xai: {len(self.xai_pool._entries)} keys"
        )

    def _gemini_pool_has_capacity(self) -> bool:
        """Returns True if at least one Gemini key is HEALTHY or will recover soon (RATE_LIMITED)."""
        now = time.time()
        for entry in self.gemini_pool._entries:
            if entry.state == KeyState.HEALTHY:
                return True
            if (entry.state == KeyState.RATE_LIMITED
                    and entry.quarantine_until is not None
                    and now >= entry.quarantine_until):
                # This key will auto-recover on next get_key() call
                return True
        return False

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model_override: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model_size: str = "large",  # "small", "medium", "large"
    ) -> str:
        """
        Unified generation method with multi-stage fallback.

        Priority order:
          1. model_override (if provided)
          2. size_to_models[model_size] — OpenRouter first, then Gemini as last entry
          3. primary_model from .env (if not already in the list)
          4. fallback_model from .env (if not already in the list)
          5. gemini_last_resort (hardcoded gemini-1.5-flash as final safety net)

        The key insight: each model is tried sequentially. When an OpenRouter model
        raises AllKeysExhaustedError OR any other exception, we move to the NEXT
        model in the list, which will eventually be a Gemini model.
        """
        # Map model_size to preferred models — Gemini is ALWAYS the last entry per tier
        # so it serves as the automatic fallback when all OpenRouter models fail.
        size_to_models = {
            "small": [
                "openrouter/google/gemma-3-12b-it:free",
                "openrouter/meta-llama/llama-3.2-3b-instruct:free",
                "kilo/nvidia/nemotron-3-super-120b-a12b:free",
                "models/gemini-2.0-flash",   # gemini-1.5-flash is 404 on v1beta
            ],
            "medium": [
                "openrouter/meta-llama/llama-3.3-70b-instruct:free",
                "openrouter/google/gemma-3-27b-it:free",
                "kilo/nvidia/nemotron-3-super-120b-a12b:free",
                "models/gemini-2.0-flash",
            ],
            "large": [
                "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
                "openrouter/meta-llama/llama-3.3-70b-instruct:free",
                "kilo/nvidia/nemotron-3-super-120b-a12b:free",
                "models/gemini-2.0-flash",
            ],
        }

        models_to_try = []
        if model_override:
            models_to_try.append(model_override)
        else:
            # Use size-based models first
            preferred = size_to_models.get(model_size, size_to_models["large"])
            models_to_try.extend(preferred)

        # Add configured primary/fallback if not already included
        if self.primary_model not in models_to_try:
            models_to_try.append(self.primary_model)

        if self.fallback_model not in models_to_try:
            models_to_try.append(self.fallback_model)

        # Hard-coded absolute last resort — gemini-1.5-flash
        if self.gemini_last_resort not in models_to_try:
            models_to_try.append(self.gemini_last_resort)

        logger.info(f"LLMClient: model chain for size='{model_size}': {models_to_try}")

        last_exception = None
        for model in models_to_try:
            try:
                logger.info(f"LLMClient: Attempting generation with {model}")
                result = await self._execute_request(
                    model, prompt, system_instruction, temperature, max_tokens
                )
                logger.success(f"LLMClient: Success with {model}")
                return result

            except Exception as e:
                last_exception = e
                err_str = str(e)
                logger.warning(f"Model {model} failed: {err_str[:200]}")

                # ── Resilience Recovery (only for 404/NOT_FOUND on Gemini models) ──
                if ("404" in err_str or "NOT_FOUND" in err_str.upper() or "400" in err_str):
                    logger.error(
                        f"Model '{model}' failure (404/400). Adding to avoid list for 5min."
                    )
                    self._avoid_models[model] = time.time() + 300  # Avoid for 5 mins

                    # Only attempt discovery-based resilience if Gemini pool has capacity
                    if self._gemini_pool_has_capacity():
                        try:
                            # Refresh model list if stale (> 1 hour) or never run
                            if not self._discovered_models or (
                                time.time() - self._last_discovery_time > 3600
                            ):
                                logger.info("Refreshing Gemini model list via discovery...")
                                # Use pool key for discovery to avoid burning primary key
                                pool_entry = self.gemini_pool.get_key()
                                discovery_key = (
                                    pool_entry.key if pool_entry else self.google_api_key
                                )
                                client = genai.Client(api_key=discovery_key)
                                self._discovered_models = [
                                    m.name for m in client.models.list()
                                ]
                                self._last_discovery_time = time.time()
                                logger.info(
                                    f"Discovered {len(self._discovered_models)} Gemini models"
                                )

                            # Pick the best healthy candidate not already in our list
                            candidates = [
                                m
                                for m in self._discovered_models
                                if m not in models_to_try 
                                and m not in self._avoid_models
                                and "tts" not in m.lower()
                                and "audio" not in m.lower()
                            ]

                            # Preference: gemini-2.0-flash > gemini-1.5-flash > anything else
                            new_fallback = None
                            if candidates:
                                for pref in ["2.0-flash", "1.5-flash"]:
                                    match = next((m for m in candidates if pref in m), None)
                                    if match:
                                        new_fallback = match
                                        break
                                if not new_fallback:
                                    new_fallback = candidates[0]

                            if new_fallback:
                                logger.info(
                                    f"Resilience: Falling back to auto-discovered model: {new_fallback}"
                                )
                                try:
                                    result = await self._execute_request(
                                        new_fallback,
                                        prompt,
                                        system_instruction,
                                        temperature,
                                        max_tokens,
                                    )
                                    logger.success(
                                        f"Resilience recovery succeeded with {new_fallback}"
                                    )
                                    return result
                                except Exception as recovery_e:
                                    logger.error(
                                        f"Resilience recovery model {new_fallback} also failed: {recovery_e}"
                                    )
                        except Exception as inner_e:
                            logger.error(f"Resilience recovery setup failed: {inner_e}")

                # ── Pool exhaustion: skip remaining OpenRouter models, jump to Gemini ──
                if "exhausted" in err_str.lower() or "all" in err_str.lower() and "keys" in err_str.lower():
                    logger.warning(
                        f"Pool exhaustion detected for {model}. "
                        "Skipping remaining same-provider models in this chain."
                    )
                    # Check if we should skip ahead to the first Gemini model
                    is_openrouter = model.startswith("openrouter/") or ":" in model
                    if is_openrouter:
                        # Find the first non-OpenRouter model in remaining chain and jump to it
                        remaining = models_to_try[models_to_try.index(model) + 1:]
                        gemini_fallback = next(
                            (m for m in remaining if m.startswith("models/") or m.startswith("gemini-")),
                            None,
                        )
                        if gemini_fallback:
                            logger.info(
                                f"Pool exhaustion: jumping directly to Gemini fallback: {gemini_fallback}"
                            )
                            try:
                                result = await self._execute_request(
                                    gemini_fallback, prompt, system_instruction, temperature, max_tokens
                                )
                                logger.success(
                                    f"Gemini fallback succeeded with {gemini_fallback}"
                                )
                                return result
                            except Exception as gfb_e:
                                logger.error(
                                    f"Gemini fallback {gemini_fallback} also failed: {gfb_e}"
                                )
                                last_exception = gfb_e
                                break  # No point continuing the loop — Gemini itself failed

                # Small backoff before trying the next model to prevent rapid key burning
                await asyncio.sleep(1)
                continue

        logger.error(f"All models failed for prompt. Last error: {str(last_exception)}")
        raise last_exception

    async def generate_multimodal(
        self,
        contents: List[Any],
        system_instruction: Optional[str] = None,
        model_override: Optional[str] = "models/gemini-2.0-flash",
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """
        Multimodal generation (e.g. for audio transcription/analysis).
        Currently only supported via Gemini native path.
        """
        # Ensure we use a Gemini model
        model = model_override or "models/gemini-2.0-flash"
        if not (model.startswith("models/") or model.startswith("gemini-")):
             model = "models/gemini-2.0-flash"
             
        logger.info(f"LLMClient: Multimodal request with {model}")
        
        # Space the request
        async with global_gemini_lock:
            now = time.time()
            elapsed = now - global_last_gemini_time
            if elapsed < 2.1:
                await asyncio.sleep(2.1 - elapsed)
            global_last_gemini_time = time.time()

        return await self._call_gemini_sdk(
            model, contents, system_instruction, temperature, max_tokens
        )

    async def _execute_request(
        self,
        model_name: str,
        prompt: str,
        system_instruction: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        Routing Rules:
        1. Kilo Gateway: kilo/ prefixed models (uses Kilo API key)
        2. xAI: xai/ prefixed models (uses direct xAI API key)
        3. OpenRouter: Any model name with ':' variant suffix (e.g. :free, :nitro)
           OR explicitly prefixed with openrouter/
        4. Gemini SDK: Direct names, models/ names, or gemini- names.
        """
        is_kilo = model_name.startswith("kilo/")
        is_xai = model_name.startswith("xai/")
        is_explicit_openrouter = model_name.startswith("openrouter/") or (
            ":" in model_name and not model_name.startswith("models/")
        )
        is_google_native = model_name.startswith("models/") or model_name.startswith(
            "gemini-"
        )
        is_google_prefixed = (
            model_name.startswith("google/") and not is_explicit_openrouter
        )

        global global_last_gemini_time, global_last_router_time

        if is_kilo:
            # Kilo Gateway path — strip kilo/ prefix
            clean_name = model_name.replace("kilo/", "")
            return await self._call_kilo_sdk(
                clean_name, prompt, system_instruction, temperature, max_tokens
            )
        elif is_xai:
            # xAI API path — strip xai/ prefix
            clean_name = model_name.replace("xai/", "")
            return await self._call_xai_sdk(
                clean_name, prompt, system_instruction, temperature, max_tokens
            )
        elif is_explicit_openrouter:
            # OpenRouter path — uses its own lock so Gemini calls don't block
            async with global_router_lock:
                now = time.time()
                elapsed = now - global_last_router_time
                if elapsed < 4.2:
                    await asyncio.sleep(4.2 - elapsed)
                global_last_router_time = time.time()
            clean_name = model_name.replace("openrouter/", "")
            return await self._call_openrouter(
                clean_name, prompt, system_instruction, temperature, max_tokens
            )
        elif is_google_native or is_google_prefixed:
            # Gemini path — uses its own lock, 2.1s spacing (safe with 9-key pool)
            async with global_gemini_lock:
                now = time.time()
                elapsed = now - global_last_gemini_time
                if elapsed < 2.1:
                    await asyncio.sleep(2.1 - elapsed)
                global_last_gemini_time = time.time()
            clean_name = model_name
            if clean_name.startswith("google/"):
                clean_name = clean_name.replace("google/", "models/")
            if not clean_name.startswith("models/"):
                clean_name = f"models/{clean_name}"
            return await self._call_gemini_sdk(
                clean_name, prompt, system_instruction, temperature, max_tokens
            )
        else:
            # No prefix matched — treat as OpenRouter
            logger.warning(
                f"No matching model prefix for {model_name}, trying OpenRouter fallback"
            )
            async with global_router_lock:
                now = time.time()
                elapsed = now - global_last_router_time
                if elapsed < 4.2:
                    await asyncio.sleep(4.2 - elapsed)
                global_last_router_time = time.time()
            return await self._call_openrouter(
                model_name, prompt, system_instruction, temperature, max_tokens
            )

    async def _call_gemini_sdk(
        self,
        model_name: str,
        prompt: str,
        system_instruction: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Calls Gemini via rotating key pool."""
        try:
            return await gemini_provider.call_with_pool(
                pool=self.gemini_pool,
                model_name=model_name,
                contents=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except AllKeysExhaustedError as e:
            logger.error(f"[llm_client] Gemini pool exhausted: {e}")
            raise RuntimeError(f"All Gemini keys in pool are exhausted. Check /dev/pool-status/ui for details.")

    async def _call_xai_sdk(
        self,
        model_name: str,
        prompt: str,
        system_instruction: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Calls xAI via rotating key pool."""
        try:
            return await xai_provider.call_with_pool(
                pool=self.xai_pool,
                model_name=model_name,
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except AllKeysExhaustedError as e:
            logger.error(f"[llm_client] {e}")
            raise RuntimeError(str(e))

    async def _call_kilo_sdk(
        self,
        model_name: str,
        prompt: str,
        system_instruction: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Calls Kilo Gateway via rotating key pool."""
        try:
            return await kilo_provider.call_with_pool(
                pool=self.kilo_pool,
                model_name=model_name,
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except AllKeysExhaustedError as e:
            logger.error(f"[llm_client] {e}")
            raise RuntimeError(str(e))

    async def _call_openrouter(
        self,
        model_name: str,
        prompt: str,
        system_instruction: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Calls OpenRouter via rotating key pool."""
        try:
            return await openrouter_provider.call_with_pool(
                pool=self.router_pool,
                model_name=model_name,
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except AllKeysExhaustedError as e:
            logger.error(f"[llm_client] OpenRouter pool exhausted: {e}")
            raise RuntimeError(f"All OpenRouter keys exhausted — falling through to Gemini pool.")
