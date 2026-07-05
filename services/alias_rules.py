"""Explicit campaign alias rules for ZIP mapping."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def default_alias_rules_path() -> Path:
    """Return the built-in alias training file path."""

    return Path(__file__).resolve().parents[1] / "config" / "campaign_aliases.csv"


def load_alias_rules(alias_rules_path: Path | None = None) -> dict[str, tuple[str, ...]]:
    """Load explicit campaign aliases from CSV or JSON.

    CSV format is preferred because it is easier to maintain as a training file.
    Supported CSV columns:
    - campaign_key
    - alias

    JSON remains supported for backward compatibility with a mapping of campaign_key -> alias list.
    """

    path = alias_rules_path or default_alias_rules_path()
    if not path.exists():
        fallback_json = path.with_suffix(".json")
        if fallback_json.exists():
            path = fallback_json
        else:
            return {}

    if path.suffix.lower() == ".csv":
        return _load_alias_rules_from_csv(path)

    return _load_alias_rules_from_json(path)


def _load_alias_rules_from_csv(path: Path) -> dict[str, tuple[str, ...]]:
    try:
        raw_rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    except OSError:
        return {}

    alias_rules: dict[str, list[str]] = {}
    for row in raw_rows:
        if not isinstance(row, dict):
            continue

        campaign_key = str(row.get("campaign_key", "")).strip().lower()
        alias_value = str(row.get("alias", "")).strip()
        if not campaign_key or not alias_value:
            continue

        alias_rules.setdefault(campaign_key, []).append(alias_value)

    return {campaign_key: tuple(aliases) for campaign_key, aliases in alias_rules.items() if aliases}


def _load_alias_rules_from_json(path: Path) -> dict[str, tuple[str, ...]]:
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    alias_rules: dict[str, tuple[str, ...]] = {}
    if not isinstance(raw_data, dict):
        return alias_rules

    for campaign_key, alias_values in raw_data.items():
        if not isinstance(campaign_key, str):
            continue

        if isinstance(alias_values, str):
            alias_values = [alias_values]

        if not isinstance(alias_values, list):
            continue

        cleaned_aliases = tuple(
            alias.strip()
            for alias in alias_values
            if isinstance(alias, str) and alias.strip()
        )
        if cleaned_aliases:
            alias_rules[campaign_key.strip().lower()] = cleaned_aliases

    return alias_rules
