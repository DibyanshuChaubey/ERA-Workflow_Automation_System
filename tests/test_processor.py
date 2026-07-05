from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from openpyxl import Workbook

from config.run_config import MappingConfig, RunConfig
from core.processor import CampaignSuppressionProcessor
from models.mapping import MappingStrategy


def _write_workbook(path: Path, rows: list[str]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Campaigns"
    for index, value in enumerate(rows, start=1):
        worksheet.cell(row=index, column=1, value=value)
    workbook.save(path)
    workbook.close()


def _write_campaign_zip(path: Path, suppression_csv: str = "campaign,suppression\nA,1\n") -> None:
    with ZipFile(path, "w") as archive:
        archive.writestr("Cleaned Email List.csv", "campaign,email\nA,a@example.com\n")
        archive.writestr("Suppression List.csv", suppression_csv)


def test_processor_validate_and_extract_success(tmp_path: Path) -> None:
    excel_path = tmp_path / "campaigns.xlsx"
    zip_folder = tmp_path / "zips"
    output_folder = tmp_path / "output"
    zip_folder.mkdir()
    output_folder.mkdir()

    _write_workbook(excel_path, ["JSG 47", "Summer Sale", "Winter Sale"])
    _write_campaign_zip(zip_folder / "Summer Sale.zip", "campaign,suppression\nSummer Sale,yes\n")
    _write_campaign_zip(zip_folder / "Winter Sale.zip", "campaign,suppression\nWinter Sale,yes\n")

    processor = CampaignSuppressionProcessor(
        RunConfig(
            excel_path=excel_path,
            zip_folder=zip_folder,
            output_folder=output_folder,
            mapping=MappingConfig(strategy=MappingStrategy.EXACT),
        )
    )

    validation_report = processor.validate()
    assert validation_report.issues == ()
    assert [row.selected_zip_path.name for row in validation_report.preview_rows] == ["Summer Sale.zip", "Winter Sale.zip"]

    result = processor.extract(validation_report)
    assert len(result.output_files) == 2
    assert result.output_files[0].name == "001 Suppression List.csv"
    assert result.output_files[1].name == "002 Suppression List.csv"
    assert result.report_file.parent.name == "JSG 47 SUPP"
    assert result.log_file.exists()
    assert result.report_file.exists()


def test_processor_reports_missing_zip_issue(tmp_path: Path) -> None:
    excel_path = tmp_path / "campaigns.xlsx"
    zip_folder = tmp_path / "zips"
    output_folder = tmp_path / "output"
    zip_folder.mkdir()
    output_folder.mkdir()

    _write_workbook(excel_path, ["JSG 47", "Missing Campaign"])

    processor = CampaignSuppressionProcessor(
        RunConfig(
            excel_path=excel_path,
            zip_folder=zip_folder,
            output_folder=output_folder,
            mapping=MappingConfig(strategy=MappingStrategy.EXACT),
        )
    )

    validation_report = processor.validate()
    assert validation_report.issues
    assert validation_report.preview_rows[0].issue is not None
    assert "Expected exactly one ZIP match" in validation_report.preview_rows[0].issue.message
