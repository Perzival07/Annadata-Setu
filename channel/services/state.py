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

    def get_user_location(self, phone: str) -> Optional[tuple[float, float]]:
        """Retrieve last known coordinates for farmer."""
        session = self.user_sessions.get(phone, {})
        if "lat" in session and "lon" in session:
            return (session["lat"], session["lon"])
        return None

user_state_service = UserStateService()
