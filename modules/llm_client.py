import os
import time
import asyncio
from typing import Optional, List, Dict, Any
from google import genai
from google.genai import types as genai_types
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger

class LLMClient:
    def __init__(self):
        # API Keys
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        
        # Primary & Fallback Models
        self.primary_model = os.getenv("PRIMARY_MODEL", "google/gemini-2.0-flash-exp:free")
        # Update fallback to a more stable OpenRouter free model (Qwen 2.5 7B is highly stable)
        self.fallback_model = os.getenv("FALLBACK_MODEL", "qwen/qwen-2.5-7b-instruct:free")
        # Last resort fallback for Gemini SDK — confirmed model from API discovery
        self.gemini_last_resort = "models/gemini-2.0-flash"

        # Initialize Clients
        if self.google_api_key:
            try:
                self.gemini_client = genai.Client(api_key=self.google_api_key)
                logger.info("Gemini client (google.genai) initialized successfully.")
            except Exception as e:
                self.gemini_client = None
                logger.error(f"Failed to configure Gemini client: {e}")
        else:
            self.gemini_client = None
        self.openrouter_client = None
        if self.openrouter_api_key:
            self.openrouter_client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_api_key,
                default_headers={
                    "HTTP-Referer": "https://teaching.monster",
                    "X-Title": "Teaching Monster AI",
                }
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

    async def _execute_request(self, model_name: str, prompt: str, system_instruction: str, temperature: float, max_tokens: int) -> str:
        """Internal router for specific provider SDKs.
        
        Routing rules:
        - OpenRouter: any model name containing ":" (e.g., :free, :nitro) OR any
          slash-separated provider path (e.g., google/gemini-..., qwen/qwen-...)
          that is NOT a native Gemini SDK path (models/...).
        - Gemini SDK: plain names like "gemini-1.5-flash" or "models/gemini-1.5-flash".
        """
        # OpenRouter models use a "provider/model:variant" format.
        # The ":" variant qualifier is the clearest signal it's an OpenRouter model.
        # e.g. google/gemini-2.0-flash-exp:free, qwen/qwen-2.5-7b-instruct:free
        is_openrouter_style = ":" in model_name or (
            "/" in model_name and not model_name.startswith("models/")
        )
        
        if is_openrouter_style and self.openrouter_client:
            return await self._call_openrouter(model_name, prompt, system_instruction, temperature, max_tokens)
        else:
            # Native Gemini SDK path — ensure "models/" prefix if missing
            full_model_path = model_name if model_name.startswith("models/") else f"models/{model_name}"
            return await self._call_gemini_sdk(full_model_path, prompt, system_instruction, temperature, max_tokens)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def _call_gemini_sdk(self, model_name: str, prompt: str, system_instruction: str, temperature: float, max_tokens: int) -> str:
        """Call Gemini via the new google.genai client (v1 API — no more v1beta 404s)."""
        if not self.gemini_client:
            raise ValueError("Gemini client is not initialized. Check GOOGLE_API_KEY.")
        
        # Use name directly as provided (typically models/... or already clean)
        clean_name = model_name.strip()
        
        config = genai_types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction if system_instruction else None,
        )
        
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.gemini_client.models.generate_content(
                    model=clean_name,
                    contents=prompt,
                    config=config,
                )
            )
            
            if not response or not response.text:
                return "[Empty or blocked response]"
            return response.text
            
        except Exception as e:
            err_msg = str(e)
            if "404" in err_msg or "not found" in err_msg.lower():
                logger.warning(f"Gemini model '{clean_name}' not found. Falling back to models/gemini-2.0-flash...")
                config_fallback = genai_types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    system_instruction=system_instruction if system_instruction else None,
                )
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.gemini_client.models.generate_content(
                        model="models/gemini-2.0-flash",
                        contents=prompt,
                        config=config_fallback,
                    )
                )
                return response.text if (response and response.text) else "[Fallback failed]"
            raise e

    async def _call_openrouter(self, model_name: str, prompt: str, system_instruction: str, temperature: float, max_tokens: int) -> str:
        """Calls OpenRouter via OpenAI-compatible SDK."""
        if not self.openrouter_client:
            raise ValueError("OPENROUTER_API_KEY is missing for OpenRouter call.")
            
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.openrouter_client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        if not response.choices or not response.choices[0].message.content:
            raise ValueError(f"OpenRouter ({model_name}) returned an empty response.")
            
        return response.choices[0].message.content
