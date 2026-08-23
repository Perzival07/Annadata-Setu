"""Marathi view of the shared rendering layer.

Kept as its own module because channel/services/composer.py, translate.py and
channel/tests/test_marathi.py all import these names, and because Marathi is
still the default language (BRAIN.md §13). Every function here is the
language-aware implementation in render.py / languages.py with code="mr".

New code should call those directly and pass the farmer's language. Nothing in
this module knows anything Marathi-specific any more — the Marathi strings live
in phrasebook.py alongside the other three languages.
"""

from typing import Optional

from contracts.languages import (
    has_foreign_script as _has_foreign_script,
    localize_digits as _localize_digits,
    strip_to_speakable as _strip_to_speakable,
)
from channel.services.phrasebook import DISEASE_NAMES
from channel.services.render import disease_name as _disease_name
from channel.services.render import dosage_phrase as _dosage_phrase

MARATHI = "mr"

# Kept for callers that read the table directly.
DISEASE_NAMES_MR = DISEASE_NAMES[MARATHI]


def to_devanagari_digits(text: str) -> str:
    """Speak numerals in Devanagari so the voice reads them as Marathi."""
    return _localize_digits(text, MARATHI)


def disease_in_marathi(disease_name: str) -> Optional[str]:
    """Marathi name for a disease, or None when we have no safe rendering."""
    return _disease_name(disease_name, MARATHI)


def dosage_in_marathi(dosage: Optional[str]) -> Optional[str]:
    """Render a simple dose as speakable Marathi, e.g. '2g per litre'."""
    return _dosage_phrase(dosage, MARATHI)


def has_latin_script(text: str) -> bool:
    """True if any Latin letter survives — such a script is not safely speakable.

    Latin is what is foreign *to Marathi*. For the general test against any
    target language, use languages.has_foreign_script.
    """
    return _has_foreign_script(text, MARATHI)


def strip_to_speakable(text: str) -> str:
    """Last-resort guard: drop any Latin-script run that slipped through."""
    return _strip_to_speakable(text, MARATHI)
