# Campaign Suppression Manager

Campaign Suppression Manager is a Python desktop application for daily data-operations workflows. It reads an ordered campaign Excel workbook, maps each campaign to exactly one downloaded ZIP file, previews the resolved mapping, extracts only the suppression file from each ZIP, and writes the results in Excel order.

## Version 1.0 Scope

- No API integration.
- No web automation.
- Only already-downloaded ZIP files are processed.
- Validation fails fast if anything is ambiguous or missing.

## Features

- CustomTkinter desktop UI with a preview-before-start workflow.
- Excel campaign reading with order preservation and blank-row skipping.
- ZIP validation for corruption, password protection, and empty archives.
- Configurable campaign-to-ZIP mapping strategy.
- Suppression-only extraction.
- Ordered file output with numbered prefixes.
- Run log and summary report generation.
- Pytest coverage for the core services and end-to-end processor flow.
- Explicit alias rules for campaign codes that do not map cleanly by name.

## Project Structure

- `app.py` - application entry point.
- `gui/` - desktop UI.
- `core/` - orchestration and workflow control.
- `services/` - Excel, ZIP, mapping, extraction, logging, reporting, and file organization.
- `models/` - domain and workflow data models.
- `config/` - runtime configuration objects.
- `tests/` - pytest coverage.

## Run Locally

1. Create or activate the project virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Launch the app with `python app.py`.

## Test

Run the test suite with:

```bash
pytest -q
```

## Packaging

PyInstaller is included in the dependency list so the app can be packaged once the workflow is finalized.

Build a Windows executable with:

```bash
pyinstaller CampaignSuppressionManager.spec
```

## Alias Training File

The smart mapping strategy reads [config/campaign_aliases.csv](config/campaign_aliases.csv) by default.

Add rows in this format to teach the matcher new equivalents:

```csv
campaign_key,alias
rgr,Refi Kart
wn_ad,Window Nation Advertiser
```

This is the recommended way to "train" mapping behavior because it is deterministic, auditable, and easy to update without changing code.

## Alias Rules

Use [config/campaign_aliases.json](config/campaign_aliases.json) to define explicit campaign-code to ZIP-name aliases. This is the safest way to map abbreviations such as `RGR` to `Refi Kart` when the name itself does not contain enough information for automatic matching.

## Workflow

1. Select the campaign Excel file.
2. Select the folder containing downloaded ZIP files.
3. Select the output folder.
4. Validate the mapping preview.
5. Confirm the preview.
6. Start extraction.
7. Review the generated output, log, and summary report.
