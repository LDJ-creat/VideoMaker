from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext
from app.validation.schema_loader import validate_contract


TASK_KEY = "content_strategist"
VALID_FACT_KINDS = {"selling_point", "audience", "scene", "constraint", "other"}


def _coerce_fact_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_extracted_facts(facts: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            raise ValueError("extractedFacts items must be objects")
        item = dict(fact)
        item["id"] = _coerce_fact_id(item.get("id")) or f"fact-{index + 1}"
        if "text" in item and item["text"] is not None:
            item["text"] = str(item["text"])
        if "source" in item and item["source"] is not None:
            item["source"] = str(item["source"])
        if "kind" in item and item["kind"] is not None:
            item["kind"] = str(item["kind"])
        normalized.append(item)
    return normalized


def _validate_content_fact(fact: dict[str, Any]) -> None:
    kind = fact.get("kind")
    if kind not in VALID_FACT_KINDS:
        raise ValueError(f"Invalid extractedFacts kind: {kind}")

    probe = {
        "id": "inventory-probe",
        "projectId": "probe",
        "userBrief": {
            "sellingPoints": [],
            "mustMention": [],
            "avoidMention": [],
        },
        "assets": [],
        "extractedFacts": [fact],
        "candidateMoments": [],
    }
    validation = validate_contract("asset-inventory", probe)
    if not validation.valid:
        raise ValueError(f"Invalid extractedFacts item: {validation.errors}")


def _validate_content_strategist_output(payload: dict[str, Any]) -> dict[str, Any]:
    facts = payload.get("extractedFacts")
    if not isinstance(facts, list):
        raise ValueError("content_strategist output must include extractedFacts array")
    normalized_facts = _normalize_extracted_facts(facts)
    for fact in normalized_facts:
        for key in ("id", "kind", "text", "source"):
            if key not in fact or not str(fact.get(key, "")).strip():
                raise ValueError(f"extractedFacts item missing '{key}'")
        _validate_content_fact(fact)
    normalized = dict(payload)
    normalized["extractedFacts"] = normalized_facts
    return normalized


def _filter_avoid_mention(
    facts: list[dict[str, Any]],
    avoid_mention: list[str],
) -> list[dict[str, Any]]:
    if not avoid_mention:
        return facts
    blocked = {item.strip().lower() for item in avoid_mention if item.strip()}
    filtered: list[dict[str, Any]] = []
    for fact in facts:
        if str(fact.get("source", "")).startswith("brief."):
            filtered.append(fact)
            continue
        text = str(fact.get("text", "")).lower()
        if any(term in text for term in blocked):
            continue
        filtered.append(fact)
    return filtered


def _merge_extracted_facts(
    baseline: list[dict[str, Any]],
    agent_facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = list(baseline)
    seen = {(fact.get("kind"), fact.get("text")) for fact in baseline}
    for fact in agent_facts:
        key = (fact.get("kind"), fact.get("text"))
        if key in seen:
            continue
        merged.append(fact)
        seen.add(key)
    return merged


def run_content_strategist(
    runner: AgentRunner,
    *,
    inventory: dict[str, Any],
    context: TaskContext,
    progress: int = 15,
    generation_id: str | None = None,
) -> dict[str, Any]:
    output = runner.run(
        "content_strategist",
        task=TASK_KEY,
        schema_name=None,
        inputs={
            "userBrief": inventory.get("userBrief", {}),
            "assets": inventory.get("assets", []),
        },
        context=context,
        progress=progress,
        generation_id=generation_id,
        post_validate=_validate_content_strategist_output,
    )

    user_brief = inventory.get("userBrief", {})
    avoid_mention = list(user_brief.get("avoidMention", []))
    agent_facts = _filter_avoid_mention(list(output.get("extractedFacts", [])), avoid_mention)
    baseline_facts = list(inventory.get("extractedFacts", []))

    merged = dict(inventory)
    merged["extractedFacts"] = _merge_extracted_facts(baseline_facts, agent_facts)
    if output.get("toneSummary") and isinstance(user_brief, dict):
        brief = dict(user_brief)
        if not brief.get("tone"):
            brief["tone"] = str(output["toneSummary"])
        merged["userBrief"] = brief
    return merged
