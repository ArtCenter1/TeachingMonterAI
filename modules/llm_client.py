import os
import time
import asyncio
from typing import Optional, List, Dict, Any
from google import genai
from google.genai import types as genai_types
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger

from keyrotator.pool import KeyPool, AllKeysExhaustedError
from keyrotator.providers import gemini as gemini_provider
from keyrotator.providers import openrouter as openrouter_provider

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

class LLMClient:
    def __init__(self):
        self.google_api_key   = os.getenv("GOOGLE_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

        # Primary & Fallback model names (unchanged)
        self.primary_model    = os.getenv("PRIMARY_MODEL", "google/gemini-2.0-flash-exp:free")
        self.fallback_model   = os.getenv("FALLBACK_MODEL", "qwen/qwen-2.5-7b-instruct:free")
        self.gemini_last_resort = "models/gemini-2.0-flash"

        # Build key pools (auto-falls-back to single key if pool env not set)
        gemini_keys = _parse_pool("GOOGLE_API_KEY_POOL", "GOOGLE_API_KEY")
        router_keys = _parse_pool("OPENROUTER_API_KEY_POOL", "OPENROUTER_API_KEY")

        self.gemini_pool  = KeyPool("gemini", gemini_keys)
        self.router_pool  = KeyPool("openrouter", router_keys)

        # Keep legacy single clients for backward compat (used nowhere after this change)
        self.gemini_client = None
        self.openrouter_client = None

        logger.info(
            f"LLMClient ready | gemini pool: {len(gemini_keys)} keys "
            f"| openrouter pool: {len(router_keys)} keys"
        )

    async def generate_text(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None,
        model_override: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """
        Unified generation method with multi-stage fallback.
        """
        models_to_try = []
        if model_override:
            models_to_try.append(model_override)
        
        if self.primary_model not in models_to_try:
            models_to_try.append(self.primary_model)
            
        if self.fallback_model not in models_to_try:
            models_to_try.append(self.fallback_model)
            
        # Hard-coded absolute fallback
        if "gemini-1.5-flash" not in models_to_try:
            models_to_try.append("gemini-1.5-flash")

        last_exception = None
        for model in models_to_try:
            try:
                logger.info(f"LLMClient: Attempting generation with {model}")
                return await self._execute_request(model, prompt, system_instruction, temperature, max_tokens)
            except Exception as e:
                last_exception = e
                logger.warning(f"Model {model} failed: {str(e)}")
                # If it's a 429 (Rate Limit) on OpenRouter, wait a bit
                if "429" in str(e) and "openrouter" in str(e).lower():
                    await asyncio.sleep(2)
                continue
                
        logger.error(f"All models failed for prompt. Last error: {str(last_exception)}")
        raise last_exception

        # Routing Rules:
        # 1. OpenRouter: Any model name explicitly asking for :free, :nitro, etc.
        #    OR non-Google providers (anthropic/, qwen/, etc.)
        # 2. Gemini SDK: Direct names, models/ names, or google/ names (without OR variants).
        
        is_explicit_openrouter = ":" in model_name
        is_google_native = model_name.startswith("models/") or model_name.startswith("gemini-")
        is_google_prefixed = model_name.startswith("google/") and not is_explicit_openrouter
        
        if is_google_native or is_google_prefixed:
            # Native Gemini SDK path — ensure "models/" prefix
            clean_name = model_name
            if clean_name.startswith("google/"):
                clean_name = clean_name.replace("google/", "models/")
            if not clean_name.startswith("models/"):
                clean_name = f"models/{clean_name}"
            return await self._call_gemini_sdk(clean_name, prompt, system_instruction, temperature, max_tokens)
        else:
            return await self._call_openrouter(model_name, prompt, system_instruction, temperature, max_tokens)

    async def _call_gemini_sdk(
        self, model_name: str, prompt: str, system_instruction: str,
        temperature: float, max_tokens: int
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

    async def _call_openrouter(
        self, model_name: str, prompt: str, system_instruction: str,
        temperature: float, max_tokens: int
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
