import asyncio
from typing import Optional
from loguru import logger
from google import genai
from google.genai import types as genai_types

from keyrotator.pool import KeyPool, AllKeysExhaustedError


def _extract_error_code(exc: Exception) -> int:
    """
    Parse HTTP status code from google.genai exceptions.
    google.genai raises exceptions with status codes in the message string.
    Pattern: "429 RESOURCE_EXHAUSTED..." or "402 ..." or "403 ..."
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
    Attempt Gemini generation using pool rotation.
    On quota errors: quarantine the key and try the next one.
    On non-quota errors: re-raise immediately (don't rotate).
    Raises AllKeysExhaustedError if no healthy key is available.
    """
    attempted_keys = set()

    while True:
        entry = pool.get_key()
        if entry is None:
            raise AllKeysExhaustedError(
                f"All Gemini keys in pool are exhausted. "
                f"Check /dev/pool-status/ui for details."
            )

        # Avoid infinite loop if pool cycles back to already-failed keys
        if entry.key in attempted_keys:
            raise AllKeysExhaustedError(
                f"All Gemini keys attempted and failed. Last key: {entry.alias}"
            )
        attempted_keys.add(entry.key)

        try:
            # Build a fresh client per key (keys rotate, clients don't)
            client = genai.Client(api_key=entry.key)

            clean_name = (
                model_name if model_name.startswith("models/")
                else f"models/{model_name}"
            )

            config = genai_types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_instruction or None,
            )

            # google.genai is sync — run in executor to avoid blocking event loop
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=clean_name,
                    contents=prompt,
                    config=config,
                )
            )

            if not response or not response.text:
                return "[Empty or blocked response]"

            pool.report_success(entry)
            logger.debug(f"[keyrotator:gemini] Success with {entry.alias}")
            return response.text

        except Exception as e:
            if _is_quota_error(e):
                code = _extract_error_code(e)
                pool.report_error(entry, code, str(e))
                logger.warning(
                    f"[keyrotator:gemini] {entry.alias} failed ({code}), rotating..."
                )
                await asyncio.sleep(2)  # Prevent rapid-fire exhaustion across shared IP limits
                continue  # try next key
            else:
                # Non-quota error (e.g. invalid content, network issue)
                # Don't penalize the key, just re-raise
                raise
