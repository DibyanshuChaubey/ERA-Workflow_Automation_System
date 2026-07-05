"""Campaign domain models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CampaignRecord:
    """A campaign entry read from the Excel workbook."""

    index: int
    name: str
