from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict

IGNORED_DIRS = {".git", "__pycache__", ".venv", "build", "dist", ".pytest_cache", ".mypy_cache"}
WATCH_EXTENSIONS = {".py", ".spec", ".json", ".csv", ".txt", ".md", ".ico", ".png", ".jpg", ".jpeg", ".gif", ".webp"}


def discover_watch_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in WATCH_EXTENSIONS:
            files.append(path)
    return sorted(files)


def get_file_states(files: list[Path]) -> Dict[Path, int]:
    return {path: path.stat().st_mtime_ns for path in files}


def build_app(root: Path) -> int:
    print(f"[{time.strftime('%H:%M:%S')}] Rebuilding application...")
    python_exe = root / ".venv" / "Scripts" / "python.exe"
    if os.name == "nt" and python_exe.exists():
        cmd = [str(python_exe), "-m", "PyInstaller", "CampaignSuppressionManager.spec", "--noconfirm"]
    else:
        cmd = [sys.executable, "-m", "PyInstaller", "CampaignSuppressionManager.spec", "--noconfirm"]

    result = subprocess.run(cmd, cwd=root, text=True)
    if result.returncode == 0:
        print(f"[{time.strftime('%H:%M:%S')}] Build complete. Updated executable: {root / 'dist' / 'CampaignSuppressionManager.exe'}")
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Build failed with exit code {result.returncode}")
    return result.returncode


def watch(root: Path, delay: float, once: bool) -> int:
    print(f"Watching {root} for changes. Press Ctrl+C to stop.")
    files = discover_watch_files(root)
    states = get_file_states(files)

    if once:
        return build_app(root)

    build_app(root)

    while True:
        time.sleep(delay)
        current_files = discover_watch_files(root)
        current_states = get_file_states(current_files)

        changed = [path for path in current_states if states.get(path) != current_states.get(path)]
        removed = [path for path in states if path not in current_states]

        if changed or removed:
            print(f"[{time.strftime('%H:%M:%S')}] Changes detected in {len(changed) + len(removed)} file(s).")
            build_app(root)
            states = current_states
            files = current_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch the project and rebuild the packaged app on changes")
    parser.add_argument("--delay", type=float, default=2.0, help="Polling interval in seconds")
    parser.add_argument("--once", action="store_true", help="Run one build and exit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    return watch(root, args.delay, args.once)


if __name__ == "__main__":
    raise SystemExit(main())
