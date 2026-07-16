#!/usr/bin/env python3
"""Standalone daily bubble-monitor digest — send the email WITHOUT the dashboard.

The FastAPI server's in-process APScheduler only fires while the server is
running. If you don't keep the dashboard up 24/7 (or it's on a scale-to-zero
host), the daily email never sends. Run THIS from OS cron / launchd instead —
it refreshes the snapshot, generates the AI note, and emails the digest, then
exits. No server required.

Usage:
    /path/to/venv/bin/python dashboard/api/send_daily_digest.py

macOS launchd (recommended — runs even after sleep, at next wake):
    Create ~/Library/LaunchAgents/com.fe-analyst.bubble-digest.plist with a
    StartCalendarInterval for your preferred hour, ProgramArguments =
    [<venv python>, <this script>].  Then: launchctl load <plist>.

Linux cron:
    0 10 * * *  cd /path/to/FE-analyst && dashboard/api/venv/bin/python dashboard/api/send_daily_digest.py
"""

import sys
import logging
from pathlib import Path

# Make the repo importable (src.*) and load .env exactly like the server does.
API_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = API_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(API_DIR))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("daily_digest")


def main() -> int:
    import macro_monitor

    # Restore prior state from GCS (so trip-detection isn't "first run" every time).
    macro_monitor.restore_from_gcs()
    snap = macro_monitor.refresh_and_store(send_email=True, digest=True)
    macro_monitor.backup_to_gcs()
    log.info(
        "Digest sent: overall=%s sell_now=%s topmodel=%s/%s ai_note=%s",
        snap.get("overall_status"),
        snap.get("sell_now"),
        snap.get("top_model_triggered"),
        snap.get("top_model_total"),
        "yes" if snap.get("ai_commentary") else "no",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
