from __future__ import annotations

from pathlib import Path

from app.services.cookie_store import CookieStore, merge_netscape_cookie_files, platform_from_url


def _line(domain: str, name: str, value: str = "v") -> str:
    return f"{domain}\tTRUE\t/\tFALSE\t2000000000\t{name}\t{value}"


def test_merge_replaces_only_incoming_domains(tmp_path: Path) -> None:
    existing = "\n".join([_line(".douyin.com", "a", "1"), _line(".bilibili.com", "b", "1")])
    incoming = _line(".douyin.com", "a", "2")
    merged = merge_netscape_cookie_files(existing, incoming)
    assert ".douyin.com" in merged and "\ta\t2" in merged
    assert ".bilibili.com" in merged and "\tb\t1" in merged


def test_cookie_store_merge_keeps_other_platforms(tmp_path: Path) -> None:
    store = CookieStore(tmp_path)
    douyin = ("\n".join([_line(".douyin.com", "sid", "d1")])).encode()
    store.save_upload(douyin, mode="replace")
    bilibili = ("\n".join([_line(".bilibili.com", "SESSDATA", "b1")])).encode()
    result = store.save_upload(bilibili, mode="merge")
    assert ".douyin.com" in result["domains"]
    assert ".bilibili.com" in result["domains"]
    text = (tmp_path / "global" / "cookies" / "ytdlp-cookies.txt").read_text(encoding="utf-8")
    assert "sid\td1" in text
    assert "SESSDATA\tb1" in text


def test_cookie_store_replace_wipes_previous(tmp_path: Path) -> None:
    store = CookieStore(tmp_path)
    store.save_upload(_line(".douyin.com", "x").encode(), mode="replace")
    store.save_upload(_line(".bilibili.com", "y").encode(), mode="replace")
    status = store.get_status()
    assert ".bilibili.com" in status["domains"]
    text = (tmp_path / "global" / "cookies" / "ytdlp-cookies.txt").read_text(encoding="utf-8")
    assert ".douyin.com" not in text


def test_platform_from_url() -> None:
    assert platform_from_url("https://v.douyin.com/abc/") == "douyin"
    assert platform_from_url("https://www.bilibili.com/video/BV1") == "bilibili"


def test_save_upload_rejects_empty_file(tmp_path: Path) -> None:
    store = CookieStore(tmp_path)
    empty = b"# Netscape HTTP Cookie File\n# no entries\n"
    try:
        store.save_upload(empty, mode="replace")
        raised = False
    except ValueError:
        raised = True
    assert raised
    assert store.get_status()["configured"] is False
