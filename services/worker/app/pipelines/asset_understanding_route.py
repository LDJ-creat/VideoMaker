from __future__ import annotations

from typing import Literal

from model_gateway.analysis_route import resolve_analysis_route_preview
from model_gateway.store import ModelGatewayStore

AssetUnderstandingRoute = Literal["direct_multimodal", "legacy"]


def resolve_asset_understanding_route(store: ModelGatewayStore) -> AssetUnderstandingRoute:
    status = store.get_status()
    preview = resolve_analysis_route_preview(
        preferences=status["preferences"],
        video_understanding=status["providers"]["videoUnderstanding"],
    )
    return "direct_multimodal" if preview == "direct_multimodal" else "legacy"
