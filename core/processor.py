"""Application orchestration for Campaign Suppression Manager."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.run_config import RunConfig
from models.campaign import CampaignRecord
from models.mapping import ValidationIssue
from models.run import CampaignMappingPreview, ExtractionResult, ValidationReport
from services.excel_reader import read_campaign_records
from services.file_organizer import build_output_file_path, create_timestamped_output_dir
from services.logging_service import create_run_logger
from services.mapping_history import load_mapping_history, merge_mapping_history, save_mapping_history
from services.mapping_service import build_mapping_preview
from services.report_generator import generate_report
from services.suppression_extractor import extract_suppression_file, select_suppression_member
from services.zip_inventory import detect_duplicate_zip_names, list_zip_files, validate_zip_file


@dataclass(frozen=True, slots=True)
class ValidationBundle:
    """All validation artifacts generated before extraction."""

    campaigns: tuple[CampaignRecord, ...]
    zip_paths: tuple[Path, ...]
    preview: tuple[CampaignMappingPreview, ...]
    issues: tuple[ValidationIssue, ...]


class CampaignSuppressionProcessor:
    """Coordinate validation, preview, and extraction."""

    def __init__(self, run_config: RunConfig) -> None:
        self._run_config = run_config

    def validate(self) -> ValidationReport:
        campaigns = tuple(read_campaign_records(self._run_config.excel_path))
        zip_paths = tuple(list_zip_files(self._run_config.zip_folder))
        naming_seed = campaigns[0] if campaigns else None
        mapped_campaigns = campaigns[1:] if len(campaigns) > 1 else tuple()

        issues: list[ValidationIssue] = []
        issues.extend(self._validate_campaigns(campaigns))
        issues.extend(self._validate_output_folder(self._run_config.output_folder))

        if not zip_paths:
            issues.append(ValidationIssue(subject=str(self._run_config.zip_folder), message="No ZIP archives were found in the selected folder."))

        issues.extend(detect_duplicate_zip_names(list(zip_paths)))

        preview_rows, mapping_issues, _ = build_mapping_preview(list(mapped_campaigns), list(zip_paths), self._run_config.mapping)
        issues.extend(mapping_issues)
        warnings = tuple(row.warning for row in preview_rows if row.warning)

        for zip_path in zip_paths:
            zip_result = validate_zip_file(zip_path)
            issues.extend(zip_result.issues)

            if not zip_result.issues:
                suppression_selection = select_suppression_member(zip_path)
                if suppression_selection.issue is not None:
                    issues.append(suppression_selection.issue)

        missing_zip_count = sum(1 for preview_row in preview_rows if preview_row.selected_zip_path is None)
        missing_suppression_count = sum(
            1
            for zip_path in zip_paths
            if select_suppression_member(zip_path).issue is not None
        )

        return ValidationReport(
            preview_rows=tuple(preview_rows),
            campaign_count=len(mapped_campaigns),
            zip_count=len(zip_paths),
            missing_zip_count=missing_zip_count,
            missing_suppression_count=missing_suppression_count,
            issues=tuple(issues),
            available_zip_paths=tuple(zip_paths),
        )

    def extract(self, validation_report: ValidationReport) -> ExtractionResult:
        if validation_report.issues:
            raise ValueError("Extraction cannot start until validation passes.")

        campaigns = read_campaign_records(self._run_config.excel_path)
        first_campaign_name = campaigns[0].name if campaigns else "Campaign"
        preview_rows = validation_report.preview_rows
        zip_paths = list(list_zip_files(self._run_config.zip_folder))
        output_dir = create_timestamped_output_dir(self._run_config.output_folder, first_campaign_name)
        log_file = output_dir / "run.log"
        logger = create_run_logger(log_file)

        extracted_files: list[Path] = []
        for position, preview_row in enumerate(preview_rows, start=1):
            assert preview_row.selected_zip_path is not None
            suppression_selection = select_suppression_member(preview_row.selected_zip_path)
            if suppression_selection.issue is not None or suppression_selection.member_name is None:
                raise ValueError(suppression_selection.issue.message if suppression_selection.issue else "Suppression file validation failed.")

            original_filename = Path(suppression_selection.member_name).name
            output_path = build_output_file_path(
                output_dir,
                position,
                original_filename,
                campaign_name=preview_row.campaign.name,
            )
            extracted_file = extract_suppression_file(
                preview_row.selected_zip_path,
                suppression_selection.member_name,
                output_path,
            )
            extracted_files.append(extracted_file)
            logger.info("Extracted campaign=%s zip=%s output=%s", preview_row.campaign.name, preview_row.selected_zip_path.name, extracted_file.name)

        report_placeholder = output_dir / "summary.txt"
        report_result = ExtractionResult(output_files=tuple(extracted_files), log_file=log_file, report_file=report_placeholder)
        report_file = generate_report(
            output_dir,
            ValidationReport(
                preview_rows=tuple(preview_rows),
                campaign_count=len(preview_rows),
                zip_count=len(zip_paths),
                missing_zip_count=0,
                missing_suppression_count=0,
                issues=tuple(),
            ),
            report_result,
            status="SUCCESS",
        )

        mapping_history = load_mapping_history()
        mapped_pairs = {
            preview_row.campaign.name: preview_row.selected_zip_path.stem
            for preview_row in preview_rows
            if preview_row.selected_zip_path is not None
        }
        merged_history = merge_mapping_history(mapping_history, mapped_pairs)
        save_mapping_history(merged_history)
        logger.info("Persisted mapping history for future runs: %s", mapped_pairs)

        return ExtractionResult(output_files=tuple(extracted_files), log_file=log_file, report_file=report_file)

    def _validate_campaigns(self, campaigns: tuple[CampaignRecord, ...]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        names_seen: dict[str, list[int]] = {}

        for campaign in campaigns:
            names_seen.setdefault(campaign.name.strip().lower(), []).append(campaign.index)

        for campaign_name, indexes in names_seen.items():
            if len(indexes) > 1:
                issues.append(ValidationIssue(subject=campaign_name, message=f"Duplicate campaign name detected at positions: {indexes}"))

        if not campaigns:
            issues.append(ValidationIssue(subject="Campaign Excel", message="No campaign names were found in the workbook."))

        return issues

    def _validate_output_folder(self, output_folder: Path) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        try:
            output_folder.mkdir(parents=True, exist_ok=True)
            probe = output_folder / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            issues.append(ValidationIssue(subject=str(output_folder), message=f"Output folder is not writable: {exc}"))

        return issues
