import os
import logging
from typing import Optional

logger = logging.getLogger("channel.tts")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"

class TTSService:
    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        if MOCK:
            logger.info("TTSService initialized in MOCK_MODE.")
            return

        try:
            from google.cloud import texttospeech
            self.client = texttospeech.TextToSpeechClient()
            logger.info("Google Cloud TextToSpeechClient initialized.")
        except Exception as e:
            logger.warning(f"Failed to initialize TextToSpeechClient: {e}. Falling back to MOCK mode.")

    async def synthesize_speech(self, text: str, language_code: str = "mr-IN") -> bytes:
        """
        Synthesize Marathi text into spoken audio in OGG_OPUS format.
        """
        if MOCK or not self.client:
            logger.info("Returning MOCK synthesized speech bytes.")
            return b"OggS_mock_opus_audio_stream_header_data"

        try:
            from google.cloud import texttospeech

            synthesis_input = texttospeech.SynthesisInput(text=text)

            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
            )

            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.OGG_OPUS
            )

            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )

            return response.audio_content
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}. Falling back to mock bytes.")
            return b"OggS_mock_opus_audio_stream_header_data"

tts_service = TTSService()
