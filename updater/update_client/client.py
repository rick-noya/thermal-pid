import json
import hashlib
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Dict
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

import tkinter as tk
from tkinter import messagebox

from packaging import version as packaging_version

try:
    from senxor import __version__ as CURRENT_VERSION
except ImportError:  # Fallback if __version__ not set for some reason
    CURRENT_VERSION = "0.0.0"


DEFAULT_MANIFEST_URL = (
    "https://github.com/rick-noya/thermal-pid/releases/download/0.1.0/latest.json"
)

_CHECK_INTERVAL_SECONDS = 60 * 60 * 24  # once a day
_last_check_ts: float = 0.0


class UpdateError(Exception):
    """Base exception for update-related errors."""


def _fetch_manifest(url: str = DEFAULT_MANIFEST_URL, *, timeout: int = 5) -> Dict:
    try:
        req = Request(url, headers={"User-Agent": "SenxorApp-Updater"})
        with urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
    except (HTTPError, URLError, OSError) as e:
        raise UpdateError(f"Failed to download manifest: {e}") from e

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise UpdateError("Manifest JSON is malformed") from e

    required_keys = {"version", "url", "sha256"}
    if not required_keys.issubset(data):
        raise UpdateError(
            f"Manifest missing required keys {required_keys - set(data.keys())}"
        )
    return data


def _is_newer(remote_ver: str, local_ver: str = CURRENT_VERSION) -> bool:
    try:
        return packaging_version.parse(remote_ver) > packaging_version.parse(local_ver)
    except Exception:
        return remote_ver > local_ver


def check_for_updates_async(
    manifest_url: str = DEFAULT_MANIFEST_URL, parent: Optional[tk.Tk] = None, user_initiated: bool = False
):
    global _last_check_ts
    if not user_initiated and time.time() - _last_check_ts < _CHECK_INTERVAL_SECONDS:
        return
    _last_check_ts = time.time()

    def _worker():
        try:
            manifest = _fetch_manifest(manifest_url)
            if not _is_newer(manifest["version"], CURRENT_VERSION):
                if user_initiated:
                    if parent is not None:
                        parent.after(0, lambda: messagebox.showinfo("Software Update", "You are running the latest version.", parent=parent))
                    else:
                        messagebox.showinfo("Software Update", "You are running the latest version.")
                return
            if parent is not None:
                parent.after(0, _prompt_update_available, manifest, parent)
            else:
                _prompt_update_available(manifest, None)
        except UpdateError as exc:
            print(f"Updater: {exc}")
            if user_initiated:
                if parent is not None:
                    parent.after(0, lambda: messagebox.showerror("Update Check Failed", f"Could not check for updates.\n{exc}", parent=parent))
                else:
                    messagebox.showerror("Update Check Failed", f"Could not check for updates.\n{exc}")

    threading.Thread(target=_worker, daemon=True).start()


def _prompt_update_available(manifest: Dict, parent: Optional[tk.Tk]):
    if parent is None:
        parent = tk._default_root  # type: ignore
    if parent is None:
        return
    def _open_changelog():
        import webbrowser
        changelog_url = manifest.get("changelog") or manifest["url"]
        webbrowser.open(changelog_url)
    new_ver = manifest["version"]
    msg = (
        f"A new version of Senxor (v{new_ver}) is available.\n\n"
        f"You are running v{CURRENT_VERSION}.\n\n"
        "Would you like to download and install the update now?"
    )
    if messagebox.askyesno("Software Update", msg, parent=parent):
        _download_and_stage_update_async(manifest, parent)
    else:
        if messagebox.askyesno(
            "Software Update", "View release notes?", parent=parent
        ):
            _open_changelog()

_CHUNK_SIZE = 1 << 16  # 64 KB

def _download_and_stage_update_async(manifest: Dict, parent: Optional[tk.Tk]):
    def _worker():
        try:
            _download_and_stage_update(manifest)
            if parent is not None:
                parent.after(0, _prompt_restart_to_update, parent)
            else:
                _prompt_restart_to_update(None)
        except UpdateError as exc:
            if parent is not None:
                parent.after(
                    0,
                    lambda: messagebox.showerror("Update Failed", str(exc), parent=parent),
                )
            else:
                print(f"Update Failed: {exc}")
    threading.Thread(target=_worker, daemon=True).start()

def _download_and_stage_update(manifest: Dict):
    url = manifest["url"]
    sha256_expected = manifest["sha256"]
    tmp_dir = Path(os.getenv("TEMP", ".")) / "Senxor_update"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    file_name = url.split("/")[-1]
    archive_path = tmp_dir / file_name
    hasher = hashlib.sha256()
    try:
        req = Request(url, headers={"User-Agent": "SenxorApp-Updater"})
        with urlopen(req) as resp, open(archive_path, "wb") as f:
            while True:
                chunk = resp.read(_CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
                hasher.update(chunk)
    except Exception as e:
        raise UpdateError(f"Download error: {e}") from e
    if hasher.hexdigest().lower() != sha256_expected.lower():
        raise UpdateError("Downloaded file hash mismatch; aborting.")
    manifest_path = tmp_dir / "update_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as fp:
        json.dump(manifest, fp)
    print(f"Updater: Update downloaded to {archive_path}")

def _prompt_restart_to_update(parent: Optional[tk.Tk]):
    if messagebox.askyesno(
        "Restart Required",
        "The update has been downloaded.\nSenxor will restart to complete the installation. Continue?",
        parent=parent,
    ):
        _launch_updater_and_exit()

def _launch_updater_and_exit():
    app_exe = Path(sys.executable)
    app_dir = app_exe.parent
    updater_exe = app_dir / "senxor_updater.exe"
    if not updater_exe.exists():
        messagebox.showerror(
            "Updater Missing",
            f"Updater executable not found: {updater_exe}.\nUpdate cannot proceed.",
        )
        return
    try:
        import subprocess
        subprocess.Popen([str(updater_exe)], close_fds=True)
    except OSError as e:
        messagebox.showerror("Launch Failed", f"Could not launch updater: {e}")
        return
    sys.exit(0) 