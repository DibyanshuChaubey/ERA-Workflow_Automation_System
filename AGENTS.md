# Campaign Suppression Manager - AI Agent Guide

**Project**: Desktop data-operations application for daily campaign suppression workflows. Read campaigns from Excel, map to downloaded ZIPs, validate mappings, extract suppression files, output with numbered prefixes and reports.

## Quick Start

| Task | Command |
|------|---------|
| Run app | `python app.py` |
| Run tests | `pytest -q` or `pytest -v` |
| Build Windows EXE | `pyinstaller CampaignSuppressionManager.spec` |
| Install deps | `pip install -r requirements.txt` |
| Activate venv | `venv\Scripts\activate` (Windows) |

## Architecture & Data Flow

**Three-layer design**:
1. **GUI** ([gui/main_window.py](gui/main_window.py)): CustomTkinter dark-themed UI, file selection, strategy config
2. **Orchestration** ([core/processor.py](core/processor.py)): `CampaignSuppressionProcessor` with explicit **two-phase flow**: `validate()` → validation report with issues → user preview → `extract()` 
3. **Services** ([services/](services/)): Stateless functions for Excel, ZIP, mapping, extraction, reporting

**Data flow**:
```
User selects files (GUI) → RunConfig 
  → Processor.validate() 
    → read campaigns, scan ZIPs, detect issues 
    → ValidationReport preview 
  → User confirms 
  → Processor.extract() 
    → extract suppressions → output folder + log + report
```

**Key principle**: Fast-fail validation before extraction. All validation happens before any IO—issues reported to user with exact positions/names.

## Project Structure & Key Files

| Path | Purpose | Type |
|------|---------|------|
| [app.py](app.py) | Entry point; GUI initialization | main |
| [gui/main_window.py](gui/main_window.py) | CustomTkinter app + workflow control | UI orchestration |
| [core/processor.py](core/processor.py) | `CampaignSuppressionProcessor`: validate/extract phases | orchestration |
| [models/](models/) | Domain models: `CampaignRecord`, `MappingStrategy`, `ValidationReport`, `ExtractionResult` | data |
| [services/excel_reader.py](services/excel_reader.py) | Read campaigns, preserve order, skip blanks/headers | excel |
| [services/zip_inventory.py](services/zip_inventory.py) | Find ZIPs recursively, detect dupes/corruption/password/empty | zip |
| [services/mapping_service.py](services/mapping_service.py) | 4 strategies (EXACT, PARTIAL, PATTERN, SMART) with scoring | mapping |
| [services/alias_rules.py](services/alias_rules.py) | Load alias training from `config/campaign_aliases.csv` and JSON | config |
| [services/suppression_extractor.py](services/suppression_extractor.py) | Find + extract suppression files; encoding fallback chain | extraction |
| [services/file_organizer.py](services/file_organizer.py) | Numbering, output folder naming, path safety | io |
| [services/logging_service.py](services/logging_service.py) | Per-run log files with timestamps | logging |
| [services/report_generator.py](services/report_generator.py) | Summary reports | reporting |
| [config/run_config.py](config/run_config.py) | `RunConfig` dataclass: paths + mapping strategy | config |
| [config/user_settings.py](config/user_settings.py) | Persisted settings to `~/.campaign_suppression_manager/settings.json` | persistence |
| [config/campaign_aliases.csv](config/campaign_aliases.csv) | Training file for mapping (recommended approach) | config |
| [config/campaign_aliases.json](config/campaign_aliases.json) | Explicit alias rules (safest for abbreviations) | config |
| [tests/](tests/) | End-to-end and unit tests | testing |

## Code Conventions

**Immutable frozen dataclasses with slots**:
```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class CampaignRecord:
    index: int
    name: str
```
Used for all domain models in `models/` for memory efficiency and immutability.

**Type hints throughout**:
- `from __future__ import annotations` for forward references
- PEP 484 compliance
- All functions have type hints

**Service functions, not classes**:
- Excel reader, ZIP inventory, mapping engine are pure functions
- Stateless, testable, composable

**Structured error reporting**:
```python
@dataclass(frozen=True, slots=True)
class ValidationIssue:
    subject: str  # e.g., "Campaign", "ZIP", "Mapping"
    message: str  # human-readable issue description
```

## Validation Flow & Checks

`Processor.validate()` runs comprehensive pre-flight checks:

| Category | Check | Failure Mode |
|----------|-------|--------------|
| **Campaigns** | No duplicates (case-insensitive), not empty | `ValidationIssue` with position |
| **ZIPs** | No duplicates, not corrupted (`testzip()`), not password-protected (`flag_bits & 0x1`), not empty (`len(namelist())`), found recursively via `rglob('*')` + `is_zipfile()` | Issue with ZIP name |
| **Mappings** | Exactly 1 match per campaign using selected strategy | Issue with campaign + matches found |
| **Suppression files** | Exactly 1 per ZIP matching pattern | Issue with ZIP + files found |
| **Output folder** | Writable (tested with `.write_test` probe file) | Issue before extraction |

**Pattern matching for suppressions** (in [services/suppression_extractor.py](services/suppression_extractor.py)):
- File must have `"suppression"` in stem (case-insensitive)
- File must NOT have `"cleaned"` in stem
- Excel files (`.xlsx`, `.xlsm`) re-encoded via pandas
- CSV/TXT decoded with fallback chain: **utf-8-sig → utf-8 → cp1252 → latin1**

## Mapping Strategies

Configured via `MappingConfig(strategy, pattern_template, case_sensitive)`.

| Strategy | Behavior |
|----------|----------|
| **EXACT** | Alphanumeric-only normalized match (score 100) |
| **PARTIAL** | Campaign name substring in ZIP name (score 90) |
| **PATTERN** | Custom regex pattern matching |
| **SMART** | Multi-strategy scoring: exact (100) → aliases (95+) → fuzzy token match (80); returns all matches ≥ threshold |

**String normalization**: `"".join(c for c in s if c.isalnum())` for all comparison.

**Alias files** (training approach):
- [config/campaign_aliases.csv](config/campaign_aliases.csv): Recommended for maintaining mapping rules (deterministic, auditable)
- [config/campaign_aliases.json](config/campaign_aliases.json): Fallback for explicit rules

## File Output Conventions

**Numbered suppression files**:
- `001 Suppression List.csv`, `002 Suppression List.csv`, etc.
- Order matches campaign Excel order

**Output folder naming**:
- First campaign name + " SUPP" suffix (e.g., `RGR SUPP`)
- Auto-increments if exists: `RGR SUPP` → `RGR SUPP_01` → `RGR SUPP_02`

**Timestamps**:
- Format: `YYYYMMDD_HHMMSS`
- Used in summary report filenames: `summary_20241215_143022.txt`

## Common Pitfalls

### Excel Handling
- First row auto-detected and skipped if it matches `{"campaign", "campaign name", "name"}` (case-insensitive)
- Blank rows silently skipped; validation only looks at non-empty rows
- Duplicate campaigns detected **case-insensitively** with exact positions reported

### ZIP Validation
- Files without `.zip` extension are found via recursive `rglob('*')` and checked with `is_zipfile()`
- Corruption detected via `archive.testzip()` returns member name (or None if OK)
- Password protection uses ZIP file flag bit: `flag_bits & 0x1`
- Empty ZIPs (0 files) flagged as validation issue

### Suppression Detection
- **MUST match pattern**: stem contains `"suppression"` AND does NOT contain `"cleaned"`
- Exactly 1 suppression file required per ZIP—0 or 2+ fails validation
- Encoding issues: Try fallback chain before giving up (see [services/suppression_extractor.py](services/suppression_extractor.py))

### Output Folder Safety
- Writability tested **at validation time**, not extraction time
- Creates temporary `.write_test` file to verify permissions
- Non-writable folders fail early with detailed message

### GUI Fallback
- If CustomTkinter not installed, lightweight tkinter fallback UI loads
- Allows import checks in CI/CD without GUI dependencies

### Multi-run Sequencing
- Each extraction creates numbered output folder (e.g., `Campaign SUPP_01`)
- Each run gets new timestamped summary report

## Extending the Application

**Add a new mapping strategy**:
1. Add enum value to `MappingStrategy` in [models/mapping.py](models/mapping.py)
2. Implement matcher in `_match_campaign()` in [services/mapping_service.py](services/mapping_service.py)
3. Add test case in [tests/test_services.py](tests/test_services.py)

**Add a new validation check**:
1. Create `ValidationIssue` in `Processor.validate()` ([core/processor.py](core/processor.py))
2. Test in [tests/test_processor.py](tests/test_processor.py)

**Update suppression file pattern**:
- Edit `_looks_like_suppression()` in [services/suppression_extractor.py](services/suppression_extractor.py)
- Test with sample files before deployment

**CSV splitting tasks**:
- Resolve input/output paths from `__file__` instead of shell directory
- Try encoding chain: utf-8-sig → utf-8 → cp1252 → latin1
- Write to temp directory first, then rename into place after full read succeeds

## Testing

**Run all tests**:
```bash
pytest -q  # quiet
pytest -v  # verbose with details
```

**Key test patterns** (in [tests/](tests/)):
- End-to-end tests in [test_processor.py](tests/test_processor.py): uses helper functions `_write_workbook()`, `_write_zip()` to create fixtures
- Unit tests in [test_services.py](tests/test_services.py): tests each mapping strategy independently
- Settings tests in [test_user_settings.py](tests/test_user_settings.py)

**Create a test fixture**:
- Excel: Use `_write_workbook()` helper → test data → cleanup
- ZIP: Use `_write_zip()` helper → archive → cleanup
- Alias CSV: Write to temp file → test → cleanup

## Dependencies

```
customtkinter≥5.2.2   # Dark-themed GUI
pandas≥2.2.0          # Excel reading/writing
openpyxl≥3.1.2        # Excel workbook ops
pytest≥8.0.0          # Testing
pyinstaller≥6.0.0     # Windows executable packaging
```

**PyInstaller hidden imports** (in [CampaignSuppressionManager.spec](CampaignSuppressionManager.spec)):
- `customtkinter`
- `openpyxl`
- `pandas`

## Documentation Links

- [README.md](README.md) - Full feature overview
- [CampaignSuppressionManager.spec](CampaignSuppressionManager.spec) - PyInstaller build config
- [config/campaign_aliases.csv](config/campaign_aliases.csv) - Mapping training file format
