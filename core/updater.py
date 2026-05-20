from __future__ import annotations
import json
import os
import subprocess
import sys
import urllib.request
from typing import Callable, Optional, Tuple

_GITHUB_REPO = "Soulsbane96/card-hand-probability-analyzer"
_ASSET_NAME  = "HandProbabilityAnalyzer.exe"
_API_URL     = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"


def _parse_version(v: str) -> Tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except ValueError:
        return (0,)


def check_for_update(current_version: str) -> Tuple[bool, str, str]:
    """Return (has_update, new_version, download_url).  Raises on network error."""
    req = urllib.request.Request(_API_URL, headers={"User-Agent": "CardHandAnalyzer"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())

    latest_tag = data.get("tag_name", "")
    latest_ver = latest_tag.lstrip("v")

    if _parse_version(latest_ver) > _parse_version(current_version):
        download_url = next(
            (a["browser_download_url"] for a in data.get("assets", []) if a["name"] == _ASSET_NAME),
            "",
        )
        return True, latest_ver, download_url

    return False, latest_ver, ""


def download_update(
    url: str,
    dest_path: str,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> None:
    """Stream the new exe to dest_path, calling progress_callback(0-100) as bytes arrive."""
    req = urllib.request.Request(url, headers={"User-Agent": "CardHandAnalyzer"})
    with urllib.request.urlopen(req) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total:
                    progress_callback(int(100 * downloaded / total))


def apply_update(old_exe_path: str, new_exe_path: str) -> None:
    """Write a .bat that swaps the exes after a 2-second delay, then exits."""
    bat_path = os.path.join(os.environ.get("TEMP", "."), "card_hand_update.bat")
    bat = (
        "@echo off\n"
        "timeout /t 2 /nobreak >nul\n"
        f'del /f /q "{old_exe_path}"\n'
        f'move /y "{new_exe_path}" "{old_exe_path}"\n'
        f'start "" "{old_exe_path}"\n'
    )
    with open(bat_path, "w") as f:
        f.write(bat)
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    sys.exit(0)
