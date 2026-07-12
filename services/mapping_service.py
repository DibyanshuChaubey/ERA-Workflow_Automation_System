"""Campaign-to-ZIP mapping logic."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from config.run_config import MappingConfig
from models.campaign import CampaignRecord
from models.mapping import CampaignZipMatch, CampaignZipScore, MappingStrategy, ValidationIssue
from models.run import CampaignMappingPreview
from services.alias_rules import load_alias_rules
from services.mapping_history import load_mapping_history


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
        candidate_scores = _score_candidates(campaign.name, zip_paths, mapping_config)
        sorted_candidates = sorted(candidate_scores, key=lambda candidate: (-candidate.score, len(candidate.zip_path.name), candidate.zip_path.name.lower()))
        selected_path = None
        selected_score = 0

        if sorted_candidates:
            selected_score = sorted_candidates[0].score
            if len(sorted_candidates) == 1 or selected_score >= sorted_candidates[1].score + 15:
                selected_path = sorted_candidates[0].zip_path
            else:
                selected_path = sorted_candidates[0].zip_path

        issue = None
        warning = None
        if not sorted_candidates:
            issue = ValidationIssue(
                subject=campaign.name,
                message="Expected exactly one ZIP match for this campaign.",
            )
            selected_path = None
        elif len(sorted_candidates) > 1 and sorted_candidates[0].score - sorted_candidates[1].score < 15:
            warning = "Low confidence: multiple close matches. Please verify."

        if issue is not None:
            issues.append(issue)

        if selected_path is not None:
            matches.append(CampaignZipMatch(campaign_name=campaign.name, zip_path=str(selected_path)))

        previews.append(
            CampaignMappingPreview(
                campaign=campaign,
                matched_zip_paths=tuple(candidate.zip_path for candidate in sorted_candidates),
                candidate_scores=tuple(sorted_candidates),
                selected_zip_path=selected_path,
                selected_score=selected_score,
                warning=warning,
                issue=issue,
            )
        )

    return previews, issues, matches


def _score_candidates(campaign_name: str, zip_paths: list[Path], mapping_config: MappingConfig) -> list[CampaignZipScore]:
    if mapping_config.strategy == MappingStrategy.EXACT:
        return [CampaignZipScore(zip_path=path, score=100) for path in zip_paths if _normalize(path.stem, mapping_config.case_sensitive) == _normalize(campaign_name, mapping_config.case_sensitive)]

    if mapping_config.strategy == MappingStrategy.PARTIAL:
        campaign_value = _normalize(campaign_name, mapping_config.case_sensitive)
        candidates: list[CampaignZipScore] = []
        for path in zip_paths:
            normalized_name = _normalize(path.stem, mapping_config.case_sensitive)
            if campaign_value in normalized_name or normalized_name in campaign_value:
                match_ratio = min(len(campaign_value), len(normalized_name)) / max(len(campaign_value), len(normalized_name), 1)
                score = int(80 + match_ratio * 10)
                candidates.append(CampaignZipScore(zip_path=path, score=score))
        return candidates

    if mapping_config.strategy == MappingStrategy.PATTERN:
        if not mapping_config.pattern_template:
            raise ValueError("Pattern strategy requires a pattern_template value.")

        pattern_text = mapping_config.pattern_template.format(campaign=re.escape(campaign_name))
        pattern = re.compile(pattern_text, re.IGNORECASE if not mapping_config.case_sensitive else 0)
        return [CampaignZipScore(zip_path=path, score=110) for path in zip_paths if pattern.search(path.name)]

    if mapping_config.strategy in {MappingStrategy.SMART, MappingStrategy.AUTO}:
        alias_rules = load_alias_rules()
        history_rules = load_mapping_history()
        return _smart_match_candidates(
            campaign_name,
            zip_paths,
            mapping_config.case_sensitive,
            alias_rules,
            history_rules,
            prefer_auto=(mapping_config.strategy == MappingStrategy.AUTO),
        )

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

    if _token_signature_matches(campaign_tokens, zip_tokens):
        return True

    return _match_token_sequence(campaign_tokens, zip_tokens, 0, 0)


def _smart_match_candidates(
    campaign_name: str,
    zip_paths: list[Path],
    case_sensitive: bool,
    alias_rules: dict[str, tuple[str, ...]],
    history_rules: dict[str, tuple[str, ...]],
    prefer_auto: bool = False,
) -> list[CampaignZipScore]:
    campaign_key = campaign_name.strip().lower()
    alias_phrases = alias_rules.get(campaign_key, ())
    history_phrases = history_rules.get(campaign_key, ())

    scored_candidates: list[CampaignZipScore] = []
    for path in zip_paths:
        score = _score_smart_match(campaign_name, path, case_sensitive, alias_phrases, history_phrases)
        if score > 0:
            scored_candidates.append(CampaignZipScore(zip_path=path, score=score))

    if not scored_candidates:
        return []

    highest_score = max(candidate.score for candidate in scored_candidates)
    top_candidates = [candidate for candidate in scored_candidates if candidate.score == highest_score]

    if prefer_auto and len(top_candidates) > 1:
        return [min(top_candidates, key=lambda candidate: (len(candidate.zip_path.stem), candidate.zip_path.name.lower()))]

    return top_candidates


def _score_smart_match(
    campaign_name: str,
    zip_path: Path,
    case_sensitive: bool,
    alias_phrases: tuple[str, ...],
    history_phrases: tuple[str, ...],
) -> int:
    zip_stem = zip_path.stem
    campaign_normalized = _normalize(campaign_name, case_sensitive)
    zip_normalized = _normalize(zip_stem, case_sensitive)

    if not campaign_normalized or not zip_normalized:
        return 0

    if campaign_normalized == zip_normalized:
        return 180

    for alias_phrase in alias_phrases:
        alias_normalized = _normalize(alias_phrase, case_sensitive)
        if not alias_normalized:
            continue
        if alias_normalized == zip_normalized:
            return 175
        if alias_normalized in zip_normalized:
            extra_token_penalty = max(0, len(_tokenize(zip_stem, case_sensitive)) - len(_tokenize(alias_phrase, case_sensitive))) * 4
            return 150 - extra_token_penalty
        if zip_normalized.startswith(alias_normalized):
            return 145
        if zip_normalized.endswith(alias_normalized):
            return 143

    for history_phrase in history_phrases:
        history_normalized = _normalize(history_phrase, case_sensitive)
        if not history_normalized:
            continue
        if history_normalized == zip_normalized:
            return 170
        if history_normalized in zip_normalized:
            extra_token_penalty = max(0, len(_tokenize(zip_stem, case_sensitive)) - len(_tokenize(history_phrase, case_sensitive))) * 4
            return 140 - extra_token_penalty
        if zip_normalized.startswith(history_normalized):
            return 135
        if zip_normalized.endswith(history_normalized):
            return 133

    if _smart_match(campaign_name, zip_stem, case_sensitive):
        return 120

    campaign_tokens = _tokenize(campaign_name, case_sensitive)
    zip_tokens = _tokenize(zip_stem, case_sensitive)
    if campaign_tokens and zip_tokens:
        if _token_signature_matches(campaign_tokens, zip_tokens):
            return 140

        overlap = [token for token in campaign_tokens if token in zip_tokens]
        if overlap:
            overlap_ratio = len(overlap) / max(len(campaign_tokens), 1)
            base_score = 90 + int(overlap_ratio * 20) + len(overlap) * 4
            extra_token_penalty = max(0, len(zip_tokens) - len(campaign_tokens)) * 3
            return max(90, base_score - extra_token_penalty)

        campaign_initials = "".join(token[0] for token in campaign_tokens if token)
        zip_initials = "".join(token[0] for token in zip_tokens if token)
        if campaign_initials and zip_initials and campaign_initials == zip_initials:
            return 85

    similarity = SequenceMatcher(None, campaign_normalized, zip_normalized).ratio()
    if similarity >= 0.75:
        return int(80 + similarity * 15)

    return 0


def _token_signature_matches(campaign_tokens: list[str], zip_tokens: list[str]) -> bool:
    if not campaign_tokens or not zip_tokens:
        return False

    sorted_campaign_tokens = tuple(sorted(campaign_tokens))
    sorted_zip_tokens = tuple(sorted(zip_tokens))
    if sorted_campaign_tokens == sorted_zip_tokens:
        return True

    campaign_token_set = set(campaign_tokens)
    zip_token_set = set(zip_tokens)
    if not campaign_token_set or not zip_token_set:
        return False

    overlap = len(campaign_token_set & zip_token_set)
    return overlap >= max(1, min(len(campaign_token_set), len(zip_token_set)) - 1)


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
