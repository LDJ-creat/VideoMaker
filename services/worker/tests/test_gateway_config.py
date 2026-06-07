from __future__ import annotations

from app.gateway.config import resolve_max_poll_sec


def test_resolve_max_poll_sec_defaults_to_600(monkeypatch) -> None:
    monkeypatch.delenv("VIDEO_MAX_POLL_SEC", raising=False)
    assert resolve_max_poll_sec() == 600


def test_resolve_max_poll_sec_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("VIDEO_MAX_POLL_SEC", "900")
    assert resolve_max_poll_sec() == 900


def test_resolve_max_poll_sec_clamps_invalid(monkeypatch) -> None:
    monkeypatch.setenv("VIDEO_MAX_POLL_SEC", "not-a-number")
    assert resolve_max_poll_sec() == 600
