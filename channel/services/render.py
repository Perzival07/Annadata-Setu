"""Turning Diagnosis fields into something a given language's voice can say.

The Marathi-only ancestor of this module (channel/services/marathi.py, now a
thin shim over it) established the rule that still governs here: where a value
cannot be rendered safely in the target language, it is OMITTED rather than
spoken in English. The WhatsApp text message still carries the exact disease
name and dose, so nothing is lost — but the voice note stays speakable.

English is the case that proves the rule rather than breaking it. Its "foreign"
script is Devanagari and Bengali, its digits are ASCII, and its disease table is
empty because a diagnosis arrives in English already. Same code path, different
row in the registry.
"""

import re
from typing import Optional

from contracts.languages import DEFAULT_LANGUAGE, get, localize_digits
from channel.services.phrasebook import DISEASE_NAMES, UNITS, voice

# Canonical unit keys. The regex captures many spellings; these map to the four
# UNITS entries every language defines.
_UNIT_KEYS = {
    "g": "g", "gm": "g", "gram": "g", "grams": "g",
    "ml": "ml",
    "l": "l", "lit": "l", "litre": "l", "liter": "l",
    "kg": "kg",
}

_DOSE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(g|gm|gram|grams|ml|kg)\b\s*(?:per|/)\s*(\d+(?:\.\d+)?)?\s*"
    r"(l|lit|litre|liter)\b",
    re.IGNORECASE,
)


def disease_name(name: str, code: str = DEFAULT_LANGUAGE) -> Optional[str]:
    """The disease in `code`, or None when there is no safe rendering.

    None is load-bearing: emitting the English name inside a Devanagari or
    Bengali sentence is what produced the garbled voice note this whole layer
    exists to prevent. The caller falls back to a generic phrase.

    For English the name passes through — with the Latin binomial dropped, since
    "Alternaria solani" is Latin that even an en-IN voice reads as gibberish.
    """
    if not name:
        return None

    # "Early Blight (Alternaria solani)" -> "early blight"
    base = re.sub(r"\(.*?\)", "", name).strip()
    if not base:
        return None

    lang = get(code)
    if lang.script == "latin":
        return base

    table = DISEASE_NAMES.get(lang.code, {})
    key = base.lower()
    if key in table:
        return table[key]
    for known, translated in table.items():
        if known in key:
            return translated
    return None


def dosage_phrase(dosage: Optional[str], code: str = DEFAULT_LANGUAGE) -> Optional[str]:
    """A dose rendered as speakable words, e.g. '2g per litre' in the language.

    Anything that does not match a simple quantity-per-quantity pattern returns
    None rather than being read out in the wrong language. A dose is the one
    field where a mangled reading costs the farmer money, so the bar is high.
    """
    if not dosage:
        return None

    match = _DOSE_RE.search(dosage)
    if not match:
        return None

    lang = get(code)
    units = UNITS[lang.code]
    qty, raw_unit, per_qty, raw_per_unit = (
        match.group(1), match.group(2).lower(), match.group(3) or "1", match.group(4).lower()
    )

    # "2 g per 1 litre" is not how the dose is said in English; the Indic
    # phrasings read naturally with the leading १ and use the same string.
    key = "dosage_pattern_single" if per_qty in ("1", "1.0") else "dosage_pattern"

    return voice(key, lang.code).format(
        qty=localize_digits(qty, lang.code),
        unit=units[_UNIT_KEYS[raw_unit]],
        per_qty=localize_digits(per_qty, lang.code),
        per_unit=units[_UNIT_KEYS[raw_per_unit]],
    )
