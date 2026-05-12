"""Personalization-Engine [CRUX-MK].

Per-Guest-Preference-Optimization basierend auf Booking-Historie.

DSGVO-Schutz: nur aggregierte Preferences, kein PII.

[CRUX-MK]
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class GuestPreference:
    """Aggregierte Preferences pro Guest (hashed-id)."""
    guest_id_hash: str
    preferred_room_types: dict[str, int] = field(default_factory=dict)  # room_type -> count
    preferred_durations: list[int] = field(default_factory=list)
    avg_booking_value_eur: float = 0.0
    n_bookings: int = 0


class PersonalizationEngine:
    """Aggregiert Guest-Preferences."""

    def __init__(self):
        self._preferences: dict[str, GuestPreference] = {}

    def _hash_guest(self, guest_email: str) -> str:
        return hashlib.sha256(guest_email.encode()).hexdigest()[:32]

    def record_booking_preference(
        self,
        guest_email: str,
        room_type: str,
        duration_nights: int,
        amount_eur: float,
    ) -> GuestPreference:
        """Booking-Preference aggregieren."""
        if duration_nights <= 0 or amount_eur < 0:
            raise ValueError("Invalid preference data")
        guest_id = self._hash_guest(guest_email)
        p = self._preferences.get(guest_id) or GuestPreference(guest_id_hash=guest_id)

        p.preferred_room_types[room_type] = p.preferred_room_types.get(room_type, 0) + 1
        p.preferred_durations.append(duration_nights)
        # Running average
        p.avg_booking_value_eur = (
            (p.avg_booking_value_eur * p.n_bookings + amount_eur) / (p.n_bookings + 1)
        )
        p.n_bookings += 1
        self._preferences[guest_id] = p
        return p

    def recommend_room_type(self, guest_email: str) -> str | None:
        """Recommend most-frequent room-type."""
        guest_id = self._hash_guest(guest_email)
        p = self._preferences.get(guest_id)
        if not p or not p.preferred_room_types:
            return None
        return Counter(p.preferred_room_types).most_common(1)[0][0]
