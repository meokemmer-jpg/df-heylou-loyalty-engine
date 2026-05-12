"""Reward-Calculator [CRUX-MK].

Berechnet konkrete Rewards (Discount, Upgrade, Free-Night) aus Punkten + Tier.

Deterministisch, kein LLM.

[CRUX-MK]
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RewardType(str, Enum):
    DISCOUNT_EUR = "discount_eur"
    ROOM_UPGRADE = "room_upgrade"
    FREE_NIGHT = "free_night"
    EARLY_CHECKIN = "early_checkin"
    LATE_CHECKOUT = "late_checkout"


@dataclass
class RewardItem:
    type: RewardType
    cost_points: int
    value_eur: float
    description: str


# Static Reward-Catalog (deterministisch, kein dynamic-pricing)
REWARD_CATALOG: list[RewardItem] = [
    RewardItem(RewardType.DISCOUNT_EUR, 500, 5.0, "5 EUR Discount voucher"),
    RewardItem(RewardType.DISCOUNT_EUR, 1000, 10.0, "10 EUR Discount voucher"),
    RewardItem(RewardType.DISCOUNT_EUR, 2500, 25.0, "25 EUR Discount voucher"),
    RewardItem(RewardType.ROOM_UPGRADE, 1500, 30.0, "Room-Upgrade (1 Kategorie)"),
    RewardItem(RewardType.FREE_NIGHT, 5000, 99.0, "1 Free-Night (Standard-Room)"),
    RewardItem(RewardType.EARLY_CHECKIN, 200, 0.0, "Early Check-In (4h)"),
    RewardItem(RewardType.LATE_CHECKOUT, 200, 0.0, "Late Check-Out (4h)"),
]


class RewardCalculator:
    def available_rewards(self, current_points: int) -> list[RewardItem]:
        """Rewards die der Guest sich leisten kann."""
        return [r for r in REWARD_CATALOG if r.cost_points <= current_points]

    def affordable_max_value(self, current_points: int) -> float:
        """Max EUR-Value der aktuell verfuegbaren Rewards."""
        rewards = self.available_rewards(current_points)
        if not rewards:
            return 0.0
        return max(r.value_eur for r in rewards)
