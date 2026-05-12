# DF-HeyLou-Loyalty-Engine [CRUX-MK]

**Welle-40 Profit-Layer #3:** Hotel-Loyalty-Programm fuer Direct-Booking-Wiederkehr.

## Status
- Version: 0.1.0-SKELETON
- Phase: PRE-PRODUCTION-CONDITIONAL
- K_0-Touch: LOW (Loyalty-Punkte sind Reward-Bookkeeping, kein direkter Charge)

## Architektur
```
src/
├── loyalty_engine.py        # Punkte-System + Tiers Bronze/Silver/Gold
├── personalization_engine.py # Per-Guest-Preference-Optimization
├── reward_calculator.py      # Punkte → Discount/Upgrade
├── loyalty_orchestrator.py
└── audit_logger.py
```

## Pflicht-Properties
- DSGVO-konforme Guest-Persistence (Hash-IDs, kein PII-Storage)
- Sandbox-Default (`DF_HEYLOU_LOYALTY_REAL_ENABLED=false`)

## rho-Gain
Year-1 Hildesheim: +5-15k EUR/J durch Repeat-Booking-Steigerung.
Year-3 5-Hotel: +50-150k EUR/J.

[CRUX-MK]
