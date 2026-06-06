from __future__ import annotations

import pytest

from app.pipelines.generation_strategy import resolve_generation_strategy


def test_resolve_generation_strategy_short_form(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_SHORT_FORM_MAX_SEC", "60")
    assert resolve_generation_strategy(60) == "short_form_direct"
    assert resolve_generation_strategy(30) == "short_form_direct"


def test_resolve_generation_strategy_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_SHORT_FORM_MAX_SEC", "60")
    assert resolve_generation_strategy(61) == "long_form_composed"
    assert resolve_generation_strategy(120) == "long_form_composed"
