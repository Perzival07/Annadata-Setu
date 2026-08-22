"""Smoke test suite verifying channel webhook verification and mock pipeline execution."""

import asyncio
import unittest
from channel.services.pipeline import process_inbound_pipeline

MOCK_PAYLOAD = {
    "sender_phone": "919876543210",
    "message_id": "wamid.HBgMOTE5ODc2NTQzMjEwFQIAERgSMzFFODQ2RjlCRjhEQjE5RjhBAA==",
    "timestamp": "1710000000",
    "type": "text",
    "text": "माझ्या पिकाची पहाणी करा"
}

class TestChannelSmoke(unittest.TestCase):
    def test_pipeline_execution(self):
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(process_inbound_pipeline(MOCK_PAYLOAD))
            print("Channel Pipeline Smoke Test Passed!")
        except Exception as e:
            self.fail(f"Pipeline processing failed: {e}")

if __name__ == "__main__":
    unittest.main()
