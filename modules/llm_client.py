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
        
        # Default Models
        self.primary_model = os.getenv("PRIMARY_MODEL", "gemini-2.0-flash")
        self.fallback_model = os.getenv("FALLBACK_MODEL", "gemini-1.5-flash")

        # Initialize Clients
        if self.google_api_key:
            genai.configure(api_key=self.google_api_key)
            
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
        Unified generation method with fallback.
        1. Tries model_override if provided.
        2. Tries primary_model.
        3. Fails-over to fallback_model on error.
        """
        target_model = model_override or self.primary_model
        
        try:
            return await self._execute_request(target_model, prompt, system_instruction, temperature, max_tokens)
        except Exception as e:
            logger.warning(f"Primary model {target_model} failed: {str(e)}. Attempting fallback...")
            if target_model != self.fallback_model:
                try:
                    return await self._execute_request(self.fallback_model, prompt, system_instruction, temperature, max_tokens)
                except Exception as fallback_e:
                    logger.error(f"Fallback model {self.fallback_model} also failed: {str(fallback_e)}")
                    raise fallback_e
            else:
                raise e

    async def _execute_request(self, model_name: str, prompt: str, system_instruction: str, temperature: float, max_tokens: int) -> str:
        """Internal router for specific provider SDKs."""
        
        # Scenario A: OpenRouter (if model name has / or specifically requested)
        if "/" in model_name or (self.openrouter_client and not model_name.startswith("gemini-")):
            return await self._call_openrouter(model_name, prompt, system_instruction, temperature, max_tokens)
        
        # Scenario B: Google Gemini SDK
        else:
            return await self._call_gemini_sdk(model_name, prompt, system_instruction, temperature, max_tokens)

    async def _call_gemini_sdk(self, model_name: str, prompt: str, system_instruction: str, temperature: float, max_tokens: int) -> str:
        """Calls Google Generative AI SDK."""
        if not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY is missing for Gemini SDK call.")
            
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction
        )
        
        # Wrap the synchronous SDK call in an executor
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
        return response.text

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
        return response.choices[0].message.content
