"""Tests fuer DF-HeyLou-Loyalty-Engine [CRUX-MK]. >=14 Tests."""

from __future__ import annotations

import sqlite3
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
    assert acc.tier == LoyaltyTier.SILVER
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
    e.record_booking("g@e.com", 100.0)
    e.record_booking("g@e.com", 200.0)
    e.record_booking("g@e.com", 100.0)
    acc = e.get_account("g@e.com")
    assert acc.tier == LoyaltyTier.GOLD
    assert acc.points >= TIER_THRESHOLDS[LoyaltyTier.GOLD]


def test_redeem_points_insufficient():
    """Test 6: Redeem mehr Punkte als vorhanden -> success=False."""
    e = LoyaltyEngine()
    e.record_booking("g@e.com", 50.0)
    r = e.redeem_points("g@e.com", 10000)
    assert r["success"] is False
    assert r["reason"] == "insufficient_points"


def test_redeem_points_success():
    """Test 7: Erfolgreicher Redeem."""
    e = LoyaltyEngine()
    e.record_booking("g@e.com", 200.0)
    r = e.redeem_points("g@e.com", 1000)
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


def test_personalization_record_preference_persists_to_sqlite(tmp_path):
    """Test 10: Preferences werden als echte SQLite-Events persistiert."""
    db_path = tmp_path / "prefs.sqlite3"
    p = PersonalizationEngine(db_path=db_path)
    pref = p.record_booking_preference("g@e.com", "deluxe", 2, 150.0)
    p.close()

    assert pref.n_bookings == 1
    assert pref.preferred_room_types["DELUXE"] == 1

    with sqlite3.connect(db_path) as db:
        row = db.execute(
            "SELECT guest_id_hash, room_type, duration_nights, amount_eur "
            "FROM booking_preferences"
        ).fetchone()

    assert row is not None
    assert row[1:] == ("DELUXE", 2, 150.0)
    assert "g@e.com" not in row[0]
    assert len(row[0]) == 32


def test_personalization_recommend_most_frequent():
    """Test 11: Recommend most-frequent room-type."""
    p = PersonalizationEngine()
    p.record_booking_preference("g@e.com", "STANDARD", 2, 100.0)
    p.record_booking_preference("g@e.com", "DELUXE", 2, 150.0)
    p.record_booking_preference("g@e.com", "DELUXE", 1, 130.0)
    assert p.recommend_room_type("g@e.com") == "DELUXE"
    p.close()


def test_personalization_invalid_duration_raises():
    """Test 12: Invalid duration raises."""
    p = PersonalizationEngine()
    with pytest.raises(ValueError):
        p.record_booking_preference("g@e.com", "DBL", 0, 100.0)
    p.close()


def test_personalization_mission_discriminates_adversarial_history(tmp_path):
    """Test 13: Gegenteilige echte Historie erzeugt anderen Output."""
    db_path = tmp_path / "counterfactual.sqlite3"
    p = PersonalizationEngine(db_path=db_path)

    for room_type, amount in [
        ("STANDARD", 95.0),
        ("DELUXE", 180.0),
        ("DELUXE", 175.0),
    ]:
        p.record_booking_preference("loyal@example.com", room_type, 2, amount)
    loyal_output = p.recommend_room_type("loyal@example.com")

    for room_type, amount in [
        ("DELUXE", 180.0),
        ("STANDARD", 95.0),
        ("STANDARD", 90.0),
    ]:
        p.record_booking_preference("counter@example.com", room_type, 2, amount)
    adversarial_output = p.recommend_room_type("counter@example.com")
    p.close()

    reopened = PersonalizationEngine(db_path=db_path)
    persisted_loyal_output = reopened.recommend_room_type("loyal@example.com")
    persisted_adversarial_output = reopened.recommend_room_type("counter@example.com")
    reopened.close()

    assert loyal_output == "DELUXE"
    assert adversarial_output == "STANDARD"
    assert persisted_loyal_output == loyal_output
    assert persisted_adversarial_output == adversarial_output
    assert persisted_loyal_output != persisted_adversarial_output


def test_personalization_rejects_empty_room_type():
    """Test 14: Empty room-type raises."""
    p = PersonalizationEngine()
    with pytest.raises(ValueError):
        p.record_booking_preference("g@e.com", "   ", 1, 100.0)
    p.close()


def test_reward_available_for_silver():
    """Test 15: Silver-Guest (2000 pts) hat Discount-Rewards."""
    r = RewardCalculator()
    avail = r.available_rewards(2000)
    assert len(avail) >= 3
    assert any(reward.type == RewardType.DISCOUNT_EUR for reward in avail)


def test_reward_no_free_night_below_threshold():
    """Test 16: < 5000 Punkte = kein Free-Night."""
    r = RewardCalculator()
    avail = r.available_rewards(2000)
    assert not any(reward.type == RewardType.FREE_NIGHT for reward in avail)


def test_orchestrator_processes_booking(tmp_path):
    """Test 17: Orchestrator end-to-end."""
    orch = LoyaltyOrchestrator(sandbox_mode=True)
    orch.audit = AuditLogger(audit_path=tmp_path / "orch-audit.jsonl", secret="s")
    r = orch.process_booking("g@e.com", 150.0, "DELUXE", 2)
    assert r.points > 0
    assert r.tier in ("bronze", "silver", "gold")
    assert r.audit_hash != ""


def test_audit_chain_loyalty(tmp_path):
    """Test 18: Audit-Chain valid."""
    a = AuditLogger(audit_path=tmp_path / "a.jsonl", secret="s")
    a.append({"e": "1"})
    a.append({"e": "2"})
    assert a.verify_chain()["valid"] is True
