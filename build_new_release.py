import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from version import __version__


ROOT = Path(__file__).resolve().parent
EXE_NAME = "HandProbabilityAnalyzer.exe"


def main() -> int:
    version_tag = f"v{__version__}"
    release_dir = ROOT / "Releases" / version_tag
    release_dir.mkdir(parents=True, exist_ok=True)

    print(f"[update] Running build.bat for {version_tag}...")
    result = subprocess.run(["build.bat"], cwd=ROOT, shell=True)
    if result.returncode != 0:
        print(f"[update] build.bat failed with exit code {result.returncode}")
        return result.returncode

    built_exe = ROOT / "dist" / EXE_NAME
    if not built_exe.is_file():
        print(f"[update] Expected exe not found: {built_exe}")
        return 1

    copied_exe = release_dir / EXE_NAME
    shutil.copy2(built_exe, copied_exe)
    print(f"[update] Copied exe -> {copied_exe}")

    themes_src = ROOT / "Releases" / "themes"
    deck_cache_src = ROOT / "Releases" / "deck_cache"
    for src in (themes_src, deck_cache_src):
        if not src.is_dir():
            print(f"[update] Missing required folder: {src}")
            return 1

    zip_path = release_dir / f"HandProbabilityAnalyzer_{version_tag}.zip"
    print(f"[update] Writing {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(copied_exe, EXE_NAME)
        for folder in (themes_src, deck_cache_src):
            for path in folder.rglob("*"):
                if not path.is_file():
                    continue
                if "__pycache__" in path.parts:
                    continue
                zf.write(path, path.relative_to(folder.parent))

    print(f"[update] Done. Release at {release_dir}")
    print(f"""GitHub Release Notes:
    Tag name — must follow the format v<major>.<minor>.<patch>, e.g. v1.2.3 to allow auto-updating. The v prefix is stripped and compared numerically against the current app version.

    Release asset filename — must be exactly HandProbabilityAnalyzer.exe (set in _ASSET_NAME on line 10 of core/updater.py).

    Make sure the release is marked as the latest release (not a pre-release)
    Attach the built .exe with the name HandProbabilityAnalyzer.exe
        and the built .zip for new users.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
