"""
Download publicly shared Google Drive files (most VNIT notices and fee
documents live on Drive, not on vnit.ac.in) through the official Drive API.

Drive's robots.txt disallows automated downloads through the normal web
links, so this uses the Drive API with an API key instead -- Google's
supported route for programs.

The key is read from a plain-text file (one line), by default
C:\\Users\\<you>\\vnit-secrets.txt, or from the path in the VNIT_KEY_FILE
environment variable. The key is never printed, and is scrubbed from any
error message (request errors normally include the full URL, key included).
"""
import os
import re
import time
from pathlib import Path

import requests

API = "https://www.googleapis.com/drive/v3/files"
REQUEST_DELAY_SECONDS = 1.0
TIMEOUT = 60

_DRIVE_ID_PATTERNS = [
    r"drive\.google\.com/file/d/([A-Za-z0-9_-]{20,})",
    r"drive\.google\.com/open\?id=([A-Za-z0-9_-]{20,})",
    r"drive\.google\.com/uc\?(?:.*&)?id=([A-Za-z0-9_-]{20,})",
]


def key_file_path() -> Path:
    return Path(os.environ.get("VNIT_KEY_FILE", Path.home() / "vnit-secrets.txt"))


def load_key() -> str:
    path = key_file_path()
    if not path.exists():
        raise FileNotFoundError(f"Google API key file not found at {path}")
    key = path.read_text(encoding="utf-8-sig").strip().splitlines()[0].strip()
    if not key:
        raise ValueError(f"Google API key file {path} is empty")
    return key


def drive_file_id(url: str):
    for pat in _DRIVE_ID_PATTERNS:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


class DriveError(Exception):
    pass


def _get(file_id: str, key: str, params: dict):
    time.sleep(REQUEST_DELAY_SECONDS)
    try:
        resp = requests.get(f"{API}/{file_id}",
                            params={**params, "supportsAllDrives": "true", "key": key},
                            timeout=TIMEOUT)
    except requests.RequestException as e:
        raise DriveError(str(e).replace(key, "<KEY>")) from None
    if not resp.ok:
        try:
            msg = resp.json()["error"]["message"]
        except Exception:
            msg = resp.text[:200]
        raise DriveError(f"HTTP {resp.status_code}: {msg}".replace(key, "<KEY>"))
    return resp


def file_metadata(file_id: str, key: str) -> dict:
    return _get(file_id, key, {"fields": "name,mimeType,size,modifiedTime"}).json()


def download(file_id: str, key: str) -> bytes:
    return _get(file_id, key, {"alt": "media"}).content
