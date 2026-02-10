"""Central configuration loader for FE-Analyst."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Project root is the parent of the src/ directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")


def load_settings() -> dict:
    """Load settings from configs/settings.yaml."""
    settings_path = PROJECT_ROOT / "configs" / "settings.yaml"
    with open(settings_path) as f:
        return yaml.safe_load(f)


SETTINGS = load_settings()


# --- API Keys ---
class Keys:
    ANTHROPIC = os.getenv("ANTHROPIC_API_KEY", "")
    FINNHUB = os.getenv("FINNHUB_API_KEY", "")
    FRED = os.getenv("FRED_API_KEY", "")
    SIMFIN = os.getenv("SIMFIN_API_KEY", "")
    FMP = os.getenv("FMP_API_KEY", "")
    TWELVE_DATA = os.getenv("TWELVE_DATA_API_KEY", "")
    ALPACA_KEY = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY", "")
    REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
    REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "FE-analyst/1.0")
    BLS = os.getenv("BLS_API_KEY", "")
    SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "")


# --- Paths ---
class Paths:
    ROOT = PROJECT_ROOT
    DATA_RAW = PROJECT_ROOT / "data" / "raw"
    DATA_CACHE = PROJECT_ROOT / "data" / "cache"
    DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
    REPORTS_OUTPUT = PROJECT_ROOT / "reports" / "output"
    REPORTS_TEMPLATES = PROJECT_ROOT / "reports" / "templates"
    MODELS = PROJECT_ROOT / "models"
