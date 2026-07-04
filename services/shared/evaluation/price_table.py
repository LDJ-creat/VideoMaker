from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_price_table(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        path = Path(__file__).resolve().parent / "price_table.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def estimate_cost_usd(usage_by_category: dict[str, Any], price_table: dict[str, Any]) -> dict[str, Any] | None:
    if not price_table:
        return None
    rates = price_table.get("rates") if isinstance(price_table.get("rates"), dict) else {}
    by_category: dict[str, float] = {}
    total = 0.0
    confidence = "estimate"

    text = usage_by_category.get("text_chat") or {}
    if text:
        prompt_k = float(rates.get("text_prompt_per_1k_tokens", 0))
        completion_k = float(rates.get("text_completion_per_1k_tokens", 0))
        cost = (float(text.get("promptTokens", 0)) / 1000.0) * prompt_k
        cost += (float(text.get("completionTokens", 0)) / 1000.0) * completion_k
        by_category["text_chat"] = round(cost, 4)
        total += cost

    vision = usage_by_category.get("vision_chat") or {}
    if vision:
        prompt_k = float(rates.get("vision_prompt_per_1k_tokens", rates.get("text_prompt_per_1k_tokens", 0)))
        completion_k = float(rates.get("vision_completion_per_1k_tokens", rates.get("text_completion_per_1k_tokens", 0)))
        cost = (float(vision.get("promptTokens", 0)) / 1000.0) * prompt_k
        cost += (float(vision.get("completionTokens", 0)) / 1000.0) * completion_k
        by_category["vision_chat"] = round(cost, 4)
        total += cost

    tts = usage_by_category.get("tts") or {}
    if tts:
        per_k = float(rates.get("tts_per_1k_chars", 0))
        cost = (float(tts.get("totalChars", 0)) / 1000.0) * per_k
        by_category["tts"] = round(cost, 4)
        total += cost

    image = usage_by_category.get("image_gen") or {}
    if image:
        per_image = float(rates.get("image_per_image", 0))
        cost = int(image.get("successfulImages", 0)) * per_image
        by_category["image_gen"] = round(cost, 4)
        total += cost

    video = usage_by_category.get("video_gen") or {}
    if video:
        per_sec = float(rates.get("video_per_second", 0))
        cost = float(video.get("totalDurationSec", 0)) * per_sec
        by_category["video_gen"] = round(cost, 4)
        total += cost

    if not by_category:
        return None
    return {
        "total": round(total, 4),
        "byCategory": by_category,
        "priceSource": str(price_table.get("version") or "static_v1"),
        "confidence": confidence,
    }
