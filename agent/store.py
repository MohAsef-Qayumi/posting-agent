"""Persistent state kept as JSON files in state/ (committed back to the repo by the workflows)."""
import json
import secrets
import shutil
from datetime import timedelta
from pathlib import Path

from .config import DRAFTS_DIR, STATE_DIR, now

HISTORY_FILE = STATE_DIR / "history.json"
TELEGRAM_FILE = STATE_DIR / "telegram.json"


def _read(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── drafts ────────────────────────────────────────────────────
def new_draft_id() -> str:
    return f"{now():%Y-%m-%d}-{secrets.token_hex(2)}"


def draft_dir(draft_id: str) -> Path:
    return DRAFTS_DIR / draft_id


def save_draft(draft: dict) -> None:
    _write(draft_dir(draft["id"]) / "draft.json", draft)


def load_draft(draft_id: str) -> dict | None:
    return _read(draft_dir(draft_id) / "draft.json", None)


def slide_paths(draft: dict) -> list[Path]:
    return [draft_dir(draft["id"]) / name for name in draft.get("images", [])]


def all_drafts() -> list[dict]:
    if not DRAFTS_DIR.exists():
        return []
    drafts = [_read(p / "draft.json", None) for p in sorted(DRAFTS_DIR.iterdir()) if p.is_dir()]
    return [d for d in drafts if d]


def prune_drafts(keep_days: int = 7) -> None:
    """Delete draft folders (and their images) older than keep_days to keep the repo small."""
    cutoff = f"{now() - timedelta(days=keep_days):%Y-%m-%d}"
    for d in all_drafts():
        if d["id"][:10] < cutoff:
            shutil.rmtree(draft_dir(d["id"]), ignore_errors=True)


# ── history ───────────────────────────────────────────────────
def history() -> list[dict]:
    return _read(HISTORY_FILE, [])


def add_history(entry: dict) -> None:
    items = history()
    items.append(entry)
    _write(HISTORY_FILE, items[-500:])


def recent_topics(days: int) -> list[str]:
    cutoff = f"{now() - timedelta(days=days):%Y-%m-%d}"
    return [f"[{h['pillar']}] {h['topic']}" for h in history() if h["date"] >= cutoff]


# ── telegram offset ───────────────────────────────────────────
def telegram_offset() -> int:
    return _read(TELEGRAM_FILE, {}).get("offset", 0)


def set_telegram_offset(offset: int) -> None:
    _write(TELEGRAM_FILE, {"offset": offset})
