"""Loyalty-Engine [CRUX-MK].

Punkte-System mit Tiers Bronze/Silver/Gold.

K_0-Schutz: Punkte-Berechnung deterministisch, kein LLM.
DSGVO: Guest-ID = SHA256-Hash, kein PII-Storage.

[CRUX-MK]
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LoyaltyTier(str, Enum):
    BRONZE = "bronze"      # 0-999 Punkte
    SILVER = "silver"      # 1000-4999 Punkte
    GOLD = "gold"          # 5000+ Punkte


TIER_THRESHOLDS = {
    LoyaltyTier.BRONZE: 0,
    LoyaltyTier.SILVER: 1000,
    LoyaltyTier.GOLD: 5000,
}


@dataclass
class LoyaltyAccount:
    guest_id_hash: str  # SHA256-Hash (DSGVO)
    points: int = 0
    tier: LoyaltyTier = LoyaltyTier.BRONZE
    total_direct_bookings: int = 0
    total_revenue_eur: float = 0.0
    first_seen_ts: float = field(default_factory=time.time)
    last_update_ts: float = field(default_factory=time.time)

    def update_tier(self) -> None:
        """Update tier basierend auf points (deterministisch)."""
        if self.points >= TIER_THRESHOLDS[LoyaltyTier.GOLD]:
            self.tier = LoyaltyTier.GOLD
        elif self.points >= TIER_THRESHOLDS[LoyaltyTier.SILVER]:
            self.tier = LoyaltyTier.SILVER
        else:
            self.tier = LoyaltyTier.BRONZE


class LoyaltyEngine:
    """Loyalty-Engine: Punkte-Berechnung + Tier-Management.

    Punkte-Rate: 10 Punkte pro Euro Direct-Booking-Revenue.
    Tier-Multiplier: Bronze=1.0, Silver=1.5, Gold=2.0.
    """

    BASE_POINTS_PER_EUR = 10
    TIER_MULTIPLIERS = {
        LoyaltyTier.BRONZE: 1.0,
        LoyaltyTier.SILVER: 1.5,
        LoyaltyTier.GOLD: 2.0,
    }

    def __init__(self, sandbox_mode: Optional[bool] = None):
        if sandbox_mode is None:
            sandbox_mode = (
                os.environ.get("DF_HEYLOU_LOYALTY_REAL_ENABLED", "false").lower() != "true"
            )
        self.sandbox_mode = sandbox_mode
        self._accounts: dict[str, LoyaltyAccount] = {}

    def _hash_guest(self, guest_email: str) -> str:
        """SHA256-Hash fuer DSGVO."""
        return hashlib.sha256(guest_email.encode()).hexdigest()[:32]

    def record_booking(
        self,
        guest_email: str,
        amount_eur: float,
    ) -> LoyaltyAccount:
        """Booking erfassen + Punkte vergeben."""
        if amount_eur < 0:
            raise ValueError(f"Invalid amount: {amount_eur}")

        guest_id = self._hash_guest(guest_email)
        acc = self._accounts.get(guest_id) or LoyaltyAccount(guest_id_hash=guest_id)

        # Tier-Multiplier auf aktueller Tier (NICHT future-Tier)
        multiplier = self.TIER_MULTIPLIERS[acc.tier]
        points_earned = int(amount_eur * self.BASE_POINTS_PER_EUR * multiplier)

        acc.points += points_earned
        acc.total_direct_bookings += 1
        acc.total_revenue_eur += amount_eur
        acc.last_update_ts = time.time()
        acc.update_tier()

        self._accounts[guest_id] = acc
        return acc

    def redeem_points(self, guest_email: str, points: int) -> dict:
        """Punkte einlösen (Discount-Voucher)."""
        if points <= 0:
            raise ValueError(f"Invalid points: {points}")

        guest_id = self._hash_guest(guest_email)
        acc = self._accounts.get(guest_id)
        if not acc:
            return {"success": False, "reason": "guest_not_found"}

        if acc.points < points:
            return {
                "success": False,
                "reason": "insufficient_points",
                "current": acc.points,
                "requested": points,
            }

        # 100 Punkte = 1 EUR Discount
        discount_eur = round(points / 100.0, 2)
        acc.points -= points
        acc.update_tier()  # Tier kann sich nach Redeem aendern
        acc.last_update_ts = time.time()

        return {
            "success": True,
            "discount_eur": discount_eur,
            "remaining_points": acc.points,
            "tier": acc.tier.value,
        }

    def get_account(self, guest_email: str) -> Optional[LoyaltyAccount]:
        return self._accounts.get(self._hash_guest(guest_email))
