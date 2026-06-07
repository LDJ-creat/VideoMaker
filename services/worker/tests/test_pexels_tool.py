from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from app.tools.pexels_tool import PexelsTool
from app.tools.image_gen_tool import ToolError


def test_search_photos_fixture_mode() -> None:
    tool = PexelsTool(api_key="", fixture_mode=True)
    photos = tool.search_photos("kitchen lifestyle")
    assert len(photos) == 1
    assert photos[0]["id"] == 1001


def test_search_photos_requires_api_key() -> None:
    tool = PexelsTool(api_key="", fixture_mode=False)
    with pytest.raises(ToolError) as exc:
        tool.search_photos("kitchen")
    assert exc.value.code == "pexels_unauthorized"


def test_search_photos_live_mock() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "secret"
        return httpx.Response(
            200,
            json={
                "photos": [
                    {
                        "id": 42,
                        "alt": "kitchen cooking",
                        "width": 1920,
                        "height": 1080,
                        "url": "https://www.pexels.com/photo/42/",
                        "photographer": "Alice",
                        "src": {"original": "https://images.pexels.com/photo.jpg"},
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    tool = PexelsTool(api_key="secret", client=client, fixture_mode=False)
    photos = tool.search_photos("kitchen")
    assert photos[0]["photographer"] == "Alice"
