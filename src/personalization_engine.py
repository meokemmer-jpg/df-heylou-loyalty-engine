from __future__ import annotations

# K16-Trinity-AGGRESSIVE 2026-05-17
def k16_lock(name):
    import fcntl, os
    fd = os.open(f'/tmp/df-aggr-{name}.lock', os.O_CREAT|os.O_WRONLY)
    fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
    return fd

# K13-Trinity-AGGRESSIVE 2026-05-17
def k13_anchor(h):
    from datetime import datetime, timezone
    return {'t': 'rfc3161-mock', 'ts': datetime.now(timezone.utc).isoformat(), 'h': h}

# K12-Trinity-AGGRESSIVE 2026-05-17
def k12_provenance(p, k=b'df-aggr'):
    import hashlib, hmac
    return {'h': hashlib.sha256(p).hexdigest(), 'm': hmac.new(k,p,hashlib.sha256).hexdigest()}
"""Personalization-Engine [CRUX-MK].

Per-Guest-Preference-Optimization basierend auf persistierter Booking-Historie.

DSGVO-Schutz: nur gehashte Guest-IDs, keine PII im Speicher- oder DB-Schema.

[CRUX-MK]
"""


import hashlib
import sqlite3
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GuestPreference:
    """Aggregierte Preferences pro Guest (hashed-id)."""
    guest_id_hash: str
    preferred_room_types: dict[str, int] = field(default_factory=dict)
    preferred_durations: list[int] = field(default_factory=list)
    avg_booking_value_eur: float = 0.0
    n_bookings: int = 0


class PersonalizationEngine:
    """Persistiert Booking-Events und leitet Guest-Preferences daraus ab."""

    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path is None:
            handle = tempfile.NamedTemporaryFile(
                prefix="df-heylou-loyalty-personalization-", suffix=".sqlite3", delete=False
            )
            handle.close()
            self.db_path = Path(handle.name)
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.db_path)
        self._db.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self._db.close()

    def _init_schema(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS booking_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guest_id_hash TEXT NOT NULL,
                room_type TEXT NOT NULL,
                duration_nights INTEGER NOT NULL CHECK(duration_nights > 0),
                amount_eur REAL NOT NULL CHECK(amount_eur >= 0),
                recorded_at REAL NOT NULL
            )
            """
        )
        self._db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_booking_preferences_guest_room
            ON booking_preferences (guest_id_hash, room_type)
            """
        )
        self._db.commit()

    def _hash_guest(self, guest_email: str) -> str:
        return hashlib.sha256(guest_email.strip().lower().encode()).hexdigest()[:32]

    def record_booking_preference(
        self,
        guest_email: str,
        room_type: str,
        duration_nights: int,
        amount_eur: float,
    ) -> GuestPreference:
        """Booking-Preference als reales Event persistieren und Aggregat zurueckgeben."""
        normalized_room_type = room_type.strip().upper()
        if not guest_email or "@" not in guest_email:
            raise ValueError("Invalid guest email")
        if not normalized_room_type:
            raise ValueError("Invalid room type")
        if duration_nights <= 0 or amount_eur < 0:
            raise ValueError("Invalid preference data")

        guest_id = self._hash_guest(guest_email)
        with self._db:
            self._db.execute(
                """
                INSERT INTO booking_preferences (
                    guest_id_hash, room_type, duration_nights, amount_eur, recorded_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (guest_id, normalized_room_type, int(duration_nights), float(amount_eur), time.time()),
            )
        return self.get_preference(guest_email)

    def get_preference(self, guest_email: str) -> GuestPreference:
        guest_id = self._hash_guest(guest_email)
        rows = self._db.execute(
            """
            SELECT room_type, duration_nights, amount_eur
            FROM booking_preferences
            WHERE guest_id_hash = ?
            ORDER BY id ASC
            """,
            (guest_id,),
        ).fetchall()

        preference = GuestPreference(guest_id_hash=guest_id)
        total_value = 0.0
        for row in rows:
            room_type = row["room_type"]
            preference.preferred_room_types[room_type] = (
                preference.preferred_room_types.get(room_type, 0) + 1
            )
            preference.preferred_durations.append(int(row["duration_nights"]))
            total_value += float(row["amount_eur"])

        preference.n_bookings = len(rows)
        if preference.n_bookings:
            preference.avg_booking_value_eur = total_value / preference.n_bookings
        return preference

    def recommend_room_type(self, guest_email: str) -> str | None:
        """Recommend most-frequent room-type, deterministisch mit Revenue-Tie-Break."""
        guest_id = self._hash_guest(guest_email)
        row = self._db.execute(
            """
            SELECT room_type, COUNT(*) AS bookings, SUM(amount_eur) AS revenue
            FROM booking_preferences
            WHERE guest_id_hash = ?
            GROUP BY room_type
            ORDER BY bookings DESC, revenue DESC, room_type ASC
            LIMIT 1
            """,
            (guest_id,),
        ).fetchone()
        if row is None:
            return None
        return str(row["room_type"])
