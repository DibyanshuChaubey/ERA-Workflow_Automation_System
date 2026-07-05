"""Suppression file identification and extraction."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from models.mapping import ValidationIssue


@dataclass(frozen=True, slots=True)
class SuppressionFileSelection:
    """Resolved suppression member inside a ZIP file."""

    zip_path: Path
    member_name: str | None
    issue: ValidationIssue | None


SUPPORTED_SUPPRESSION_EXTENSIONS = {".csv", ".txt", ".xlsx", ".xlsm"}


def select_suppression_member(zip_path: Path) -> SuppressionFileSelection:
    """Return the only suppression member if exactly one exists."""

    with ZipFile(zip_path) as archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
        suppression_members = [info for info in members if _looks_like_suppression(info.filename)]

    if len(suppression_members) != 1:
        return SuppressionFileSelection(
            zip_path=zip_path,
            member_name=None,
            issue=ValidationIssue(
                subject=zip_path.name,
                message=f"Expected exactly one suppression file, found {len(suppression_members)}.",
            ),
        )

    return SuppressionFileSelection(zip_path=zip_path, member_name=suppression_members[0].filename, issue=None)


def extract_suppression_file(zip_path: Path, member_name: str, output_path: Path) -> Path:
    """Extract the suppression file while preserving the original filename."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(zip_path) as archive:
        suffix = Path(member_name).suffix.lower()
        raw_bytes = archive.read(member_name)

    if suffix not in SUPPORTED_SUPPRESSION_EXTENSIONS:
        raise ValueError(f"Unsupported suppression file type: {suffix}")

    if suffix in {".xlsx", ".xlsm"}:
        dataframe = pd.read_excel(io.BytesIO(raw_bytes), dtype=str)
        dataframe.to_excel(output_path, index=False)
        return output_path

    text = _decode_bytes(raw_bytes)
    output_path.write_text(text, encoding="utf-8-sig", newline="")
    return output_path


def _looks_like_suppression(member_name: str) -> bool:
    stem = Path(member_name).stem.lower()
    return "suppression" in stem and "cleaned" not in stem


def _decode_bytes(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError("utf-8", raw_bytes, 0, 1, "Unable to decode suppression file.")
