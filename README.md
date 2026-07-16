# ERA Campaign Suppression Manager

ERA Campaign Suppression Manager is a Windows desktop application for automating campaign suppression file processing. It reads ordered campaign data from Excel, matches each campaign to a single ZIP archive, previews the resolved mapping, extracts suppression lists, and writes the results in campaign order.

## Key Features

- Modern desktop UI with preview-first workflow.
- Automatic campaign-to-ZIP matching with alias and history learning.
- Intelligent ZIP validation for corruption, password protection, and empty archives.
- Suppression-only extraction with campaign-aware output naming.
- Ordered numerical output file naming.
- Detailed run log and summary report generation.
- Persistent mapping history for stronger future predictions.

## Install

1. Create or activate the virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run the App

```bash
python app.py
```

## Build a Windows Executable

```bash
pyinstaller CampaignSuppressionManager.spec
```

The packaged executable is written to `dist/CampaignSuppressionManager.exe`.

## Project Layout

- `app.py` — application entry point.
- `gui/` — user interface and workflow orchestration.
- `core/` — validation and extraction orchestration.
- `config/` — runtime configuration and user settings.
- `models/` — domain and workflow data models.
- `services/` — Excel reading, ZIP discovery, mapping, extraction, reporting, and file organization.
- `tests/` — automated regression and unit tests.

## Configuration

### Mapping History

The app stores corrected mappings in the user profile at:

- `%USERPROFILE%\.campaign_suppression_manager\mapping_history.json`

This enables the system to learn from preview confirmations and prefer previously accepted ZIP matches.

### Alias Training

The smart matcher reads alias data from:

- `config/campaign_aliases.csv`
- `config/campaign_aliases.json`

Use `campaign_aliases.csv` to add deterministic alias pairs:

```csv
campaign_key,alias
rgr,Refi Kart
wn_ad,Window Nation Advertiser
```

Use `campaign_aliases.json` for explicit alias rules when campaign codes require exact ZIP-name mappings.

## Workflow

1. Select the campaign Excel file.
2. Select the ZIP folder containing downloaded archives.
3. Select the output folder.
4. Click **Validate** to preview the campaign-to-ZIP mapping.
5. Confirm or correct the preview.
6. Click **Extract** to write suppression files.
7. Review output, log, and summary files.

## Testing

Run the automated test suite:

```bash
pytest -q
```

## Notes

- The app is designed for offline ZIP processing only.
- Validation is performed before extraction to prevent partial or ambiguous results.
- Generic suppression filenames are rewritten with the mapped campaign name for easier tracking.
