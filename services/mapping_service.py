"""Campaign-to-ZIP mapping logic."""

from __future__ import annotations

import re
from pathlib import Path

from config.run_config import MappingConfig
from models.campaign import CampaignRecord
from models.mapping import CampaignZipMatch, MappingStrategy, ValidationIssue
from models.run import CampaignMappingPreview
from services.alias_rules import load_alias_rules


def build_mapping_preview(
    campaigns: list[CampaignRecord],
    zip_paths: list[Path],
    mapping_config: MappingConfig,
) -> tuple[list[CampaignMappingPreview], list[ValidationIssue], list[CampaignZipMatch]]:
    """Resolve campaign-to-ZIP mappings and return preview data plus issues.

    The active strategy must produce exactly one ZIP per campaign. Pattern matching expects a
    pattern template containing the literal token {campaign}, which is replaced with the escaped
    campaign name.
    """

    previews: list[CampaignMappingPreview] = []
    issues: list[ValidationIssue] = []
    matches: list[CampaignZipMatch] = []

    for campaign in campaigns:
        matched_paths = _match_campaign(campaign.name, zip_paths, mapping_config)
        selected_path = matched_paths[0] if len(matched_paths) == 1 else None

        issue = None
        if len(matched_paths) != 1:
            issue = ValidationIssue(
                subject=campaign.name,
                message=f"Expected exactly one ZIP match, found {len(matched_paths)}.",
            )
            issues.append(issue)
        elif selected_path is not None:
            matches.append(CampaignZipMatch(campaign_name=campaign.name, zip_path=str(selected_path)))

        previews.append(
            CampaignMappingPreview(
                campaign=campaign,
                matched_zip_paths=tuple(matched_paths),
                selected_zip_path=selected_path,
                issue=issue,
            )
        )

    return previews, issues, matches


def _match_campaign(campaign_name: str, zip_paths: list[Path], mapping_config: MappingConfig) -> list[Path]:
    if mapping_config.strategy == MappingStrategy.EXACT:
        return [path for path in zip_paths if _normalize(path.stem, mapping_config.case_sensitive) == _normalize(campaign_name, mapping_config.case_sensitive)]

    if mapping_config.strategy == MappingStrategy.PARTIAL:
        campaign_value = _normalize(campaign_name, mapping_config.case_sensitive)
        return [
            path
            for path in zip_paths
            if campaign_value in _normalize(path.stem, mapping_config.case_sensitive)
            or _normalize(path.stem, mapping_config.case_sensitive) in campaign_value
        ]

    if mapping_config.strategy == MappingStrategy.PATTERN:
        if not mapping_config.pattern_template:
            raise ValueError("Pattern strategy requires a pattern_template value.")

        pattern_text = mapping_config.pattern_template.format(campaign=re.escape(campaign_name))
        pattern = re.compile(pattern_text, re.IGNORECASE if not mapping_config.case_sensitive else 0)
        return [path for path in zip_paths if pattern.search(path.name)]

    if mapping_config.strategy == MappingStrategy.SMART:
        alias_rules = load_alias_rules()
        return _smart_match_candidates(campaign_name, zip_paths, mapping_config.case_sensitive, alias_rules)

    raise ValueError(f"Unsupported mapping strategy: {mapping_config.strategy}")


def _normalize(value: str, case_sensitive: bool) -> str:
    cleaned = "".join(character for character in value if character.isalnum())
    return cleaned if case_sensitive else cleaned.lower()


def _tokenize(value: str, case_sensitive: bool) -> list[str]:
    tokens = [token for token in re.split(r"[^A-Za-z0-9]+", value) if token]
    if case_sensitive:
        return tokens

    return [token.lower() for token in tokens]


def _smart_match(campaign_name: str, zip_stem: str, case_sensitive: bool) -> bool:
    campaign_tokens = _tokenize(campaign_name, case_sensitive)
    zip_tokens = _tokenize(zip_stem, case_sensitive)

    if not campaign_tokens or not zip_tokens:
        return False

    return _match_token_sequence(campaign_tokens, zip_tokens, 0, 0)


def _smart_match_candidates(
    campaign_name: str,
    zip_paths: list[Path],
    case_sensitive: bool,
    alias_rules: dict[str, tuple[str, ...]],
) -> list[Path]:
    campaign_key = campaign_name.strip().lower()
    alias_phrases = alias_rules.get(campaign_key, ())

    scored_candidates: list[tuple[int, Path]] = []
    for path in zip_paths:
        score = _score_smart_match(campaign_name, path, case_sensitive, alias_phrases)
        if score > 0:
            scored_candidates.append((score, path))

    if not scored_candidates:
        return []

    highest_score = max(score for score, _ in scored_candidates)
    return [path for score, path in scored_candidates if score == highest_score]


def _score_smart_match(
    campaign_name: str,
    zip_path: Path,
    case_sensitive: bool,
    alias_phrases: tuple[str, ...],
) -> int:
    zip_stem = zip_path.stem
    campaign_normalized = _normalize(campaign_name, case_sensitive)
    zip_normalized = _normalize(zip_stem, case_sensitive)

    if campaign_normalized == zip_normalized:
        return 100

    for alias_phrase in alias_phrases:
        alias_normalized = _normalize(alias_phrase, case_sensitive)
        if alias_normalized and alias_normalized in zip_normalized:
            return 95 + len(alias_normalized)

    if _smart_match(campaign_name, zip_stem, case_sensitive):
        return 80

    campaign_tokens = _tokenize(campaign_name, case_sensitive)
    zip_tokens = _tokenize(zip_stem, case_sensitive)
    if campaign_tokens and zip_tokens:
        campaign_initials = "".join(token[0] for token in campaign_tokens if token)
        zip_initials = "".join(token[0] for token in zip_tokens if token)
        if campaign_initials and zip_initials and campaign_initials == zip_initials:
            return 70

    return 0


def _match_token_sequence(campaign_tokens: list[str], zip_tokens: list[str], campaign_index: int, zip_index: int) -> bool:
    if campaign_index >= len(campaign_tokens):
        return True

    if zip_index >= len(zip_tokens):
        return False

    campaign_token = campaign_tokens[campaign_index]

    for end_index in range(zip_index + 1, len(zip_tokens) + 1):
        zip_group = zip_tokens[zip_index:end_index]
        if _token_matches_group(campaign_token, zip_group) and _match_token_sequence(campaign_tokens, zip_tokens, campaign_index + 1, end_index):
            return True

    return False


def _token_matches_group(campaign_token: str, zip_group: list[str]) -> bool:
    joined_words = "".join(zip_group)
    initials = "".join(word[0] for word in zip_group if word)

    return (
        campaign_token == joined_words
        or joined_words.startswith(campaign_token)
        or campaign_token.startswith(joined_words)
        or campaign_token == initials
        or initials.startswith(campaign_token)
        or campaign_token.startswith(initials)
    )
