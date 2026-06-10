from __future__ import annotations

from composition.author.forbidden_copy_guard import (
    check_forbidden_copy_in_spec,
    collect_forbidden_copy_phrases,
)
from composition.author.payload import build_material_author_user_payload
from composition.types import AuthorRequest


def test_collect_forbidden_copy_includes_voiceover_and_brief() -> None:
    payload = build_material_author_user_payload(
        AuthorRequest(
            slot={
                "role": "benefit_card",
                "scriptIntent": "消解受众懊悔情绪",
                "visualIntent": "三要点卡片",
            },
            finish_brief={
                "finishIntent": "用逐行动态字幕强化金句",
                "voiceoverContext": {"line": "夏天出门怕晒黑？", "doNotRender": True},
                "creativeBrief": {
                    "visualDirection": "快切产品特写",
                    "narrativeGoal": "消解受众懊悔情绪",
                },
            },
        )
    )
    phrases = collect_forbidden_copy_phrases(payload)
    assert "夏天出门怕晒黑？" in phrases
    assert "消解受众懊悔情绪" in phrases
    assert "用逐行动态字幕强化金句" in phrases


def test_check_forbidden_copy_rejects_verbatim_brief_in_spec() -> None:
    payload = build_material_author_user_payload(
        AuthorRequest(
            slot={"role": "benefit_card", "scriptIntent": "消解受众懊悔情绪"},
            finish_brief={
                "voiceoverContext": {"line": "夏天出门怕晒黑？", "doNotRender": True},
            },
        )
    )
    spec = {
        "template": "composition",
        "durationSec": 3,
        "composition": {
            "bodyHtml": '<div id="root">消解受众懊悔情绪</div>',
            "timelineScript": "tl.set('#root', { autoAlpha: 1 }, 0);",
        },
    }
    errors = check_forbidden_copy_in_spec(spec, payload)
    assert any("Forbidden brief or voiceover" in item for item in errors)


def test_check_forbidden_copy_allows_display_copy_whitelist() -> None:
    payload = build_material_author_user_payload(
        AuthorRequest(
            slot={"role": "benefit_card"},
            finish_brief={
                "renderPolicy": {"allowedDisplayCopy": ["限时特惠"]},
            },
        )
    )
    spec = {
        "template": "benefit-card",
        "durationSec": 3,
        "params": {"title": "限时特惠"},
    }
    assert check_forbidden_copy_in_spec(spec, payload) == []


def test_user_payload_includes_field_semantics_and_render_policy() -> None:
    payload = build_material_author_user_payload(
        AuthorRequest(
            slot={"role": "hook_visual", "scriptIntent": "hook"},
            finish_brief={
                "renderPolicy": {
                    "forbidVoiceoverText": True,
                    "allowedDisplayCopy": ["Go"],
                }
            },
        )
    )
    assert payload["fieldSemantics"]
    assert payload["slot"]["creativeDirection"]["scriptGoal"] == "hook"
    assert "scriptIntent" not in payload["slot"]
    assert payload["renderPolicy"]["forbidVoiceoverText"] is True
    assert payload["renderPolicy"]["allowedDisplayCopy"] == ["Go"]
