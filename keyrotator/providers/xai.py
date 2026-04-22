import asyncio
import aiohttp
from typing import Optional
from loguru import logger

from keyrotator.pool import KeyPool, AllKeysExhaustedError


def _extract_error_code(exc: Exception) -> int:
    """
    Parse HTTP status code from aiohttp exceptions.
    Returns the code as int, or 500 if unparseable.
    """
    msg = str(exc)
    for code in [429, 402, 403, 404, 500]:
        if str(code) in msg:
            return code
    return 500


def _is_quota_error(exc: Exception) -> bool:
    """Returns True for errors we should rotate on (quota/auth related)."""
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
    Attempt xAI generation using pool rotation.
    On quota errors: quarantine the key and try the next one.
    On non-quota errors: re-raise immediately (don't rotate).
    Raises AllKeysExhaustedError if no healthy key is available.
    """
    attempted_keys = set()

    while True:
        entry = pool.get_key()
        if entry is None:
            raise AllKeysExhaustedError(
                f"All xAI keys in pool are exhausted. "
                "Check /dev/pool-status/ui for details."
            )

        if entry.key in attempted_keys:
            # All available keys attempted — pool is exhausted
            raise AllKeysExhaustedError(
                f"All xAI keys in pool are exhausted after attempting {len(attempted_keys)}. "
                "Check /dev/pool-status/ui for details."
            )

        attempted_keys.add(entry.key)

        try:
            logger.debug(f"Attempting xAI call with key {entry.alias}")
            result = await _call_xai_api(
                api_key=entry.key,
                model_name=model_name,
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            pool.report_success(entry)
            return result

        except Exception as exc:
            error_code = _extract_error_code(exc)
            if _is_quota_error(exc):
                logger.warning(
                    f"xAI key {entry.alias} → {error_code} ({exc}). "
                    f"Quarantining for {pool.rate_limit_quarantine_sec}s."
                )
                pool.report_error(entry, error_code)
                # Continue to next key
            else:
                # Non-quota error — re-raise immediately
                logger.error(
                    f"xAI key {entry.alias} → {error_code} ({exc}). Re-raising."
                )
                pool.report_error(entry, error_code)
                raise


async def _call_xai_api(
    api_key: str,
    model_name: str,
    prompt: str,
    system_instruction: Optional[str],
    temperature: float,
    max_tokens: int,
) -> str:
    """
    Call xAI API directly via REST.
    """
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["choices"][0]["message"]["content"]
