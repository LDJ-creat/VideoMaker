from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from app.services.task_events import now_iso

UploadMode = Literal["merge", "replace"]

# Netscape cookies.txt data line: domain \t flag \t path \t secure \t expiry \t name \t value
_DATA_LINE = re.compile(r"^[^\s#].*\t")

PLATFORM_LABELS: dict[str, str] = {
    "douyin": "抖音",
    "bilibili": "B站",
    "youtube": "YouTube",
}


def platform_from_url(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return None
    if "douyin" in host or host.endswith("iesdouyin.com"):
        return "douyin"
    if "bilibili" in host or host == "b23.tv":
        return "bilibili"
    if "youtube" in host or host == "youtu.be":
        return "youtube"
    return None


def platform_label(platform: str | None) -> str | None:
    if platform is None:
        return None
    return PLATFORM_LABELS.get(platform, platform)


def _parse_cookie_lines(content: str) -> tuple[list[str], list[str]]:
    """Return (header/prefix lines, data lines)."""
    headers: list[str] = []
    data: list[str] = []
    for raw in content.splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        if line.lstrip().startswith("#") or not _DATA_LINE.match(line):
            headers.append(line)
            continue
        data.append(line)
    return headers, data


def _domain_from_data_line(line: str) -> str | None:
    parts = line.split("\t")
    if len(parts) < 7:
        return None
    return parts[0].strip().lower()


def _domains_in_data_lines(data_lines: list[str]) -> set[str]:
    domains: set[str] = set()
    for line in data_lines:
        domain = _domain_from_data_line(line)
        if domain:
            domains.add(domain)
    return domains


def count_cookie_entries(content: str) -> int:
    _, data = _parse_cookie_lines(content)
    return len(data)


def merge_netscape_cookie_files(existing: str, incoming: str) -> str:
    """Replace cookies only for domains present in `incoming`; keep other domains."""
    _, existing_data = _parse_cookie_lines(existing)
    incoming_headers, incoming_data = _parse_cookie_lines(incoming)
    incoming_domains = _domains_in_data_lines(incoming_data)

    kept = [
        line
        for line in existing_data
        if _domain_from_data_line(line) not in incoming_domains
    ]
    merged_data = kept + incoming_data

    header = "# Netscape HTTP Cookie File\n# Merged by VideoMaker API\n"
    if incoming_headers:
        for line in incoming_headers:
            if line.startswith("#") and "Netscape" not in line and "Merged" not in line:
                header += line + "\n"

    body = "\n".join(merged_data)
    if body:
        body += "\n"
    return header + body


class CookieStore:
    """Global yt-dlp cookies under storage/global/cookies/."""

    def __init__(self, storage_root: Path) -> None:
        self._root = storage_root / "global" / "cookies"
        self._cookies_file = self._root / "ytdlp-cookies.txt"
        self._meta_file = self._root / "meta.json"

    def get_cookies_path(self) -> str | None:
        if self._cookies_file.is_file():
            return str(self._cookies_file.resolve())
        return None

    def _file_domains(self) -> list[str]:
        if not self._cookies_file.is_file():
            return []
        content = self._cookies_file.read_text(encoding="utf-8")
        _, data = _parse_cookie_lines(content)
        return sorted(_domains_in_data_lines(data))

    def get_status(self) -> dict[str, Any]:
        domains = self._file_domains()
        configured = len(domains) > 0
        meta = self._read_meta()
        return {
            "configured": configured,
            "entryCount": count_cookie_entries(
                self._cookies_file.read_text(encoding="utf-8")
            )
            if configured
            else 0,
            "updatedAt": meta.get("updatedAt") if configured else None,
            "domains": domains,
            "uploadMode": meta.get("lastUploadMode"),
        }

    def save_upload(
        self,
        content: bytes,
        *,
        mode: UploadMode = "merge",
    ) -> dict[str, Any]:
        self._root.mkdir(parents=True, exist_ok=True)
        incoming = content.decode("utf-8", errors="replace")
        _, incoming_data = _parse_cookie_lines(incoming)
        if not incoming_data:
            raise ValueError(
                "Cookie file has no entries. Export cookies while logged in on the "
                "target site (e.g. douyin.com), not an empty template file."
            )
        incoming_domains = sorted(_domains_in_data_lines(incoming_data))

        if mode == "replace" or not self._cookies_file.is_file():
            merged = incoming if incoming.endswith("\n") else incoming + "\n"
        else:
            existing = self._cookies_file.read_text(encoding="utf-8")
            merged = merge_netscape_cookie_files(existing, incoming)

        self._cookies_file.write_text(merged, encoding="utf-8")
        _, merged_data = _parse_cookie_lines(merged)
        all_domains = sorted(_domains_in_data_lines(merged_data))
        updated_at = now_iso()
        self._write_meta(
            {
                "updatedAt": updated_at,
                "lastUploadMode": mode,
                "domains": all_domains,
                "lastIncomingDomains": incoming_domains,
            }
        )
        return {
            "ok": True,
            "configured": True,
            "updatedAt": updated_at,
            "domains": all_domains,
            "mergedDomainsFromUpload": incoming_domains,
            "mode": mode,
        }

    def _read_meta(self) -> dict[str, Any]:
        if not self._meta_file.is_file():
            return {}
        try:
            return json.loads(self._meta_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_meta(self, meta: dict[str, Any]) -> None:
        self._meta_file.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
