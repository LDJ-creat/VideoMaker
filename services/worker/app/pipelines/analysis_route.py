from __future__ import annotations

from typing import Literal

from model_gateway.analysis_route import resolve_analysis_route_preview
from model_gateway.store import ModelGatewayStore

StructureAnalysisRoute = Literal["map_reduce", "direct_multimodal"]


def resolve_structure_analysis_route(store: ModelGatewayStore) -> StructureAnalysisRoute:
    status = store.get_status()
    return resolve_analysis_route_preview(
        preferences=status["preferences"],
        video_understanding=status["providers"]["videoUnderstanding"],
    )
