from __future__ import annotations

import json
from typing import Any


def format_schema_prompt_appendix(schema_name: str, schema: dict[str, Any]) -> str:
    """Compact machine-readable contract appendix appended to agent system prompts."""
    title = str(schema.get("title") or schema_name)
    lines = [
        f"# Contract appendix: {title}",
        "Your response must validate against this contract after JSON parsing.",
        "Use only listed enum values. Do not add keys not defined on each object.",
    ]

    required_root = schema.get("required")
    if isinstance(required_root, list) and required_root:
        lines.append(f"Required top-level keys: {', '.join(str(k) for k in required_root)}.")

    props = schema.get("properties")
    if isinstance(props, dict):
        lines.extend(_format_properties(props, prefix="Top-level"))

    intent_schema = _extract_intent_item_schema(schema)
    if intent_schema is not None:
        lines.append("Each intents[] item:")
        item_required = intent_schema.get("required")
        if isinstance(item_required, list) and item_required:
            lines.append(f"  Required: {', '.join(str(k) for k in item_required)}.")
        item_props = intent_schema.get("properties")
        if isinstance(item_props, dict):
            lines.extend(_format_properties(item_props, prefix="  ", indent="  "))

    return "\n".join(lines)


def _extract_intent_item_schema(schema: dict[str, Any]) -> dict[str, Any] | None:
    props = schema.get("properties")
    if not isinstance(props, dict):
        return None
    intents = props.get("intents")
    if not isinstance(intents, dict):
        return None
    items = intents.get("items")
    return items if isinstance(items, dict) else None


def _format_properties(
    props: dict[str, Any],
    *,
    prefix: str,
    indent: str = "",
) -> list[str]:
    lines: list[str] = []
    for name, spec in props.items():
        if not isinstance(spec, dict):
            continue
        detail = _describe_schema_node(spec)
        lines.append(f"{indent}{prefix} `{name}`: {detail}")
    return lines


def _describe_schema_node(spec: dict[str, Any]) -> str:
    enum = spec.get("enum")
    if isinstance(enum, list) and enum:
        values = " | ".join(json.dumps(v, ensure_ascii=False) for v in enum)
        return f"enum {values}"

    type_name = spec.get("type")
    if type_name == "array":
        min_items = spec.get("minItems")
        suffix = f", minItems={min_items}" if min_items is not None else ""
        items = spec.get("items")
        if isinstance(items, dict):
            item_desc = _describe_schema_node(items)
            return f"array{suffix} of {item_desc}"
        return f"array{suffix}"

    if type_name == "object":
        required = spec.get("required")
        req_suffix = ""
        if isinstance(required, list) and required:
            req_suffix = f" required keys: {', '.join(str(k) for k in required)}"
        return f"object{req_suffix}"

    if type_name == "boolean":
        return "boolean"
    if type_name == "string":
        min_len = spec.get("minLength")
        if min_len:
            return f"string (minLength {min_len})"
        return "string"

    return str(type_name or "any")
