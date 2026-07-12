"""Application entry point for Campaign Suppression Manager."""

from __future__ import annotations

from gui.main_window import CampaignSuppressionApp


def main() -> None:
    """Start the desktop application."""

    app = CampaignSuppressionApp()
    app.run()

if __name__ == "__main__":
    main()
