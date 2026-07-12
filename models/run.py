"""Workflow result models for Campaign Suppression Manager."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from models.campaign import CampaignRecord
from models.mapping import CampaignZipScore, ValidationIssue


@dataclass(frozen=True, slots=True)
class CampaignMappingPreview:
    """Preview row for a campaign-to-ZIP resolution."""

    campaign: CampaignRecord
    matched_zip_paths: tuple[Path, ...]
    candidate_scores: tuple[CampaignZipScore, ...]
    selected_zip_path: Path | None
    selected_score: int
    warning: str | None
    issue: ValidationIssue | None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Full validation output shown before extraction begins."""

    preview_rows: tuple[CampaignMappingPreview, ...]
    campaign_count: int
    zip_count: int
    missing_zip_count: int
    missing_suppression_count: int
    issues: tuple[ValidationIssue, ...]
    warnings: tuple[str, ...] = ()
    available_zip_paths: tuple[Path, ...] = ()


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Artifacts produced by a successful extraction run."""

    output_files: tuple[Path, ...]
    log_file: Path
    report_file: Path
