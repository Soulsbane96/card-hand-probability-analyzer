from __future__ import annotations
import json
import os
import subprocess
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
    """Write a .bat that polls until the old exe is releasable, swaps it,
    and relaunches the new one. Logs every step to %TEMP%\\card_hand_update.log.

    Does NOT call sys.exit — the caller must shut down Qt cleanly so that
    PyInstaller can tear down its temp folder in the correct order.
    """
    old_exe_dir = os.path.dirname(old_exe_path)
    temp_dir = os.environ.get("TEMP", ".")
    bat_path = os.path.join(temp_dir, "card_hand_update.bat")
    log_path = os.path.join(temp_dir, "card_hand_update.log")

    # Poll up to 30s for the old exe to become deletable, then swap.
    # PowerShell Start-Process gives a cleanly detached child — `start` from a
    # detached cmd can leave the new process racing with the dying parent's
    # PyInstaller cleanup, which is what was producing the python313.dll error.
    bat = (
        "@echo off\n"
        "setlocal\n"
        f'set "LOG={log_path}"\n'
        f'set "OLD={old_exe_path}"\n'
        f'set "NEW={new_exe_path}"\n'
        f'set "DIR={old_exe_dir}"\n'
        '>"%LOG%" echo [%date% %time%] update bat started\n'
        "set /a TRIES=0\n"
        ":wait_loop\n"
        'del /f /q "%OLD%" 2>nul\n'
        'if not exist "%OLD%" goto deleted\n'
        "set /a TRIES+=1\n"
        'if %TRIES% GEQ 30 (\n'
        '  >>"%LOG%" echo [%date% %time%] FAIL: old exe still locked after 30s\n'
        '  exit /b 1\n'
        ')\n'
        '>>"%LOG%" echo [%date% %time%] old exe still locked, retry %TRIES%\n'
        "timeout /t 1 /nobreak >nul\n"
        "goto wait_loop\n"
        ":deleted\n"
        '>>"%LOG%" echo [%date% %time%] old exe deleted, moving new in\n'
        'move /y "%NEW%" "%OLD%" >>"%LOG%" 2>&1\n'
        'if errorlevel 1 (\n'
        '  >>"%LOG%" echo [%date% %time%] FAIL: move failed\n'
        '  exit /b 1\n'
        ')\n'
        '>>"%LOG%" echo [%date% %time%] launching new exe via powershell\n'
        'set "_MEIPASS2="\n'
        'set "_PYI_APPLICATION_HOME_DIR="\n'
        'set "_PYI_PARENT_PROCESS_LEVEL="\n'
        'powershell -NoProfile -WindowStyle Hidden -Command '
        '"Start-Process -FilePath \'%OLD%\' -WorkingDirectory \'%DIR%\'" '
        '>>"%LOG%" 2>&1\n'
        '>>"%LOG%" echo [%date% %time%] done\n'
    )
    with open(bat_path, "w") as f:
        f.write(bat)

    # Strip every PyInstaller env var that signals "you are a re-exec of an
    # onefile parent — reuse that parent's _MEI dir." Names changed across
    # PyInstaller versions, so clear all of them.
    env = os.environ.copy()
    for var in ("_MEIPASS2", "_PYI_APPLICATION_HOME_DIR", "_PYI_PARENT_PROCESS_LEVEL"):
        env.pop(var, None)

    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        env=env,
    )
