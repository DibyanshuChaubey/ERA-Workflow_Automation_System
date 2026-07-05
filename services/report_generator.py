"""Generate run summary reports."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from models.mapping import ValidationIssue
from models.run import ExtractionResult, ValidationReport


def generate_report(
    report_dir: Path,
    validation_report: ValidationReport,
    extraction_result: ExtractionResult | None,
    status: str,
) -> Path:
    """Write a human-readable summary report for the current run."""

    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    lines = [
        f"Date: {datetime.now().date().isoformat()}",
        f"Time: {datetime.now().time().replace(microsecond=0).isoformat()}",
        f"Final Status: {status}",
        f"Campaign Count: {validation_report.campaign_count}",
        f"ZIP Count: {validation_report.zip_count}",
        f"Extracted Files: {len(extraction_result.output_files) if extraction_result else 0}",
        f"Missing ZIPs: {validation_report.missing_zip_count}",
        f"Missing Suppression Files: {validation_report.missing_suppression_count}",
        f"Errors: {len(validation_report.issues)}",
        f"Warnings: {len(validation_report.warnings)}",
        "",
        "Errors:",
    ]

    lines.extend(_format_issues(validation_report.issues))

    lines.extend(["", "Warnings:"])
    lines.extend(_format_warnings(validation_report.warnings))

    if extraction_result is not None:
        lines.extend(
            [
                "",
                f"Log File: {extraction_result.log_file}",
                f"Report File: {extraction_result.report_file}",
            ]
        )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _format_issues(issues: tuple[ValidationIssue, ...]) -> list[str]:
    if not issues:
        return ["None"]

    return [f"- {issue.subject}: {issue.message}" for issue in issues]


def _format_warnings(warnings: tuple[str, ...]) -> list[str]:
    if not warnings:
        return ["None"]

    return [f"- {warning}" for warning in warnings]
