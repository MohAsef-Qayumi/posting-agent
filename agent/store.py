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
# One file per draft (state/history/<draft_id>.json) so the generate and process
# workflows can save state at the same time without git merge conflicts.
HISTORY_DIR = STATE_DIR / "history"


def history() -> list[dict]:
    items = _read(HISTORY_FILE, [])  # legacy single-file history
    if HISTORY_DIR.exists():
        items += [_read(p, None) for p in sorted(HISTORY_DIR.glob("*.json"))]
    return sorted((h for h in items if h), key=lambda h: h["draft_id"])


def add_history(entry: dict) -> None:
    _write(HISTORY_DIR / f"{entry['draft_id']}.json", entry)


def recent_topics(days: int) -> list[str]:
    cutoff = f"{now() - timedelta(days=days):%Y-%m-%d}"
    return [f"[{h['pillar']}] {h['topic']}" for h in history() if h["date"] >= cutoff]


# ── telegram ──────────────────────────────────────────────────
def telegram_offset() -> int:
    return _read(TELEGRAM_FILE, {}).get("offset", 0)


def set_telegram_offset(offset: int) -> None:
    data = _read(TELEGRAM_FILE, {})
    data["offset"] = max(offset, data.get("offset", 0))
    _write(TELEGRAM_FILE, data)


def seen_updates() -> set[int]:
    """Update ids already handled in instant mode (the worker's queue may briefly return them again)."""
    return set(_read(TELEGRAM_FILE, {}).get("seen", []))


def mark_seen(update_id: int) -> None:
    data = _read(TELEGRAM_FILE, {})
    data["seen"] = (data.get("seen", []) + [update_id])[-300:]
    _write(TELEGRAM_FILE, data)


# ── misc small state (e.g. Threads token renewal) ─────────────
def get_state(name: str, default):
    return _read(STATE_DIR / f"{name}.json", default)


def set_state(name: str, data) -> None:
    _write(STATE_DIR / f"{name}.json", data)
