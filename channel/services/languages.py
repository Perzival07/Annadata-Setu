"""Channel's view of the language registry.

The registry itself is contracts/languages.py — brain needs the same script
rules for the scripts it generates, so the tables cannot live in one service.
What is here is the part only channel does: working out which language a farmer
wants from a pin, a message, or a menu reply.
"""

from typing import Dict, List, Optional
import re

from contracts.languages import (
    ASCII_DIGITS,
    DEFAULT_LANGUAGE,
    LANGUAGES,
    SCRIPT_RANGES,
    Language,
    codes,
    get,
    has_foreign_script,
    is_supported,
    localize_digits,
    strip_to_speakable,
)

# Every state outside the two below is answered in Hindi. It is the widest-reach
# option of the four and the product decision for this deployment; English stays
# reachable, but only when a farmer asks for it or writes in it, never as the
# consequence of a pin landing somewhere unmapped.
FALLBACK_BY_REGION = "hi"


# --- Where a pin implies a language -----------------------------------------
# Layer 3 of resolution (see resolve_language in pipeline.py). Deliberately a
# majority-language guess and nothing more — it is the weakest signal, and it
# loses to anything the farmer has actually told us.

STATE_LANGUAGE: Dict[str, str] = {
    # Deliberately only two entries. The rule is: West Bengal is answered in
    # Bengali, Maharashtra in Marathi, and everywhere else in Hindi via
    # FALLBACK_BY_REGION. Listing more states here would quietly re-introduce
    # per-state guesses that nobody asked for — Goa and Assam used to be mapped
    # to Marathi and Bengali respectively, which is defensible linguistically
    # and is not the rule this deployment runs on.
    "west bengal": "bn",
    "maharashtra": "mr",
}


def language_for_state(state: Optional[str]) -> Optional[str]:
    """The language for a state, or None when the state itself is unknown.

    A known state that is not West Bengal or Maharashtra returns None here and
    the caller falls through to FALLBACK_BY_REGION (Hindi). None therefore means
    "this table has nothing to say", not "answer in the default" — the caller
    still distinguishes a real state from an unresolved pin.
    """
    if not state:
        return None
    return STATE_LANGUAGE.get(state.strip().lower())


# --- Detecting what the farmer wrote ----------------------------------------

def script_of(text: str) -> Optional[str]:
    """Which writing system dominates `text`, or None if it has no letters."""
    if not text:
        return None
    counts = {
        name: len(re.findall(rf"[{rng}]", text)) for name, rng in SCRIPT_RANGES.items()
    }
    best = max(counts, key=counts.get)
    return best if counts[best] else None


def detect_from_text(text: str) -> Optional[str]:
    """Best-effort language for a farmer's own message, or None.

    Script alone cannot separate Hindi from Marathi — both are Devanagari — so
    this returns None for Devanagari rather than guessing. The caller asks
    Cloud Translate, which can tell them apart, and falls through to the region
    default if it is unavailable. Guessing here would silently answer a Marathi
    farmer in Hindi with no way to tell it had happened.
    """
    script = script_of(text)
    if script == "bengali":
        return "bn"
    if script == "latin":
        return "en"
    return None


# --- The farmer asking for a language ---------------------------------------
# Free text, because a WhatsApp list message is one more thing to configure in
# Meta's console and a farmer typing "hindi" should just work.

_NAME_ALIASES: Dict[str, str] = {
    "mr": "mr", "marathi": "mr", "मराठी": "mr",
    "hi": "hi", "hindi": "hi", "हिन्दी": "hi", "हिंदी": "hi",
    "en": "en", "english": "en", "इंग्रजी": "en", "इंग्लिश": "en", "ইংরেজি": "en",
    "bn": "bn", "bengali": "bn", "bangla": "bn", "বাংলা": "bn", "বাঙালি": "bn",
}

# The numbered shortcuts are DERIVED from registry order, never written out. The
# menu numbers its options the same way, so "reply 3" cannot come to mean one
# language in the menu and another in the parser — which is precisely the bug a
# second hand-written list would eventually introduce.
_LANGUAGE_ALIASES: Dict[str, str] = {
    **_NAME_ALIASES,
    **{str(i): code for i, code in enumerate(LANGUAGES, start=1)},
}


def menu_position(code: str) -> int:
    """1-based position of a language in the chooser."""
    return list(LANGUAGES).index(code) + 1

# Words that mean "language" in each of the four — the farmer asking to switch
# without naming one gets the menu.
_LANGUAGE_REQUEST = {"language", "lang", "भाषा", "ভাষা"}


def parse_language_command(text: str) -> Optional[str]:
    """A language code when this message is the farmer choosing one, else None.

    Matched on the whole message only. A note that merely mentions a language
    ("my hindi neighbour has the same spots") is a note about their crop, not a
    settings change.
    """
    if not text:
        return None
    cleaned = text.strip().lower().strip(".!?,")
    if cleaned in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[cleaned]
    # "language: hindi", "भाषा हिंदी"
    parts = [p for p in re.split(r"[\s:=]+", cleaned) if p]
    if len(parts) == 2 and parts[0] in _LANGUAGE_REQUEST:
        return _LANGUAGE_ALIASES.get(parts[1])
    return None


def is_language_request(text: str) -> bool:
    """True when the farmer asked about language without naming one."""
    if not text:
        return False
    return text.strip().lower().strip(".!?,") in _LANGUAGE_REQUEST
