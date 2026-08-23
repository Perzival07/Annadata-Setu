"""Cloud Translation — used narrowly, to recover detail the fallback script drops.

READ channel/services/marathi.py FIRST. The spoken advisory is synthesised with
an mr-IN voice, so Latin script in the script gets mispronounced or skipped. The
local template therefore refuses to emit anything it cannot render in Marathi,
and the single largest thing it drops is `action_text` — the actual instruction —
which arrives from brain in English.

The primary path (brain's /advisory-script) asks Gemini for Marathi directly and
is unaffected by any of this. This module improves only the fallback, which runs
when brain is unreachable: rather than dropping action_text entirely, translate
it, and keep it only if the result is genuinely speakable.

THE INVARIANT IS UNCHANGED, NOT RELAXED
Translation is not trusted. Cloud Translate happily passes Latin script through —
product names, "Mancozeb 75% WP", anything it cannot map — and that is exactly
what must not reach the voice. So every translation is re-checked with
has_latin_script() and discarded on failure. A dropped sentence is a worse voice
note; an English sentence read by a Marathi voice is an unusable one.

Dosages are deliberately NOT translated here. marathi.py renders them from the
parsed quantity (dosage_in_marathi), which cannot silently corrupt a number the
way a general-purpose translator can.
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("channel.translate")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
# Off unless asked for: it is a fallback-path nicety, and the fallback path is
# already the one where something upstream has gone wrong.
ENABLED = os.getenv("ENABLE_TRANSLATION", "false").lower() == "true"

TIMEOUT_S = 4.0
TARGET_LANGUAGE = "mr"
SOURCE_LANGUAGE = "en"


class TranslateService:
    def __init__(self):
        self.client = None
        self.parent = None
        self._init_client()

    def _init_client(self):
        if MOCK or not ENABLED:
            logger.info("TranslateService disabled (MOCK_MODE or ENABLE_TRANSLATION unset).")
            return

        if not GCP_PROJECT_ID:
            logger.warning("ENABLE_TRANSLATION set but GCP_PROJECT_ID is not — staying off.")
            return

        try:
            from google.cloud import translate

            self.client = translate.TranslationServiceClient()
            # v3 is regional; "global" is the right location for plain text and
            # avoids pinning this to asia-south1 having a Translate endpoint.
            self.parent = f"projects/{GCP_PROJECT_ID}/locations/global"
            logger.info("Google Cloud TranslationServiceClient initialized.")
        except Exception as e:
            logger.warning(f"Failed to initialize TranslationServiceClient: {e}. Staying off.")

    @property
    def is_available(self) -> bool:
        return self.client is not None

    async def to_marathi(self, text: str) -> Optional[str]:
        """Translate English to Marathi, or None if the result is not speakable.

        None is a normal, expected return. Callers must already have a path for
        it — the same path they used before this module existed.
        """
        if not text or not text.strip():
            return None
        if not self.client:
            return None

        try:
            # The v3 client is synchronous; off-thread so it cannot stall the
            # webhook's background pipeline.
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.translate_text,
                    request={
                        "parent": self.parent,
                        "contents": [text],
                        "mime_type": "text/plain",
                        "source_language_code": SOURCE_LANGUAGE,
                        "target_language_code": TARGET_LANGUAGE,
                    },
                ),
                timeout=TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Translation timed out after {TIMEOUT_S}s.")
            return None
        except Exception as e:
            logger.warning(f"Translation failed: {e}")
            return None

        translations = getattr(response, "translations", None) or []
        if not translations:
            logger.warning("Translation returned no result.")
            return None

        translated = (translations[0].translated_text or "").strip()
        if not translated:
            return None

        # Imported here, not at module scope, to keep the dependency arrow
        # pointing one way: marathi.py is the authority on what is speakable and
        # must not end up importing this module back.
        from channel.services.marathi import has_latin_script

        if has_latin_script(translated):
            # Translate leaves chemical names, percentages and product codes in
            # Latin. Half-translated is not better than untranslated here.
            logger.info(
                f"Discarding translation — Latin script survived: {translated[:60]!r}"
            )
            return None

        return translated

    def status(self) -> Dict[str, Any]:
        return {"enabled": ENABLED, "available": self.is_available, "target": TARGET_LANGUAGE}


translate_service = TranslateService()
