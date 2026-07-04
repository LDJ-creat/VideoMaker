from __future__ import annotations

import json
from pathlib import Path

from composition.author.standalone_canvas_guard import (
    check_hf_native_standalone_composition,
    is_hf_native_standalone,
)
from composition.lint_pipeline import validate_spec_gate

_HF_NATIVE_PAYLOAD = {
    "finishBrief": {
        "completionMode": "hf_native",
        "compositionAuthorBrief": {"mode": "hf_native"},
    },
    "slot": {"slotId": "action-slot-3", "role": "benefit_card"},
}

_SLOT3_SPEC_PATH = (
    Path(__file__).resolve().parents[2]
    / "api/storage/projects/7bed327a-f272-4887-a294-938d30b98723"
    / "generations/21fbf28a-b79b-4876-b4d5-e43cbe6f10c4/generated/action-slot-3/material-spec.json"
)


def _good_standalone_spec() -> dict:
    return {
        "template": "composition",
        "durationSec": 4.79,
        "composition": {
            "bodyHtml": (
                '<div class="vm-stage" data-composition-id="main">'
                '<div class="vm-hero"><span class="vm-word">认知差</span></div></div>'
            ),
            "styles": (
                ":root { --vm-bg: #f5f0e8; --vm-fg: #2a2826; --vm-accent: #e8b923; }\n"
                "#root { width: 100%; height: 100%; background: var(--vm-bg); }\n"
                ".vm-word { font-size: 88px; color: var(--vm-accent); }\n"
            ),
            "timelineScript": (
                "tl.set('#root', { autoAlpha: 1 }, 0);\n"
                "tl.from('.vm-word', { y: 36, autoAlpha: 0, duration: 0.6 }, 0.2);\n"
                "tl.set('.vm-hero', { autoAlpha: 1 }, 4.79);"
            ),
        },
    }


def test_is_hf_native_standalone() -> None:
    assert is_hf_native_standalone(_HF_NATIVE_PAYLOAD) is True
    overlay = {"finishBrief": {"completionMode": "source_then_polish"}}
    assert is_hf_native_standalone(overlay) is False


def test_slot3_black_screen_spec_fails_guard() -> None:
    if not _SLOT3_SPEC_PATH.is_file():
        spec = {
            "template": "composition",
            "durationSec": 5.743,
            "composition": {
                "bodyHtml": '<div id="root"><div class="phrase"><span class="word">x</span></div></div>',
                "styles": (
                    ":root { --vm-bg: transparent; }\n"
                    "#root { background: transparent; }\n"
                    ".phrase { opacity: 0; visibility: hidden; }\n"
                ),
                "timelineScript": (
                    "tl.set('#root', { autoAlpha: 1 }, 0);\n"
                    "tl.from('.phrase', { autoAlpha: 0, duration: 0.5 }, 0.1);\n"
                    "tl.set('.phrase', {}, 5.743);"
                ),
            },
        }
    else:
        spec = json.loads(_SLOT3_SPEC_PATH.read_text(encoding="utf-8"))

    errors = check_hf_native_standalone_composition(spec, _HF_NATIVE_PAYLOAD)
    assert any("transparent" in e for e in errors)
    assert any('id="root"' in e for e in errors)
    assert any("autoAlpha:1 on content" in e for e in errors)


def test_good_standalone_spec_passes_guard() -> None:
    errors = check_hf_native_standalone_composition(_good_standalone_spec(), _HF_NATIVE_PAYLOAD)
    assert errors == []


def test_validate_spec_gate_includes_standalone_guard() -> None:
    bad = _good_standalone_spec()
    bad["composition"]["styles"] = ":root { --vm-bg: transparent; }\n#root { background: transparent; }"
    errors = validate_spec_gate(bad, _HF_NATIVE_PAYLOAD)
    assert any("transparent" in e for e in errors)
