"""ZIP discovery and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile, is_zipfile

from models.mapping import ValidationIssue


@dataclass(frozen=True, slots=True)
class ZipValidationResult:
    """Validation result for a ZIP file."""

    zip_path: Path
    issues: tuple[ValidationIssue, ...]
    member_names: tuple[str, ...]


def list_zip_files(zip_folder: Path) -> list[Path]:
    """Return ZIP files in deterministic order."""

    if not zip_folder.exists():
        raise FileNotFoundError(f"ZIP folder not found: {zip_folder}")

    zip_paths: list[Path] = []
    for path in zip_folder.rglob("*"):
        if path.is_file() and is_zipfile(path):
            zip_paths.append(path)

    return sorted(zip_paths)


def validate_zip_file(zip_path: Path) -> ZipValidationResult:
    """Check that a ZIP is readable, not corrupted, and not password protected."""

    issues: list[ValidationIssue] = []
    member_names: list[str] = []

    if not zip_path.exists():
        issues.append(ValidationIssue(subject=zip_path.name, message="ZIP file is missing."))
        return ZipValidationResult(zip_path=zip_path, issues=tuple(issues), member_names=tuple(member_names))

    try:
        with ZipFile(zip_path) as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                issues.append(ValidationIssue(subject=zip_path.name, message=f"ZIP is corrupted: {bad_member}"))

            for info in archive.infolist():
                if info.is_dir():
                    continue
                member_names.append(info.filename)
                if info.flag_bits & 0x1:
                    issues.append(ValidationIssue(subject=zip_path.name, message="ZIP is password protected."))

            if not member_names:
                issues.append(ValidationIssue(subject=zip_path.name, message="ZIP contains no files."))

    except BadZipFile:
        issues.append(ValidationIssue(subject=zip_path.name, message="ZIP is not a valid archive."))

    return ZipValidationResult(zip_path=zip_path, issues=tuple(issues), member_names=tuple(member_names))


def detect_duplicate_zip_names(zip_paths: list[Path]) -> list[ValidationIssue]:
    """Detect duplicate ZIP stems after normalization."""

    normalized_to_paths: dict[str, list[Path]] = {}
    for zip_path in zip_paths:
        normalized_to_paths.setdefault(_normalize(zip_path.stem), []).append(zip_path)

    issues: list[ValidationIssue] = []
    for normalized_name, grouped_paths in normalized_to_paths.items():
        if len(grouped_paths) > 1:
            joined = ", ".join(path.name for path in grouped_paths)
            issues.append(ValidationIssue(subject=normalized_name, message=f"Duplicate ZIP names detected: {joined}"))

    return issues


def _normalize(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())
