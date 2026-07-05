"""Domain models for Campaign Suppression Manager."""

from .campaign import CampaignRecord
from .mapping import CampaignZipMatch, MappingStrategy, ValidationIssue

__all__ = [
    "CampaignRecord",
    "CampaignZipMatch",
    "MappingStrategy",
    "ValidationIssue",
]
