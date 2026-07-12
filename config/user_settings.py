"""Persistent user settings for Campaign Suppression Manager."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from models.mapping import MappingStrategy


@dataclass(slots=True)
class UserSettings:
    """Last-used paths and mapping preferences."""

    excel_path: str = ""
    zip_folder: str = ""
    output_folder: str = ""
    mapping_strategy: str = MappingStrategy.AUTO.value
    pattern_template: str = "{campaign}"


def default_settings_path() -> Path:
    """Return the per-user settings file location."""

    return Path.home() / ".campaign_suppression_manager" / "settings.json"


def load_user_settings(settings_path: Path | None = None) -> UserSettings:
    """Load persisted settings, falling back to defaults if the file is missing or invalid."""

    path = settings_path or default_settings_path()
    if not path.exists():
        return UserSettings()

    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return UserSettings()

    return UserSettings(
        excel_path=str(raw_data.get("excel_path", "")),
        zip_folder=str(raw_data.get("zip_folder", "")),
        output_folder=str(raw_data.get("output_folder", "")),
        mapping_strategy=str(raw_data.get("mapping_strategy", MappingStrategy.AUTO.value)),
        pattern_template=str(raw_data.get("pattern_template", "{campaign}")),
    )


def save_user_settings(settings: UserSettings, settings_path: Path | None = None) -> Path:
    """Persist the current settings to disk."""

    path = settings_path or default_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "excel_path": settings.excel_path,
                "zip_folder": settings.zip_folder,
                "output_folder": settings.output_folder,
                "mapping_strategy": settings.mapping_strategy,
                "pattern_template": settings.pattern_template,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
