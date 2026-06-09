from __future__ import annotations

import json

from model_gateway.chat_messages import normalize_messages_for_chat_api, normalize_tool_call_for_api


def test_normalize_tool_call_from_internal_shape() -> None:
    item = {
        "id": "call-1",
        "name": "skill_view",
        "arguments": {"location": "skills/public/hyperframes/SKILL.md"},
    }
    normalized = normalize_tool_call_for_api(item)
    assert normalized == {
        "id": "call-1",
        "type": "function",
        "function": {
            "name": "skill_view",
            "arguments": json.dumps({"location": "skills/public/hyperframes/SKILL.md"}, ensure_ascii=False),
        },
    }


def test_normalize_messages_rewrites_assistant_tool_calls() -> None:
    messages = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-1",
                    "name": "skill_view",
                    "arguments": {"location": "skills/public/hyperframes/SKILL.md"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": "{}"},
    ]
    normalized = normalize_messages_for_chat_api(messages)
    tool_call = normalized[1]["tool_calls"][0]
    assert tool_call["type"] == "function"
    assert "function" in tool_call
    assert isinstance(tool_call["function"]["arguments"], str)


def test_normalize_tool_call_preserves_openai_shape() -> None:
    item = {
        "id": "call-2",
        "type": "function",
        "function": {"name": "registry_list", "arguments": "{}"},
    }
    normalized = normalize_tool_call_for_api(item)
    assert normalized["function"]["arguments"] == "{}"
