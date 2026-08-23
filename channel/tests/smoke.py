"""Smoke tests for the channel inbound pipeline.

The property under test is the one that matters most on a real handset: a
failure anywhere in the chain must reach the farmer as "we don't know", never
as the demo fixture's confident "spray ₹340 of Mancozeb".
"""

import asyncio
import base64
import unittest
from unittest import mock

from channel.services import pipeline
from contracts.mock_data import DIAGNOSIS as FIXTURE


def _payload(msg_type, message_id, **extra):
    return {"sender_phone": "919876543210", "message_id": message_id, "type": msg_type, **extra}


class FakeOutbound:
    def __init__(self):
        self.texts = []
        self.audio = []

    async def send_text_message(self, phone, text):
        self.texts.append(text)
        return True

    async def send_audio_message(self, phone, audio):
        self.audio.append(audio)
        return True


class FakeInbound:
    def __init__(self, media=b"\xff\xd8\xff fake-jpeg"):
        self.media = media

    async def fetch_media_bytes(self, media_id):
        return self.media


class FakeTTS:
    async def synthesize_speech(self, text):
        return b"OggS_fake"


class ChannelPipelineTest(unittest.TestCase):
    def setUp(self):
        self.out = FakeOutbound()
        self.patches = [
            mock.patch.object(pipeline, "whatsapp_out_service", self.out),
            mock.patch.object(pipeline, "whatsapp_in_service", FakeInbound()),
            mock.patch.object(pipeline, "tts_service", FakeTTS()),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])
        pipeline.user_state_service.processed_message_ids.clear()
        pipeline.user_state_service.user_sessions.clear()

    def _run(self, payload):
        asyncio.run(pipeline.process_inbound_pipeline(payload))

    # ---------------------------------------------------------------- routing

    def test_location_pin_is_stored_and_does_not_diagnose(self):
        self._run(_payload("location", "m_loc", lat=19.9975, lon=73.7898))
        self.assertEqual(
            pipeline.user_state_service.get_user_location("919876543210"), (19.9975, 73.7898)
        )
        self.assertEqual(len(self.out.texts), 1)
        self.assertNotIn(FIXTURE.disease_name, self.out.texts[0])

    def test_text_message_asks_for_a_photo(self):
        self._run(_payload("text", "m_txt", text="माझ्या पिकावर डाग आहेत"))
        self.assertEqual(len(self.out.texts), 1)
        self.assertNotIn(FIXTURE.disease_name, self.out.texts[0])

    def test_duplicate_message_id_is_skipped(self):
        """Meta retries slow webhooks; a second delivery must not reply twice."""
        self._run(_payload("text", "m_dupe", text="hello"))
        first = len(self.out.texts)
        self._run(_payload("text", "m_dupe", text="hello"))
        self.assertEqual(len(self.out.texts), first)

    # ------------------------------------------------------- failure handling

    def test_brain_outage_never_yields_the_fixture(self):
        async def boom(*a, **k):
            raise RuntimeError("brain unreachable")

        with mock.patch.object(pipeline, "diagnose_leaf", boom), \
             mock.patch.object(pipeline, "get_plot_passport", boom):
            self._run(_payload("image", "m_img", media_id="mid1"))

        reply = self.out.texts[-1]
        self.assertNotIn(FIXTURE.disease_name, reply)
        self.assertNotIn(str(FIXTURE.estimated_cost_inr), reply)
        self.assertIn("फवारणी करू नका", reply)  # "do not spray"

    def test_undownloadable_media_escalates(self):
        with mock.patch.object(pipeline, "whatsapp_in_service", FakeInbound(media=None)):
            self._run(_payload("image", "m_nomedia", media_id="mid2"))
        self.assertNotIn(FIXTURE.disease_name, self.out.texts[-1])

    def test_image_is_sent_to_brain_as_base64(self):
        """Meta graph URLs need our bearer token, so brain cannot fetch them."""
        seen = {}

        async def capture(image_url, passport, image_base64=None):
            seen["url"] = image_url
            seen["b64"] = image_base64
            return FIXTURE

        async def fake_passport(lat, lon):
            from contracts.mock_data import PASSPORT
            return PASSPORT

        with mock.patch.object(pipeline, "diagnose_leaf", capture), \
             mock.patch.object(pipeline, "get_plot_passport", fake_passport):
            self._run(_payload("image", "m_b64", media_id="mid3"))

        self.assertIsNone(seen["url"])
        self.assertEqual(base64.b64decode(seen["b64"]), b"\xff\xd8\xff fake-jpeg")


if __name__ == "__main__":
    unittest.main()
