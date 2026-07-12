"""Persisted campaign->ZIP mapping history for smarter auto-selection."""

from __future__ import annotations

import json
from pathlib import Path


def default_mapping_history_path() -> Path:
    """Return the path for the persistent campaign mapping history file."""
    return Path.home() / ".campaign_suppression_manager" / "mapping_history.json"


def _canonicalize_history_value(raw_value: str) -> str:
    value = str(raw_value).strip()
    if not value:
        return ""
    return Path(value).stem


def load_mapping_history(history_path: Path | None = None) -> dict[str, tuple[str, ...]]:
    """Load prior campaign-to-ZIP mappings from the user's local history store."""
    path = history_path or default_mapping_history_path()
    if not path.exists():
        return {}

    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    history: dict[str, tuple[str, ...]] = {}
    if not isinstance(raw_data, dict):
        return history

    for campaign_key, saved_values in raw_data.items():
        if not isinstance(campaign_key, str) or not isinstance(saved_values, list):
            continue
        cleaned = tuple(
            canonical_value
            for canonical_value in (
                _canonicalize_history_value(value)
                for value in saved_values
                if isinstance(value, str)
            )
            if canonical_value
        )
        if cleaned:
            history[campaign_key.strip().lower()] = tuple(dict.fromkeys(cleaned))

    return history


def save_mapping_history(history: dict[str, tuple[str, ...]], history_path: Path | None = None) -> Path:
    """Persist campaign history data to disk."""
    path = history_path or default_mapping_history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw_data = {campaign_key: list(values) for campaign_key, values in history.items()}
    path.write_text(json.dumps(raw_data, indent=2), encoding="utf-8")
    return path


def merge_mapping_history(
    existing_history: dict[str, tuple[str, ...]],
    new_entries: dict[str, str],
) -> dict[str, tuple[str, ...]]:
    """Merge new campaign mapping examples into the existing history."""
    merged = {campaign_key: list(values) for campaign_key, values in existing_history.items()}
    for campaign_key, new_value in new_entries.items():
        campaign_key = campaign_key.strip().lower()
        canonical_value = _canonicalize_history_value(new_value)
        if not campaign_key or not canonical_value:
            continue
        values = merged.setdefault(campaign_key, [])
        if canonical_value not in values:
            values.insert(0, canonical_value)
    return {campaign_key: tuple(values) for campaign_key, values in merged.items()}
