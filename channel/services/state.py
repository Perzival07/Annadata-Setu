import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("channel.state")

class UserStateService:
    def __init__(self):
        self.processed_message_ids = set()
        self.user_sessions: Dict[str, Dict[str, Any]] = {}

    def is_duplicate_message(self, message_id: str) -> bool:
        """Check if Meta message_id has already been processed (prevents duplicate retries)."""
        if not message_id:
            return False
        if message_id in self.processed_message_ids:
            return True
        self.processed_message_ids.add(message_id)
        # Cap set size to prevent unbounded memory growth
        if len(self.processed_message_ids) > 10000:
            self.processed_message_ids.clear()
        return False

    def update_user_location(self, phone: str, lat: float, lon: float):
        """Update last known coordinates for farmer."""
        if phone not in self.user_sessions:
            self.user_sessions[phone] = {}
        self.user_sessions[phone]["lat"] = lat
        self.user_sessions[phone]["lon"] = lon

    def set_pending_note(self, phone: str, note: str):
        """Remember the farmer's last text/voice note so the next photo carries it."""
        if not note:
            return
        self.user_sessions.setdefault(phone, {})["pending_note"] = note

    def take_pending_note(self, phone: str) -> Optional[str]:
        """Read and clear the note — it belongs to one diagnosis, not to all of them."""
        return self.user_sessions.get(phone, {}).pop("pending_note", None)

    def set_user_language(self, phone: str, code: str):
        """Record a language the farmer explicitly chose.

        Explicit beats everything: it is the only layer that reflects a decision
        rather than an inference, so it is never overwritten by detection.
        """
        self.user_sessions.setdefault(phone, {})["language"] = code

    def get_user_language(self, phone: str) -> Optional[str]:
        """The language the farmer chose, or None if they never chose one."""
        return self.user_sessions.get(phone, {}).get("language")

    def set_detected_language(self, phone: str, code: str):
        """Remember what the farmer's own message sounded like.

        Kept separate from the chosen language and never promoted to it. It also
        has to persist: a farmer who sends a Hindi voice note and then a bare
        photo should get a Hindi reply to the photo, and the photo carries no
        language signal of its own.
        """
        if not code:
            return
        self.user_sessions.setdefault(phone, {})["detected_language"] = code

    def get_detected_language(self, phone: str) -> Optional[str]:
        return self.user_sessions.get(phone, {}).get("detected_language")

    def get_user_location(self, phone: str) -> Optional[tuple[float, float]]:
        """Retrieve last known coordinates for farmer."""
        session = self.user_sessions.get(phone, {})
        if "lat" in session and "lon" in session:
            return (session["lat"], session["lon"])
        return None

user_state_service = UserStateService()
