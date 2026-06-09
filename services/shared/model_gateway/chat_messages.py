from __future__ import annotations

import json
from typing import Any


def _arguments_to_json_string(arguments: Any) -> str:
    if isinstance(arguments, str):
        text = arguments.strip()
        if not text:
            return "{}"
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            return json.dumps({"raw": arguments}, ensure_ascii=False)
    if isinstance(arguments, dict):
        return json.dumps(arguments, ensure_ascii=False)
    if arguments is None:
        return "{}"
    return json.dumps(arguments, ensure_ascii=False)


def normalize_tool_call_for_api(item: dict[str, Any]) -> dict[str, Any]:
    """Convert internal or partial tool_call objects to OpenAI-compatible shape."""
    if not isinstance(item, dict):
        raise ValueError("tool_call must be an object")

    fn = item.get("function") if isinstance(item.get("function"), dict) else None
    if fn is not None:
        function = dict(fn)
        function["arguments"] = _arguments_to_json_string(function.get("arguments"))
        name = str(function.get("name") or "")
        call_id = str(item.get("id") or name or "call")
        return {"id": call_id, "type": "function", "function": function}

    name = str(item.get("name") or "")
    call_id = str(item.get("id") or name or "call")
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": _arguments_to_json_string(item.get("arguments")),
        },
    }


def normalize_messages_for_chat_api(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure assistant tool_calls use OpenAI `{ type, function: { name, arguments } }` shape."""
    normalized: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        copy = dict(message)
        tool_calls = copy.get("tool_calls")
        if copy.get("role") == "assistant" and isinstance(tool_calls, list) and tool_calls:
            copy["tool_calls"] = [
                normalize_tool_call_for_api(item) for item in tool_calls if isinstance(item, dict)
            ]
        normalized.append(copy)
    return normalized
