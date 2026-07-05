"""Output folder creation and file naming utilities."""

from __future__ import annotations

from pathlib import Path


def create_timestamped_output_dir(base_output_folder: Path, campaign_name: str) -> Path:
    """Create a unique output folder based on the first campaign name plus SUPP."""

    base_output_folder.mkdir(parents=True, exist_ok=True)

    base_folder_name = f"{_sanitize_folder_name(campaign_name)} SUPP"
    candidate = base_output_folder / base_folder_name
    sequence = 1
    while candidate.exists():
        candidate = base_output_folder / f"{base_folder_name}_{sequence:02d}"
        sequence += 1

    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def build_output_file_path(output_dir: Path, position: int, original_filename: str) -> Path:
    """Generate the output file path in campaign order while preserving the original file name."""

    safe_name = Path(original_filename).name
    return output_dir / f"{position:03d} {safe_name}"


def _sanitize_folder_name(value: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in {" ", "-", "_"} else "_" for character in value.strip())
    return " ".join(cleaned.split()) or "Campaign"
