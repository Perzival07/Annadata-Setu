"""Cloud Translation — used narrowly, to recover detail the fallback script drops.

READ channel/services/languages.py FIRST. The spoken advisory is synthesised
with the farmer's own voice (mr-IN, hi-IN, bn-IN, en-IN), and text in a script
that voice does not read comes out as noise. The local template therefore
refuses to emit anything it cannot render in the target language, and the single
largest thing it drops is `action_text` — the actual instruction — which arrives
from brain in English.

The primary path (brain's /advisory-script) asks Gemini for Marathi directly and
is unaffected by any of this. This module improves only the fallback, which runs
when brain is unreachable: rather than dropping action_text entirely, translate
it, and keep it only if the result is genuinely speakable.

THE INVARIANT IS UNCHANGED, NOT RELAXED
Translation is not trusted. Cloud Translate happily passes Latin script through —
product names, "Mancozeb 75% WP", anything it cannot map — and that is exactly
what must not reach a Devanagari or Bengali voice. So every translation is
re-checked with has_foreign_script() against the TARGET language and discarded
on failure. A dropped sentence is a worse voice note; an English sentence read
by a Marathi voice is an unusable one.

English is the one target that needs no call at all: `action_text` already
arrives in English, so translating it would spend a request and a round trip to
produce approximately itself. It is returned directly, still guarded.

Dosages are deliberately NOT translated here. render.dosage_phrase builds them
from the parsed quantity, which cannot silently corrupt a number the way a
general-purpose translator can.
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from contracts.languages import DEFAULT_LANGUAGE, codes, get, is_supported

logger = logging.getLogger("channel.translate")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
# Off unless asked for: it is a fallback-path nicety, and the fallback path is
# already the one where something upstream has gone wrong.
ENABLED = os.getenv("ENABLE_TRANSLATION", "false").lower() == "true"

TIMEOUT_S = 4.0
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

    async def to_language(self, text: str, code: str = DEFAULT_LANGUAGE) -> Optional[str]:
        """Translate English into `code`, or None if the result is not speakable.

        None is a normal, expected return. Callers must already have a path for
        it — the same path they used before this module existed.
        """
        if not text or not text.strip():
            return None

        lang = get(code)
        if lang.code == SOURCE_LANGUAGE:
            # Already English. No request, no latency, no chance of a translator
            # mangling a chemical name on the way to saying the same thing.
            return self._vetted(text.strip(), lang.code)

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
                        "target_language_code": lang.code,
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

        return self._vetted(translated, lang.code)

    @staticmethod
    def _vetted(text: str, code: str) -> Optional[str]:
        """Keep a translation only if the target voice can actually read it."""
        # Imported here, not at module scope, to keep the dependency arrow
        # pointing one way: languages.py is the authority on what is speakable
        # and must not end up importing this module back.
        from contracts.languages import has_foreign_script

        if has_foreign_script(text, code):
            # Translate leaves chemical names, percentages and product codes in
            # Latin. Half-translated is not better than untranslated here.
            logger.info(
                f"Discarding translation — foreign script for {code}: {text[:60]!r}"
            )
            return None
        return text

    async def detect(self, text: str) -> Optional[str]:
        """Which of our languages the farmer wrote in, or None.

        Exists for one case that script inspection cannot solve: Hindi and
        Marathi are both Devanagari, so languages.detect_from_text deliberately
        returns None for them rather than guessing. Answering a Marathi farmer
        in Hindi is a failure they cannot report and we cannot see.

        Anything outside our four languages returns None — better to fall
        through to the region default than to answer in a language we do not
        actually support.
        """
        if not text or not text.strip() or not self.client:
            return None

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.detect_language,
                    request={
                        "parent": self.parent,
                        "content": text,
                        "mime_type": "text/plain",
                    },
                ),
                timeout=TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Language detection timed out after {TIMEOUT_S}s.")
            return None
        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
            return None

        for candidate in getattr(response, "languages", None) or []:
            code = get(getattr(candidate, "language_code", "") or "").code
            if is_supported(getattr(candidate, "language_code", "")):
                logger.info(f"Detected farmer language: {code}")
                return code
        return None

    async def to_marathi(self, text: str) -> Optional[str]:
        """to_language pinned to Marathi. Kept for existing callers and tests."""
        return await self.to_language(text, DEFAULT_LANGUAGE)

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": ENABLED,
            "available": self.is_available,
            "targets": codes(),
        }


translate_service = TranslateService()
