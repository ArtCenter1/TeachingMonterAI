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

# Global rate limit state for LLM calls (15 RPM max = 1 call per ~4 seconds)
global_llm_lock = asyncio.Lock()
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
        self.gemini_last_resort = "models/gemini-2.0-flash"

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
        """
        # Map model_size to preferred models (use OpenRouter for speed in dev mode)
        size_to_models = {
            "small": [
                "openrouter/google/gemma-3-12b-it:free",
                "openrouter/meta-llama/llama-3.2-3b-instruct:free",
                "kilo/nvidia/nemotron-3-super-120b-a12b:free",
                "models/gemini-1.5-flash",
            ],
            "medium": [
                "openrouter/meta-llama/llama-3.3-70b-instruct:free",
                "openrouter/google/gemma-3-27b-it:free",
                "kilo/nvidia/nemotron-3-super-120b-a12b:free",
                "models/gemini-1.5-pro",
            ],
            "large": [
                "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
                "openrouter/meta-llama/llama-3.3-70b-instruct:free",
                "kilo/nvidia/nemotron-3-super-120b-a12b:free",
                "models/gemini-2.0-flash-exp",
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

        # Hard-coded absolute fallback (using versioned name for stability)
        if self.gemini_last_resort not in models_to_try:
            models_to_try.append(self.gemini_last_resort)

        last_exception = None
        for model in models_to_try:
            try:
                logger.info(f"LLMClient: Attempting generation with {model}")
                return await self._execute_request(
                    model, prompt, system_instruction, temperature, max_tokens
                )
            except Exception as e:
                last_exception = e
                if "404" in str(e) or "NOT_FOUND" in str(e).upper() or "400" in str(e):
                    logger.error(
                        f"Model '{model}' failure (404/400). Initiating resilience recovery..."
                    )
                    self._avoid_models[model] = time.time() + 300  # Avoid for 5 mins

                    try:
                        # Only attempt Gemini resilience if keys are available
                        gemini_available = any(k.state in [KeyState.HEALTHY, KeyState.RATE_LIMITED] for k in self.gemini_pool._entries)
                        
                        if gemini_available:
                            # 1. Refresh discovery if stale (> 1 hour) or never run
                            if not self._discovered_models or (
                                time.time() - self._last_discovery_time > 3600
                            ):
                                logger.info("Refreshing Gemini model list...")
                                client = genai.Client(api_key=self.google_api_key)
                                self._discovered_models = [
                                    m.name for m in client.models.list()
                                ]
                                self._last_discovery_time = time.time()

                            # 2. Pick the best healthy candidate we haven't tried or blacklisted
                            candidates = [
                                m
                                for m in self._discovered_models
                                if m not in models_to_try and m not in self._avoid_models
                            ]

                            # Preference: gemini-2.0-flash > gemini-1.5-flash > anything discovery saw
                            new_fallback = None
                            if candidates:
                                for pref in ["2.0-flash", "2.5-flash", "1.5-flash"]:
                                    match = next((m for m in candidates if pref in m), None)
                                    if match:
                                        new_fallback = match
                                        break
                                if not new_fallback:
                                    new_fallback = candidates[0]

                            if new_fallback:
                                logger.info(
                                    f"Resilience: Falling back to auto-discovered healthy model: {new_fallback}"
                                )
                                return await self._execute_request(
                                    new_fallback,
                                    prompt,
                                    system_instruction,
                                    temperature,
                                    max_tokens,
                                )
                    except Exception as inner_e:
                        logger.error(f"Resilience recovery failed: {inner_e}")

                logger.warning(f"Model {model} failed: {str(e)}")
                # Universal backoff before trying the next model to prevent rapid key burning
                await asyncio.sleep(2)
                continue

        logger.error(f"All models failed for prompt. Last error: {str(last_exception)}")
        raise last_exception

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
        3. OpenRouter: Any model name explicitly asking for :free, :nitro, etc.
           OR non-Google providers (anthropic/, qwen/, etc.)
        4. Gemini SDK: Direct names, models/ names, or google/ names (without OR variants).
        """
        is_kilo = model_name.startswith("kilo/")
        is_xai = model_name.startswith("xai/")
        is_explicit_openrouter = ":" in model_name
        is_google_native = model_name.startswith("models/") or model_name.startswith(
            "gemini-"
        )
        is_google_prefixed = (
            model_name.startswith("google/") and not is_explicit_openrouter
        )

        global global_last_llm_time
        async with global_llm_lock:
            now = time.time()
            elapsed = now - global_last_llm_time
            if elapsed < 4.2:
                # 4.2 seconds spacing between requests ensures we stay safely under 15 RPM
                await asyncio.sleep(4.2 - elapsed)
            global_last_llm_time = time.time()

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
            # OpenRouter path — strip openrouter/ prefix
            clean_name = model_name.replace("openrouter/", "")
            return await self._call_openrouter(
                clean_name, prompt, system_instruction, temperature, max_tokens
            )
        elif is_google_native or is_google_prefixed:
            # Native Gemini SDK path — ensure "models/" prefix
            clean_name = model_name
            if clean_name.startswith("google/"):
                clean_name = clean_name.replace("google/", "models/")
            if not clean_name.startswith("models/"):
                clean_name = f"models/{clean_name}"
            return await self._call_gemini_sdk(
                clean_name, prompt, system_instruction, temperature, max_tokens
            )
        else:
            # No prefix matched — try OpenRouter as ultimate fallback
            logger.warning(
                f"No matching model prefix for {model_name}, trying OpenRouter fallback"
            )
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
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except AllKeysExhaustedError as e:
            logger.error(f"[llm_client] {e}")
            raise RuntimeError(str(e))

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
            logger.error(f"[llm_client] {e}")
            raise RuntimeError(str(e))
