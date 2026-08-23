"""Several API keys, tried in turn when one runs out of quota.

WHY THIS EXISTS
Gemini's free tier meters per key AND per model. A key can be exhausted for
gemini-3.6-flash and still answer happily on gemini-3.5-flash, and a day of
testing exhausts one key long before the others are touched. Holding several
keys and moving on when one returns 429 is the difference between a demo that
survives an afternoon and one that starts escalating every photo halfway
through.

Rotation is ONLY for quota (429) and transient overload (503). A 404 is the
model not existing, a 403 is the key being wrong, and a 400 is our request being
malformed — retrying those on another key burns the rest of the quota to arrive
at the same error, so they raise immediately.

KEY DISCOVERY
GEMINI_API_KEY first, then GEMINI_API_KEY_1, _2, _3... The suffixed form exists
because the natural thing to do with three keys is to number them, and the
service previously read only the unsuffixed name — so three keys in .env meant
zero keys in use, and every diagnosis escalated with the logs reporting a
missing key.

The pool starts each call from the last key that worked rather than always from
the first, so a key that is spent for today is skipped after it fails once
instead of being retried on every single request.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("brain.genai_pool")

# How many suffixed keys to look for. Beyond a handful this is a signal someone
# needs a billed project, not more free keys.
MAX_SUFFIXED_KEYS = 10

# Errors worth trying another key for. Everything else is our problem, not the
# key's.
_ROTATE_ON = ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")


def discover_keys() -> List[str]:
    """Every configured key, in preference order, de-duplicated."""
    names = ["GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{i}" for i in range(1, MAX_SUFFIXED_KEYS + 1)]
    keys, seen = [], set()
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value and value not in seen:
            seen.add(value)
            keys.append(value)
    return keys


def _should_rotate(error: Exception) -> bool:
    text = str(error)
    return any(marker in text for marker in _ROTATE_ON)


class GeminiPool:
    """Holds one client per key and fails over between them."""

    def __init__(self):
        self._clients: List[Any] = []
        self._labels: List[str] = []
        self._current = 0
        self._build()

    def _build(self):
        keys = discover_keys()
        if not keys:
            logger.info("No Gemini API key configured.")
            return
        try:
            from google import genai
        except Exception as e:
            logger.warning(f"google-genai SDK unavailable: {e}")
            return

        for index, key in enumerate(keys):
            try:
                self._clients.append(genai.Client(api_key=key))
                # Never the key itself — these labels reach logs.
                self._labels.append(f"key{index + 1}(...{key[-4:]})")
            except Exception as e:
                logger.warning(f"Could not build a client for key {index + 1}: {e}")

        if self._clients:
            logger.info(f"Gemini pool ready with {len(self._clients)} key(s): {', '.join(self._labels)}")

    @property
    def is_available(self) -> bool:
        return bool(self._clients)

    @property
    def key_count(self) -> int:
        return len(self._clients)

    async def generate(self, *, model: str, contents: Any, config: Any) -> Any:
        """generate_content with fail-over. Raises the last error if all keys fail."""
        if not self._clients:
            raise RuntimeError("no Gemini API key configured")

        last_error: Optional[Exception] = None
        count = len(self._clients)

        for attempt in range(count):
            index = (self._current + attempt) % count
            client = self._clients[index]
            try:
                # google-genai's generate_content is a blocking HTTP call.
                # Awaiting it directly would freeze the event loop for the full
                # 3-8s of every diagnosis, serialising all concurrent farmers.
                response = await asyncio.to_thread(
                    client.models.generate_content, model=model, contents=contents, config=config
                )
                # Stick with whatever worked, so a spent key is not retried first
                # on every subsequent request.
                self._current = index
                return response
            except Exception as e:
                last_error = e
                if not _should_rotate(e):
                    raise
                remaining = count - attempt - 1
                logger.warning(
                    f"{self._labels[index]} exhausted or unavailable for {model} "
                    f"({str(e)[:80]}); {remaining} key(s) left to try."
                )

        logger.error(f"All {count} Gemini key(s) failed for {model}.")
        raise last_error if last_error else RuntimeError("no key succeeded")

    def status(self) -> Dict[str, Any]:
        return {
            "keys_configured": self.key_count,
            # Labels carry only the last four characters, never a usable secret.
            "keys": self._labels,
            "active": self._labels[self._current] if self._clients else None,
        }


gemini_pool = GeminiPool()
