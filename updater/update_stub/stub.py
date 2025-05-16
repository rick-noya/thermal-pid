import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

TMP_UPDATE_DIR = Path(os.getenv("TEMP", ".")) / "Senxor_update"
MANIFEST_FILE = TMP_UPDATE_DIR / "update_manifest.json"

BACKUP_SUFFIX = time.strftime("backup_%Y%m%d_%H%M%S")


def main():
    if not MANIFEST_FILE.exists():
        print("Updater: Manifest not found; exiting.")
        return

    with open(MANIFEST_FILE, "r", encoding="utf-8") as fp:
        manifest = json.load(fp)

    archive_path = TMP_UPDATE_DIR / Path(manifest["url"]).name
    if not archive_path.exists():
        print(f"Updater: Archive {archive_path} missing; exiting.")
        return

    install_dir = Path(sys.executable).parent  # Running from frozen exe

    # Wait until main app terminates (should already be closed, but just in case)
    time.sleep(2)

    # Backup existing install
    backup_dir = install_dir.parent / f"{install_dir.name}_{BACKUP_SUFFIX}"
    try:
        print(f"Updater: Backing up current version to {backup_dir}")
        shutil.copytree(install_dir, backup_dir)
    except Exception as e:
        print(f"Updater: Failed to backup current install: {e}")

    # Extract new archive
    try:
        print(f"Updater: Extracting {archive_path} to {install_dir}")
        with zipfile.ZipFile(archive_path, "r") as zf:
            # Remove existing install directory first (except stub)??.
            for member in zf.namelist():
                target_path = install_dir / member
                if target_path.exists():
                    if target_path.is_file():
                        target_path.unlink()
                    else:
                        shutil.rmtree(target_path, ignore_errors=True)
            zf.extractall(install_dir)
    except Exception as e:
        print(f"Updater: Extraction failed: {e}")
        print("Updater: Attempting rollback...")
        shutil.rmtree(install_dir, ignore_errors=True)
        shutil.move(backup_dir, install_dir)
        return

    # Cleanup
    try:
        shutil.rmtree(TMP_UPDATE_DIR, ignore_errors=True)
    except Exception:
        pass

    # Relaunch main application
    main_exe = install_dir / "SenxorApp.exe"
    print(f"Updater: Launching {main_exe}")
    try:
        subprocess.Popen([str(main_exe)], close_fds=True)
    except OSError as e:
        print(f"Updater: Failed to launch new app: {e}")
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main() 