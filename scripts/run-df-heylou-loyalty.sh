#!/bin/bash
# DF-HeyLou-Loyalty-Engine Runner [CRUX-MK]
set -euo pipefail
LOCK_DIR="/tmp/df-heylou-loyalty.lock"
LOCK_AGE_LIMIT_S=21600
if [ -d "$LOCK_DIR" ]; then
  LOCK_AGE_S=$(( $(date +%s) - $(stat -f %m "$LOCK_DIR" 2>/dev/null || echo 0) ))
  if [ "$LOCK_AGE_S" -gt "$LOCK_AGE_LIMIT_S" ]; then rm -rf "$LOCK_DIR"; else echo "K16-VETO"; exit 3; fi
fi
mkdir "$LOCK_DIR" 2>/dev/null || { echo "K16-VETO Race"; exit 3; }
echo "$$" > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT INT TERM
[ -f /tmp/df-heylou-loyalty.stop ] && exit 0
cd "$(dirname "$0")/.."
python3 -m src.loyalty_orchestrator "$@"
