"""Several API keys, tried in turn when one runs out of quota.

WHY THIS EXISTS
Gemini's free tier meters per key AND per model. A key can be exhausted for
gemini-3.6-flash and still answer happily on gemini-3.5-flash — measured, not
assumed — and a day of testing exhausts one key long before the others are
touched.

SPREAD, DON'T STICK, AND DON'T RACE
Requests go round-robin across the keys rather than concentrating on one.

The scarce resource here is quota, not latency: a diagnosis spends 4-8s inside
the model, so racing the same request across every key would burn four times the
quota to shave a queueing delay that barely exists. That is spending the scarce
thing to buy the cheap one.

Concentrating on one key is the opposite mistake and is what this pool used to
do — it pinned to whichever key last worked, which is precisely the pattern that
trips a per-minute limit while three other keys sit idle. Round-robin gives
roughly N times the per-minute headroom for the same quota spend.

Failover still sits on top: a key that returns 429 is put on COOLDOWN, keyed by
(key, model) because that is how the quota is actually metered, and skipped
until it expires instead of being retried on every request.

WHAT ROTATES, AND THE DISTINCTION THAT MATTERS
The question is not "is this error fatal" but "would ANOTHER KEY behave
differently". Those are not the same, and conflating them is a real bug:

  429 quota          key-specific     -> rotate, short cooldown
  503 overloaded     transient        -> rotate, short cooldown
  403 project denied KEY-SPECIFIC     -> rotate, LONG cooldown
  404 model retired  same everywhere  -> raise immediately
  400 bad request    same everywhere  -> raise immediately

403 was originally grouped with 404 and 400 as "the key is simply wrong, so do
not waste the others". That reasoning was backwards. A 403 says THIS project is
denied; the other keys belong to other projects and answer fine. Under
round-robin one denied key in four meant one diagnosis in four failing outright,
where the pool exists precisely to absorb that.

It gets a long cooldown rather than a short one because a denied project does
not come back on its own — it needs someone to fix the account — so re-probing
it every minute is noise. It is logged at ERROR once per cooldown so the operator
actually finds out.

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
import itertools
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("brain.genai_pool")

# How many suffixed keys to look for. Beyond a handful this is a signal someone
# needs a billed project, not more free keys.
MAX_SUFFIXED_KEYS = 10

# Errors worth trying another key for. Everything else is our problem, not the
# key's.
_ROTATE_ON = ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "403", "PERMISSION_DENIED")

# Errors that will not fix themselves before someone touches the account.
_PERSISTENT = ("403", "PERMISSION_DENIED")

# How long a key sits out after a quota error, per model. Free-tier limits are
# per-minute and per-day and the 429 body does not say which, so this is sized
# for the per-minute case: a genuinely day-exhausted key then costs one wasted
# call per minute, which is noise next to serving farmers from the other keys.
COOLDOWN_S = float(os.getenv("GEMINI_KEY_COOLDOWN_S", "60"))

# A denied or revoked project needs a human, not a retry. Sit it out for long
# enough that it stops costing a request per minute, but not forever — a key
# restored mid-session should come back without a restart.
DEAD_KEY_COOLDOWN_S = float(os.getenv("GEMINI_DEAD_KEY_COOLDOWN_S", "1800"))


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


def _is_persistent(error: Exception) -> bool:
    """True when this key will keep failing until a human intervenes."""
    text = str(error)
    return any(marker in text for marker in _PERSISTENT)


class GeminiPool:
    """Holds one client per key and fails over between them."""

    def __init__(self):
        self._clients: List[Any] = []
        self._labels: List[str] = []
        # Round-robin cursor. Incremented once per call so concurrent farmers
        # land on different keys instead of queueing behind one.
        self._turn = itertools.count()
        # (key index, model) -> monotonic time the cooldown expires.
        self._cooldown: Dict[Tuple[int, str], float] = {}
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

    def _is_cooling(self, index: int, model: str) -> bool:
        expiry = self._cooldown.get((index, model))
        return expiry is not None and time.monotonic() < expiry

    def _order(self, model: str) -> List[int]:
        """Key indices to try, round-robin, with cooling keys moved to the back.

        Cooling keys are not dropped: if every key is cooling we still try them
        all rather than failing without making a request, because the cooldown
        is a guess about a limit whose reset time we were never told.
        """
        count = len(self._clients)
        start = next(self._turn) % count
        rotated = [(start + offset) % count for offset in range(count)]
        ready = [i for i in rotated if not self._is_cooling(i, model)]
        cooling = [i for i in rotated if self._is_cooling(i, model)]
        return ready + cooling

    async def generate(self, *, model: str, contents: Any, config: Any) -> Any:
        """generate_content, spread across keys, with fail-over.

        Raises the last error if every key fails.
        """
        if not self._clients:
            raise RuntimeError("no Gemini API key configured")

        last_error: Optional[Exception] = None
        order = self._order(model)

        for position, index in enumerate(order):
            client = self._clients[index]
            try:
                # google-genai's generate_content is a blocking HTTP call.
                # Awaiting it directly would freeze the event loop for the full
                # 3-8s of every diagnosis, serialising all concurrent farmers.
                response = await asyncio.to_thread(
                    client.models.generate_content, model=model, contents=contents, config=config
                )
                # A success clears any stale cooldown — the limit has reset.
                self._cooldown.pop((index, model), None)
                return response
            except Exception as e:
                last_error = e
                if not _should_rotate(e):
                    raise
                persistent = _is_persistent(e)
                pause = DEAD_KEY_COOLDOWN_S if persistent else COOLDOWN_S
                self._cooldown[(index, model)] = time.monotonic() + pause
                remaining = len(order) - position - 1
                if persistent:
                    # Not a transient blip. Someone has to fix the account, so
                    # say so loudly rather than burying it among quota warnings.
                    logger.error(
                        f"{self._labels[index]} is DENIED for {model} "
                        f"({str(e)[:80]}) — this key needs attention; benching it "
                        f"for {pause:.0f}s. {remaining} key(s) left to try."
                    )
                else:
                    logger.warning(
                        f"{self._labels[index]} exhausted or unavailable for {model} "
                        f"({str(e)[:80]}); cooling down {pause:.0f}s, "
                        f"{remaining} key(s) left to try."
                    )

        logger.error(f"All {len(order)} Gemini key(s) failed for {model}.")
        raise last_error if last_error else RuntimeError("no key succeeded")

    def status(self) -> Dict[str, Any]:
        now = time.monotonic()
        cooling = sorted(
            f"{self._labels[i]}@{m}" for (i, m), until in self._cooldown.items() if until > now
        )
        return {
            "keys_configured": self.key_count,
            # Labels carry only the last four characters, never a usable secret.
            "keys": self._labels,
            "strategy": "round-robin with cooldown",
            "cooling_down": cooling,
        }


gemini_pool = GeminiPool()
