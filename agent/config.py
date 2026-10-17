"""Loads config.yaml and environment secrets."""
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
DRAFTS_DIR = STATE_DIR / "drafts"
TZ = ZoneInfo("Asia/Karachi")  # Pakistan time (UTC+5)

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # optional locally, absent in the lightweight CI job
    pass


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def env(name: str, required: bool = True) -> str:
    value = os.environ.get(name, "").strip()
    if required and not value:
        raise RuntimeError(f"Missing environment variable / GitHub secret: {name}")
    return value


def now() -> datetime:
    return datetime.now(TZ)
