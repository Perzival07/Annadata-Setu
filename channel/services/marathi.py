"""Marathi rendering helpers for the spoken advisory.

The voice note is the demo (BRAIN.md §13) and it is synthesised with an mr-IN
voice, so anything left in Latin script gets mispronounced or skipped. The old
template interpolated the raw Diagnosis fields — which arrive in English — into
Marathi sentences, so ~45% of a typical script was English, including the entire
action_text.

BRAIN.md §11 (15:30) says to ask Gemini for Marathi directly. That is the
primary path (brain's /advisory-script). This module is the fallback used when
brain is unreachable, and its job is to stay speakable: never emit Latin script,
even at the cost of dropping a detail the text message still carries.
"""

import re
from typing import Optional

# Standard Marathi agronomic terms. करपा (blight), भुरी (powdery mildew),
# केवडा (downy mildew) and मर (wilt) are the words farmers actually use.
DISEASE_NAMES_MR = {
    "early blight": "अर्ली ब्लाइट म्हणजेच करपा",
    "late blight": "लेट ब्लाइट म्हणजेच उशिरा येणारा करपा",
    "bacterial blight": "जिवाणूजन्य करपा",
    "septoria leaf spot": "सेप्टोरिया पानावरील ठिपके",
    "purple blotch": "जांभळा करपा",
    "powdery mildew": "भुरी रोग",
    "downy mildew": "केवडा रोग",
    "anthracnose": "अँथ्रॅक्नोज",
    "fusarium wilt": "मर रोग",
    "leaf curl": "पाने गुंडाळणारा रोग",
    "nitrogen deficiency": "नत्राची कमतरता",
    "potassium deficiency": "पालाशची कमतरता",
    "nutrient deficiency": "अन्नद्रव्यांची कमतरता",
}

DEVANAGARI_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")

_UNITS_MR = {
    "g": "ग्रॅम", "gm": "ग्रॅम", "gram": "ग्रॅम", "grams": "ग्रॅम",
    "ml": "मिली", "l": "लिटर", "lit": "लिटर", "litre": "लिटर", "liter": "लिटर",
    "kg": "किलो",
}


def to_devanagari_digits(text: str) -> str:
    """Speak numerals in Devanagari so the voice reads them as Marathi."""
    return text.translate(DEVANAGARI_DIGITS)


def disease_in_marathi(disease_name: str) -> Optional[str]:
    """Marathi name for a disease, or None when we have no safe rendering.

    Returning None matters: emitting the English name into a Marathi sentence is
    what produced the garbled voice note. The caller falls back to a generic
    phrase, and the text message still carries the precise English name.
    """
    if not disease_name:
        return None
    # "Early Blight (Alternaria solani)" -> "early blight"; the botanical name
    # is Latin and unspeakable by an mr-IN voice.
    base = re.sub(r"\(.*?\)", "", disease_name).strip().lower()
    if base in DISEASE_NAMES_MR:
        return DISEASE_NAMES_MR[base]
    for key, value in DISEASE_NAMES_MR.items():
        if key in base:
            return value
    return None


def dosage_in_marathi(dosage: Optional[str]) -> Optional[str]:
    """Render a simple dose as speakable Marathi, e.g. '2g per litre' -> '२ ग्रॅम प्रति लिटर'.

    Anything that does not match a simple quantity-per-quantity pattern returns
    None rather than being read out in English.
    """
    if not dosage:
        return None
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*(g|gm|gram|grams|ml|kg)\b\s*(?:per|/)\s*(\d+(?:\.\d+)?)?\s*(l|lit|litre|liter)\b",
        dosage, re.IGNORECASE,
    )
    if not m:
        return None
    qty, unit, per_qty, per_unit = m.group(1), m.group(2).lower(), m.group(3) or "1", m.group(4).lower()
    return (
        f"{to_devanagari_digits(per_qty)} {_UNITS_MR[per_unit]} पाण्यात "
        f"{to_devanagari_digits(qty)} {_UNITS_MR[unit]}"
    )


def has_latin_script(text: str) -> bool:
    """True if any Latin letter survives — such a script is not safely speakable."""
    return bool(re.search(r"[A-Za-z]", text))


def strip_to_speakable(text: str) -> str:
    """Last-resort guard: drop any Latin-script run that slipped through."""
    cleaned = re.sub(r"[A-Za-z][A-Za-z'()%./-]*", "", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,।])", r"\1", cleaned)
    return re.sub(r"\.{2,}", ".", cleaned).strip()
