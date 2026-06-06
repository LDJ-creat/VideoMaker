from __future__ import annotations

import pytest

from app.gateway.providers.base import GatewayError
from app.pipelines.p0_demo_pipeline import _AGENT_FAILURES


def test_gateway_error_is_agent_failure() -> None:
    assert GatewayError in _AGENT_FAILURES

    with pytest.raises(GatewayError):
        raise GatewayError(code="quota", message="rate limited", retryable=True)
