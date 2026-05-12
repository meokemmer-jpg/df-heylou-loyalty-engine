"""Loyalty-Orchestrator [CRUX-MK]."""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LoyaltyOrchestratorResult:
    guest_hash: str
    points: int
    tier: str
    audit_hash: str
    sandbox_mode: bool


class LoyaltyOrchestrator:
    def __init__(self, sandbox_mode: Optional[bool] = None):
        from . import loyalty_engine, personalization_engine, reward_calculator, audit_logger
        if sandbox_mode is None:
            sandbox_mode = (
                os.environ.get("DF_HEYLOU_LOYALTY_REAL_ENABLED", "false").lower() != "true"
            )
        self.sandbox_mode = sandbox_mode
        self.engine = loyalty_engine.LoyaltyEngine(sandbox_mode=sandbox_mode)
        self.personalize = personalization_engine.PersonalizationEngine()
        self.rewards = reward_calculator.RewardCalculator()
        self.audit = audit_logger.AuditLogger()

    def process_booking(
        self,
        guest_email: str,
        amount_eur: float,
        room_type: str,
        duration_nights: int,
    ) -> LoyaltyOrchestratorResult:
        """Process Loyalty-Update aus Booking."""
        acc = self.engine.record_booking(guest_email, amount_eur)
        self.personalize.record_booking_preference(
            guest_email, room_type, duration_nights, amount_eur
        )
        audit_hash = self.audit.append({
            "type": "loyalty_booking",
            "guest_id_hash": acc.guest_id_hash,
            "amount_eur": amount_eur,
            "points_after": acc.points,
            "tier": acc.tier.value,
            "sandbox_mode": self.sandbox_mode,
        })
        return LoyaltyOrchestratorResult(
            guest_hash=acc.guest_id_hash,
            points=acc.points,
            tier=acc.tier.value,
            audit_hash=audit_hash,
            sandbox_mode=self.sandbox_mode,
        )


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO)
    stop_flag = Path("/tmp/df-heylou-loyalty.stop")
    if stop_flag.exists():
        return 0
    orch = LoyaltyOrchestrator()
    r = orch.process_booking("demo@heylou.example", 200.0, "STANDARD-DOUBLE", 2)
    logger.info(f"Loyalty processed: {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
