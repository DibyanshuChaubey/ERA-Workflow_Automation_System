"""Runtime configuration objects for Campaign Suppression Manager."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from models.mapping import MappingStrategy


@dataclass(frozen=True, slots=True)
class MappingConfig:
    """Rules used to map campaigns to ZIP files."""

    strategy: MappingStrategy = MappingStrategy.EXACT
    pattern_template: str | None = None
    case_sensitive: bool = False


@dataclass(frozen=True, slots=True)
class RunConfig:
    """Inputs and outputs for a single processing run."""

    excel_path: Path
    zip_folder: Path
    output_folder: Path
    mapping: MappingConfig = MappingConfig()
