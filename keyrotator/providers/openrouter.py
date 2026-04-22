import asyncio
from typing import Optional
from loguru import logger
from openai import AsyncOpenAI

from keyrotator.pool import KeyPool, AllKeysExhaustedError


def _extract_error_code(exc: Exception) -> int:
    """
    Parse HTTP status code from openai SDK exceptions.
    openai raises openai.APIStatusError with a .status_code attribute.
    Falls back to string parsing if needed.
    """
    if hasattr(exc, "status_code"):
        return exc.status_code
    msg = str(exc)
    for code in [429, 402, 403, 404, 500]:
        if str(code) in msg:
            return code
    return 500


def _is_quota_error(exc: Exception) -> bool:
    code = _extract_error_code(exc)
    return code in (429, 402, 403)


async def call_with_pool(
    pool: KeyPool,
    model_name: str,
    prompt: str,
    system_instruction: Optional[str],
    temperature: float,
    max_tokens: int,
) -> str:
    """
    Attempt OpenRouter generation using pool rotation.
    Behaves identically to gemini.call_with_pool() but for OpenRouter.
    """
    attempted_keys = set()

    while True:
        entry = pool.get_key()
        if entry is None:
            raise AllKeysExhaustedError(
                f"All OpenRouter keys in pool are exhausted. "
                f"Check /dev/pool-status/ui for details."
            )

        if entry.key in attempted_keys:
            raise AllKeysExhaustedError(
                f"All OpenRouter keys attempted and failed."
            )
        attempted_keys.add(entry.key)

        try:
            # Build a fresh AsyncOpenAI client per key
            client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=entry.key,
                default_headers={
                    "HTTP-Referer": "https://teaching.monster",
                    "X-Title": "Teaching Monster AI",
                }
            )

            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})

            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            if not response.choices or not response.choices[0].message.content:
                raise ValueError(f"OpenRouter ({model_name}) returned empty response")

            pool.report_success(entry)
            logger.debug(f"[keyrotator:openrouter] Success with {entry.alias}")
            return response.choices[0].message.content

        except Exception as e:
            if _is_quota_error(e):
                code = _extract_error_code(e)
                pool.report_error(entry, code, str(e))
                logger.warning(
                    f"[keyrotator:openrouter] {entry.alias} failed ({code}), rotating..."
                )
                await asyncio.sleep(2)  # Prevent rapid-fire exhaustion across shared limits
                continue
            else:
                raise
