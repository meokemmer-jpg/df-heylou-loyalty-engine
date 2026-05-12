"""Tests fuer DF-HeyLou-Loyalty-Engine [CRUX-MK]. >=14 Tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.loyalty_engine import LoyaltyEngine, LoyaltyTier, TIER_THRESHOLDS
from src.personalization_engine import PersonalizationEngine
from src.reward_calculator import RewardCalculator, RewardType
from src.audit_logger import AuditLogger
from src.loyalty_orchestrator import LoyaltyOrchestrator


def test_loyalty_default_sandbox():
    """Test 1: Default sandbox-mode."""
    e = LoyaltyEngine()
    assert e.sandbox_mode is True


def test_record_booking_bronze():
    """Test 2: New guest startet bronze, 200 EUR = 2000 Punkte."""
    e = LoyaltyEngine()
    acc = e.record_booking("g@example.com", 200.0)
    assert acc.tier == LoyaltyTier.SILVER  # 2000 >= 1000
    assert acc.points == 2000


def test_record_booking_negative_amount_raises():
    """Test 3: Negative amount raises."""
    e = LoyaltyEngine()
    with pytest.raises(ValueError):
        e.record_booking("g@example.com", -10.0)


def test_dsgvo_guest_hash():
    """Test 4: DSGVO - guest_id ist Hash, kein PII."""
    e = LoyaltyEngine()
    acc = e.record_booking("very.private@example.com", 100.0)
    assert "very.private" not in acc.guest_id_hash
    assert "@" not in acc.guest_id_hash


def test_tier_progression_to_gold():
    """Test 5: Mehrere Bookings = Tier-Aufstieg zu Gold."""
    e = LoyaltyEngine()
    # 100 EUR Booking als Bronze = 1000 Punkte = silber-level
    # Brauchen 5000 fuer gold
    e.record_booking("g@e.com", 100.0)  # 1000 (silver, mult 1.0 weil noch Bronze)
    e.record_booking("g@e.com", 200.0)  # +3000 (silver mult 1.5) → 4000
    e.record_booking("g@e.com", 100.0)  # +1500 (silver mult 1.5) → 5500
    acc = e.get_account("g@e.com")
    assert acc.tier == LoyaltyTier.GOLD


def test_redeem_points_insufficient():
    """Test 6: Redeem mehr Punkte als vorhanden → success=False."""
    e = LoyaltyEngine()
    e.record_booking("g@e.com", 50.0)
    r = e.redeem_points("g@e.com", 10000)
    assert r["success"] is False
    assert r["reason"] == "insufficient_points"


def test_redeem_points_success():
    """Test 7: Erfolgreicher Redeem."""
    e = LoyaltyEngine()
    e.record_booking("g@e.com", 200.0)  # 2000 Punkte
    r = e.redeem_points("g@e.com", 1000)  # 10 EUR Discount
    assert r["success"] is True
    assert r["discount_eur"] == 10.0
    assert r["remaining_points"] == 1000


def test_redeem_zero_points_raises():
    """Test 8: Redeem 0 Punkte raises."""
    e = LoyaltyEngine()
    e.record_booking("g@e.com", 100.0)
    with pytest.raises(ValueError):
        e.redeem_points("g@e.com", 0)


def test_get_account_unknown_guest():
    """Test 9: Unknown guest returns None."""
    e = LoyaltyEngine()
    assert e.get_account("never_seen@example.com") is None


# Personalization
def test_personalization_record_preference():
    """Test 10: Preferences werden aggregiert."""
    p = PersonalizationEngine()
    pref = p.record_booking_preference("g@e.com", "DELUXE", 2, 150.0)
    assert pref.n_bookings == 1
    assert pref.preferred_room_types["DELUXE"] == 1


def test_personalization_recommend_most_frequent():
    """Test 11: Recommend most-frequent room-type."""
    p = PersonalizationEngine()
    p.record_booking_preference("g@e.com", "STANDARD", 2, 100.0)
    p.record_booking_preference("g@e.com", "DELUXE", 2, 150.0)
    p.record_booking_preference("g@e.com", "DELUXE", 1, 130.0)
    assert p.recommend_room_type("g@e.com") == "DELUXE"


def test_personalization_invalid_duration_raises():
    """Test 12: Invalid duration raises."""
    p = PersonalizationEngine()
    with pytest.raises(ValueError):
        p.record_booking_preference("g@e.com", "DBL", 0, 100.0)


# Reward
def test_reward_available_for_silver():
    """Test 13: Silver-Guest (2000 pts) hat Discount-Rewards."""
    r = RewardCalculator()
    avail = r.available_rewards(2000)
    assert len(avail) >= 3
    assert any(reward.type == RewardType.DISCOUNT_EUR for reward in avail)


def test_reward_no_free_night_below_threshold():
    """Test 14: < 5000 Punkte = kein Free-Night."""
    r = RewardCalculator()
    avail = r.available_rewards(2000)
    assert not any(reward.type == RewardType.FREE_NIGHT for reward in avail)


# Orchestrator + Audit
def test_orchestrator_processes_booking():
    """Test 15: Orchestrator end-to-end."""
    orch = LoyaltyOrchestrator(sandbox_mode=True)
    r = orch.process_booking("g@e.com", 150.0, "DELUXE", 2)
    assert r.points > 0
    assert r.tier in ("bronze", "silver", "gold")
    assert r.audit_hash != ""


def test_audit_chain_loyalty(tmp_path):
    """Test 16: Audit-Chain valid."""
    a = AuditLogger(audit_path=tmp_path / "a.jsonl", secret="s")
    a.append({"e": "1"})
    a.append({"e": "2"})
    assert a.verify_chain()["valid"] is True
