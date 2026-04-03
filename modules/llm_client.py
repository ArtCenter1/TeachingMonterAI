import os
import time
import asyncio
from typing import Optional, List, Dict, Any
import google.generativeai as genai
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
        # Last resort fallback for Gemini SDK
        self.gemini_last_resort = "models/gemini-1.5-flash"

        # Initialize Clients
        if self.google_api_key:
            try:
                genai.configure(api_key=self.google_api_key)
            except Exception as e:
                logger.error(f"Failed to configure Gemini SDK: {e}")
            
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
        if "gemini-1.5-flash-latest" not in models_to_try:
            models_to_try.append("gemini-1.5-flash-latest")

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
        """Internal router for specific provider SDKs."""
        
        # Scenario A: OpenRouter (if model name has / and not explicitly google SDK target)
        if "/" in model_name and "google/" not in model_name:
            return await self._call_openrouter(model_name, prompt, system_instruction, temperature, max_tokens)
        
        # Scenario B: Google Gemini SDK
        else:
            # Strip OpenRouter prefix if it leaked in
            clean_name = model_name.replace("google/", "")
            return await self._call_gemini_sdk(clean_name, prompt, system_instruction, temperature, max_tokens)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def _call_gemini_sdk(self, model_name: str, prompt: str, system_instruction: str, temperature: float, max_tokens: int) -> str:
        """Call Gemini via direct SDK with robust model discovery."""
        if not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY is missing for Gemini SDK call.")
            
        try:
            # Clean up model name
            clean_model_name = model_name.split("/")[-1]
            
            model = genai.GenerativeModel(
                model_name=clean_model_name,
                system_instruction=system_instruction
            )
            
            # Wrap synchronous call
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens
                    )
                )
            )
            
            if not response or not hasattr(response, "text") or not response.text:
                return "[Empty or blocked response]"
                
            return response.text

        except Exception as e:
            err_msg = str(e)
            if "404" in err_msg or "not found" in err_msg.lower():
                logger.warning(f"Gemini model {model_name} not found. Attempting discovery...")
                # Try to discovery available models
                available = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
                if available:
                    alt_name = next((m for m in available if "flash" in m.lower()), available[0]).split("/")[-1]
                    logger.info(f"Retrying with discovered model: {alt_name}")
                    model = genai.GenerativeModel(model_name=alt_name, system_instruction=system_instruction)
                    response = await asyncio.get_event_loop().run_in_executor(None, lambda: model.generate_content(prompt))
                    return response.text if (response and hasattr(response, "text") and response.text) else "[Retry failed]"
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
