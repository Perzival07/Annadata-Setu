"""The language registry — what the farmer's language actually implies.

Lives in contracts/ because `channel` and `brain` must agree on it. channel
picks the language and speaks it; brain generates the script in it, and applies
the same script guard to its own output before returning it. BRAIN.md §16
forbids one service importing another's modules, and a second copy of these
tables in brain/ would drift — the two would disagree about what "bn" means, or
about which digits Bengali uses, and nothing would fail loudly.

Everything here exists because the codebase encoded exactly one assumption:
"Latin script means the voice will mispronounce it". That was true while the
only voice was mr-IN. It inverts for English, where Latin *is* the script, and
it is incomplete for Bengali, where Devanagari is just as unspeakable as Latin.

So the guard generalises rather than growing three more branches. The rule is
now "text must be in the target language's own script", and each language says
which script that is. `has_latin_script` was one instance of it (Marathi's).

Adding a language means adding a row to LANGUAGES here, its strings to
channel/services/phrasebook.py, and nothing else.
"""

import re
from typing import Dict, List, NamedTuple, Optional

# Unicode letter ranges per writing system. Digits, punctuation, ₹ and
# whitespace are script-neutral and belong to nobody.
#
# The Devanagari range deliberately EXCLUDES U+0964 and U+0965, the danda and
# double danda. Unicode files them under Devanagari for historical reasons, but
# they are the sentence terminators of Bengali, Punjabi, Odia and most other
# Indic scripts too — Unicode itself documents them as shared. Including them
# meant a correctly punctuated Bengali sentence ("নমস্কার। আপনার ফসলে…") was
# judged to contain Devanagari, so every Bengali script Gemini produced was
# rejected by compose_voice_script and silently downgraded to the local
# template. The farmer still got Bengali, just the shorter templated kind, and
# nothing above the debug log said so.
DANDA = "\u0964\u0965"
SCRIPT_RANGES = {
    "devanagari": r"\u0900-\u0963\u0966-\u097f",
    "bengali": r"\u0980-\u09ff",
    "latin": r"A-Za-z",
}

ASCII_DIGITS = "0123456789"


class Language(NamedTuple):
    code: str           # ISO 639-1, our internal key
    bcp47: str          # what Cloud STT and TTS want
    script: str         # key into SCRIPT_RANGES
    endonym: str        # the language's name in itself — farmers read this
    english_name: str
    digits: str         # digit glyphs, ASCII-ordered; "" means keep ASCII


LANGUAGES: Dict[str, Language] = {
    "mr": Language("mr", "mr-IN", "devanagari", "मराठी", "Marathi", "०१२३४५६७८९"),
    "hi": Language("hi", "hi-IN", "devanagari", "हिन्दी", "Hindi", "०१२३४५६७८९"),
    "bn": Language("bn", "bn-IN", "bengali", "বাংলা", "Bengali", "০১২৩৪৫৬৭৮৯"),
    # English keeps ASCII digits and Latin script. It is the one language where
    # action_text needs no translation at all — it already arrives in English.
    "en": Language("en", "en-IN", "latin", "English", "English", ""),
}

# Marathi stays the default: it is the demo district's language (BRAIN.md §13),
# and changing the default would silently change every existing farmer's replies.
DEFAULT_LANGUAGE = "mr"


def get(code: Optional[str]) -> Language:
    """The Language for a code, falling back to the default rather than raising.

    Callers reach this with codes from stored state, model output and STT
    responses. An unknown code must degrade to a working reply, not a 500.
    """
    if not code:
        return LANGUAGES[DEFAULT_LANGUAGE]
    normalised = code.strip().lower().replace("_", "-").split("-")[0]
    return LANGUAGES.get(normalised, LANGUAGES[DEFAULT_LANGUAGE])


def is_supported(code: Optional[str]) -> bool:
    if not code:
        return False
    return code.strip().lower().replace("_", "-").split("-")[0] in LANGUAGES


def codes() -> List[str]:
    return list(LANGUAGES)


# --- Script guards ----------------------------------------------------------
# The generalisation of has_latin_script/strip_to_speakable. "Foreign" is
# relative to the target language: Latin is foreign to Marathi, Devanagari is
# foreign to Bengali, and both are foreign to English.

_foreign_re_cache: Dict[str, re.Pattern] = {}


def _foreign_pattern(lang: Language) -> re.Pattern:
    if lang.code not in _foreign_re_cache:
        # KeyError here means a Language row named a script with no range.
        SCRIPT_RANGES[lang.script]
        others = "".join(r for name, r in SCRIPT_RANGES.items() if name != lang.script)
        # A run of foreign letters plus the punctuation that clings to it, so
        # stripping "Mancozeb 75% WP" does not leave orphaned marks behind.
        _foreign_re_cache[lang.code] = re.compile(rf"[{others}][{others}'()%./-]*")
    return _foreign_re_cache[lang.code]


def has_foreign_script(text: str, code: str = DEFAULT_LANGUAGE) -> bool:
    """True when `text` contains letters the target voice cannot pronounce."""
    if not text:
        return False
    return bool(_foreign_pattern(get(code)).search(text))


def strip_to_speakable(text: str, code: str = DEFAULT_LANGUAGE) -> str:
    """Last-resort guard: drop any foreign-script run that slipped through."""
    if not text:
        return ""
    cleaned = _foreign_pattern(get(code)).sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,।])", r"\1", cleaned)
    return re.sub(r"\.{2,}", ".", cleaned).strip()


def localize_digits(text: str, code: str = DEFAULT_LANGUAGE) -> str:
    """Render numerals in the language's own digits so the voice reads them right.

    English keeps ASCII: an en-IN voice reads "340" correctly and would stumble
    over "३४०".
    """
    lang = get(code)
    if not lang.digits:
        return text
    return text.translate(str.maketrans(ASCII_DIGITS, lang.digits))


