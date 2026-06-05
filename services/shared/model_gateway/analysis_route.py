from __future__ import annotations

from typing import Literal, TypedDict

StructureAnalysisRoute = Literal["map_reduce", "direct_multimodal"]
AnalysisRoutePreview = StructureAnalysisRoute


class ProviderStatusLike(TypedDict, total=False):
    configured: bool
    hasApiKey: bool


class ModelGatewayPreferences(TypedDict):
    directMultimodalAnalysisEnabled: bool


DEFAULT_PREFERENCES: ModelGatewayPreferences = {
    "directMultimodalAnalysisEnabled": True,
}


def normalize_preferences(raw: dict | None) -> ModelGatewayPreferences:
    if not isinstance(raw, dict):
        return dict(DEFAULT_PREFERENCES)
    enabled = raw.get("directMultimodalAnalysisEnabled")
    if not isinstance(enabled, bool):
        enabled = DEFAULT_PREFERENCES["directMultimodalAnalysisEnabled"]
    return {"directMultimodalAnalysisEnabled": enabled}


def resolve_analysis_route_preview(
    *,
    preferences: ModelGatewayPreferences,
    video_understanding: ProviderStatusLike,
) -> AnalysisRoutePreview:
    if not preferences.get("directMultimodalAnalysisEnabled", True):
        return "map_reduce"
    if video_understanding.get("configured") and video_understanding.get("hasApiKey"):
        return "direct_multimodal"
    return "map_reduce"
