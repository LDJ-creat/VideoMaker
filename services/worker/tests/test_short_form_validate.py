from __future__ import annotations

import pytest

from app.gateway.model_gateway import ModelGateway
from app.gateway.config import GatewayConfig
from app.gateway.providers.base import ProviderConfig
from app.pipelines.generation_pipeline import FixtureMaterialGateway
from app.pipelines.short_form_direct import (
    filter_short_form_completion_actions,
    validate_short_form_material_gateway,
)
from app.tools.image_gen_tool import ToolError


def _gateway_config(*, video_api_key: str = "key") -> GatewayConfig:
    provider = ProviderConfig(base_url="https://example.com", api_key="k", model="m")
    video = ProviderConfig(base_url="https://video.example.com", api_key=video_api_key, model="v")
    return GatewayConfig(
        text=provider,
        vision=provider,
        video_understanding=provider,
        tts=provider,
        image=provider,
        video_driver="generic_job",
        video=video,
    )


def test_validate_short_form_material_gateway_allows_fixture() -> None:
    plan = {
        "completionActions": [
            {"id": "a1", "slotId": "slot-a", "strategy": "video_generation", "provider": "video_generation"},
        ]
    }
    validate_short_form_material_gateway(gateway=FixtureMaterialGateway(), plan=plan)


def test_validate_short_form_material_gateway_rejects_missing_video_key() -> None:
    plan = {
        "completionActions": [
            {"id": "a1", "slotId": "slot-a", "strategy": "video_generation", "provider": "video_generation"},
        ]
    }
    gateway = ModelGateway(config=_gateway_config(video_api_key=""))
    with pytest.raises(ToolError) as exc_info:
        validate_short_form_material_gateway(gateway=gateway, plan=plan)
    assert exc_info.value.code == "video_provider_not_configured"


def test_filter_short_form_skips_image_when_video_present() -> None:
    actions = [
        {"slotId": "slot-a", "strategy": "video_generation"},
        {"slotId": "slot-a", "strategy": "image_generation"},
        {"slotId": "slot-a", "strategy": "tts"},
    ]
    filtered = filter_short_form_completion_actions(actions, primary_slot_id="slot-a")
    strategies = {action["strategy"] for action in filtered}
    assert strategies == {"video_generation", "tts"}
