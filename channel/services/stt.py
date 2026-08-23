import os
import logging
from typing import List, NamedTuple, Optional

from contracts.languages import DEFAULT_LANGUAGE, LANGUAGES, get

logger = logging.getLogger("channel.stt")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"

# Cloud Speech accepts a primary language plus a handful of alternatives and
# reports which one it actually heard. That report is layer 2 of language
# resolution (see pipeline.resolve_language): the farmer's own voice note tells
# us what to answer in, without asking them to configure anything.
MAX_ALTERNATIVE_LANGUAGES = 3

MOCK_TRANSCRIPTS = {
    "mr": "माझ्या टोमॅटोच्या पानांवर काळे डाग पडले आहेत आणि झाड सुकत आहे.",
    "hi": "मेरे टमाटर के पत्तों पर काले धब्बे पड़ गए हैं और पौधा सूख रहा है.",
    "bn": "আমার টমেটো গাছের পাতায় কালো দাগ পড়েছে এবং গাছ শুকিয়ে যাচ্ছে.",
    "en": "There are black spots on my tomato leaves and the plant is drying up.",
}


class Transcription(NamedTuple):
    """What was said, and which language it was said in."""

    text: str
    # The language Cloud Speech reports having recognised, or None when we
    # cannot tell. None must not be mistaken for the default: it means "no
    # evidence", and resolution falls through to the next layer rather than
    # pinning the farmer to a language on a guess.
    language: Optional[str] = None


class STTService:
    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        if MOCK:
            logger.info("STTService initialized in MOCK_MODE.")
            return

        try:
            from google.cloud import speech
            self.client = speech.SpeechClient()
            logger.info("Google Cloud SpeechClient initialized.")
        except Exception as e:
            logger.warning(f"Failed to initialize SpeechClient: {e}. Falling back to MOCK mode.")

    @staticmethod
    def _alternatives(primary: str) -> List[str]:
        """Every other supported language, capped at what the API accepts."""
        others = [l.bcp47 for code, l in LANGUAGES.items() if code != primary]
        return others[:MAX_ALTERNATIVE_LANGUAGES]

    async def transcribe_audio(
        self, audio_bytes: bytes, code: str = DEFAULT_LANGUAGE
    ) -> Transcription:
        """Transcribe OGG_OPUS audio, reporting the language actually recognised.

        `code` is the best current guess and becomes the primary hypothesis; the
        other supported languages ride along as alternatives. A farmer whose
        stored preference is Marathi but who speaks Hindi is answered in Hindi.
        """
        lang = get(code)

        if MOCK or not self.client:
            logger.info("Returning MOCK transcription.")
            return Transcription(MOCK_TRANSCRIPTS[lang.code], lang.code)

        try:
            from google.cloud import speech

            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
                sample_rate_hertz=16000,
                language_code=lang.bcp47,
                alternative_language_codes=self._alternatives(lang.code),
                model="latest_long",
            )
            audio = speech.RecognitionAudio(content=audio_bytes)

            response = self.client.recognize(config=config, audio=audio)

            transcript = ""
            detected: Optional[str] = None
            for result in response.results:
                transcript += result.alternatives[0].transcript + " "
                # Every result carries the language it was recognised in; the
                # first one wins, since a single voice note is one language.
                if detected is None and getattr(result, "language_code", None):
                    detected = get(result.language_code).code

            return Transcription(transcript.strip(), detected)
        except Exception as e:
            # No transcript and no language claim. Returning the mock string
            # here would put words in the farmer's mouth and — worse — assert a
            # language on the strength of a failed call.
            logger.error(f"STT transcription failed: {e}")
            return Transcription("", None)


stt_service = STTService()
