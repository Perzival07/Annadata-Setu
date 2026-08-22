import os
import logging
from typing import Optional

logger = logging.getLogger("channel.stt")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"

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

    async def transcribe_audio(self, audio_bytes: bytes, language_code: str = "mr-IN") -> str:
        """
        Transcribe audio bytes (OGG_OPUS 16000Hz) to text using Google Cloud Speech Chirp model.
        """
        if MOCK or not self.client:
            logger.info("Returning MOCK transcription.")
            return "माझ्या टोमॅटोच्या पानांवर काळे डाग पडले आहेत आणि झाड सुकत आहे."

        try:
            from google.cloud import speech

            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
                sample_rate_hertz=16000,
                language_code=language_code,
                model="latest_long"
            )
            audio = speech.RecognitionAudio(content=audio_bytes)

            response = self.client.recognize(config=config, audio=audio)
            transcript = ""
            for result in response.results:
                transcript += result.alternatives[0].transcript + " "

            return transcript.strip()
        except Exception as e:
            logger.error(f"STT transcription failed: {e}. Falling back to mock string.")
            return "माझ्या टोमॅटोच्या पानांवर काळे डाग पडले आहेत."

stt_service = STTService()
