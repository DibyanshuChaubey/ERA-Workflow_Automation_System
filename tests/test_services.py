from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from config.run_config import MappingConfig
from models.campaign import CampaignRecord
from models.mapping import MappingStrategy
from services.file_organizer import build_output_file_path, create_timestamped_output_dir
from services.mapping_service import build_mapping_preview
from services.alias_rules import load_alias_rules
from services.suppression_extractor import extract_suppression_file, select_suppression_member
from services.zip_inventory import detect_duplicate_zip_names, validate_zip_file
from services.zip_inventory import list_zip_files


def _write_zip(path: Path, suppression_name: str = "Suppression List.csv") -> None:
    with ZipFile(path, "w") as archive:
        archive.writestr("Cleaned Email List.csv", "campaign,email\nA,a@example.com\n")
        archive.writestr(suppression_name, "campaign,suppression\nA,1\n")


def test_list_zip_files_finds_archives_without_zip_extension(tmp_path: Path) -> None:
    nested_folder = tmp_path / "downloads" / "nested"
    nested_folder.mkdir(parents=True)

    archive_path = nested_folder / "cleansed_list--Refi_Kart-20260702 (1)"
    _write_zip(archive_path)

    discovered = list_zip_files(tmp_path)

    assert discovered == [archive_path]


def test_mapping_service_exact_and_partial_modes(tmp_path: Path) -> None:
    zip_paths = [tmp_path / "Summer Sale.zip", tmp_path / "Winter Promo.zip"]
    for zip_path in zip_paths:
        _write_zip(zip_path)

    campaigns = [CampaignRecord(index=1, name="Summer Sale"), CampaignRecord(index=2, name="Winter")]

    exact_preview, exact_issues, exact_matches = build_mapping_preview(campaigns, zip_paths, MappingConfig(strategy=MappingStrategy.EXACT))
    assert exact_issues
    assert exact_preview[0].selected_zip_path is not None
    assert exact_matches[0].zip_path.endswith("Summer Sale.zip")

    partial_preview, partial_issues, partial_matches = build_mapping_preview(campaigns, zip_paths, MappingConfig(strategy=MappingStrategy.PARTIAL))
    assert partial_issues == []
    assert partial_preview[1].selected_zip_path is not None
    assert partial_matches[1].zip_path.endswith("Winter Promo.zip")


def test_mapping_service_pattern_mode(tmp_path: Path) -> None:
    zip_path = tmp_path / "Campaign - Summer Sale.zip"
    _write_zip(zip_path)

    campaigns = [CampaignRecord(index=1, name="Summer Sale")]
    preview, issues, matches = build_mapping_preview(
        campaigns,
        [zip_path],
        MappingConfig(strategy=MappingStrategy.PATTERN, pattern_template=r"^Campaign - {campaign}\.zip$"),
    )

    assert issues == []
    assert preview[0].selected_zip_path == zip_path
    assert matches[0].zip_path.endswith("Campaign - Summer Sale.zip")


def test_mapping_service_smart_mode_handles_aliases(tmp_path: Path) -> None:
    zip_path = tmp_path / "Window Nation Advertiser.zip"
    _write_zip(zip_path)

    campaigns = [CampaignRecord(index=1, name="WN_AD")]
    preview, issues, matches = build_mapping_preview(
        campaigns,
        [zip_path],
        MappingConfig(strategy=MappingStrategy.SMART),
    )

    assert issues == []
    assert preview[0].selected_zip_path == zip_path
    assert matches[0].zip_path.endswith("Window Nation Advertiser.zip")


def test_alias_rule_loader_supports_explicit_override(tmp_path: Path) -> None:
    alias_path = tmp_path / "campaign_aliases.csv"
    alias_path.write_text("campaign_key,alias\nrgr,Refi Kart\nrgr,Refi_Kart\n", encoding="utf-8")

    alias_rules = load_alias_rules(alias_path)

    assert alias_rules == {"rgr": ("Refi Kart", "Refi_Kart")}


def test_mapping_service_smart_mode_uses_alias_file(tmp_path: Path) -> None:
    zip_path = tmp_path / "cleansed_list--Refi_Kart-20260702 (1)"
    _write_zip(zip_path)

    campaigns = [CampaignRecord(index=1, name="RGR")]
    preview, issues, matches = build_mapping_preview(
        campaigns,
        [zip_path],
        MappingConfig(strategy=MappingStrategy.SMART),
    )

    assert issues == []
    assert preview[0].selected_zip_path == zip_path
    assert matches[0].zip_path.endswith("cleansed_list--Refi_Kart-20260702 (1)")


def test_zip_validation_and_duplicate_detection(tmp_path: Path) -> None:
    first_zip = tmp_path / "Alpha.zip"
    second_zip = tmp_path / "alpha.zip"
    _write_zip(first_zip)
    _write_zip(second_zip)

    validation = validate_zip_file(first_zip)
    assert validation.issues == ()
    assert validation.member_names

    duplicate_issues = detect_duplicate_zip_names([first_zip, second_zip])
    assert duplicate_issues


def test_suppression_selection_and_extract_to_csv(tmp_path: Path) -> None:
    zip_path = tmp_path / "Campaign.zip"
    output_path = tmp_path / "campaign-folder" / "Suppression List.csv"
    _write_zip(zip_path)

    selection = select_suppression_member(zip_path)
    assert selection.issue is None
    assert selection.member_name == "Suppression List.csv"

    extracted_path = extract_suppression_file(zip_path, selection.member_name, output_path)
    assert extracted_path == output_path
    assert extracted_path.name == "Suppression List.csv"
    assert "suppression" in output_path.read_text(encoding="utf-8-sig").lower()


def test_output_ordering_uses_campaign_position(tmp_path: Path) -> None:
    output_dir = create_timestamped_output_dir(tmp_path, "Summer Sale")
    file_path = build_output_file_path(output_dir, 7, "Suppression List.csv")
    assert file_path.name == "007 Suppression List.csv"
    assert output_dir.name == "Summer Sale SUPP"
