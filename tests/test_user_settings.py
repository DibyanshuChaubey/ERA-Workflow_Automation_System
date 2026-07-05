from __future__ import annotations

from config.user_settings import UserSettings, load_user_settings, save_user_settings


def test_user_settings_round_trip(tmp_path) -> None:
    settings_path = tmp_path / "settings.json"
    original = UserSettings(
        excel_path="c:/data/campaigns.xlsx",
        zip_folder="c:/data/zips",
        output_folder="c:/data/output",
        mapping_strategy="pattern",
        pattern_template="Campaign - {campaign}.zip",
    )

    save_user_settings(original, settings_path)
    loaded = load_user_settings(settings_path)

    assert loaded == original


def test_user_settings_missing_file_returns_defaults(tmp_path) -> None:
    settings_path = tmp_path / "missing.json"

    loaded = load_user_settings(settings_path)

    assert loaded == UserSettings()
