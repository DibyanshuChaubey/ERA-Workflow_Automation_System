"""Mapping and validation models for campaign-to-ZIP resolution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MappingStrategy(str, Enum):
    """Supported campaign-to-ZIP mapping strategies."""

    EXACT = "exact"
    PARTIAL = "partial"
    PATTERN = "pattern"
    SMART = "smart"


@dataclass(frozen=True, slots=True)
class CampaignZipMatch:
    """Resolved mapping between a campaign and a ZIP file."""

    campaign_name: str
    zip_path: str


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A human-readable validation issue shown to the user."""

    subject: str
    message: str
