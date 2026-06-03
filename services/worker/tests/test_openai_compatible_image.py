from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from app.gateway.providers.base import ProviderConfig
from app.gateway.providers.openai_compatible_image import (
    OpenAICompatibleImageProvider,
    _dashscope_generation_url,
    _extract_image_bytes_from_dashscope,
)


def test_dashscope_generation_url_from_compatible_mode() -> None:
    url = _dashscope_generation_url(
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    assert url.endswith("/api/v1/services/aigc/multimodal-generation/generation")
    assert "dashscope.aliyuncs.com" in url


def test_extract_image_bytes_from_dashscope_downloads_url() -> None:
    client = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.content = b"png-bytes"
    client.get.return_value = response

    payload = {
        "output": {
            "choices": [
                {
                    "message": {
                        "content": [
                            {
                                "type": "image",
                                "image": "https://example.com/generated.png",
                            }
                        ]
                    }
                }
            ]
        }
    }
    assert _extract_image_bytes_from_dashscope(payload, client) == b"png-bytes"
    client.get.assert_called_once_with("https://example.com/generated.png")


def test_generate_uses_dashscope_endpoint(monkeypatch) -> None:
    config = ProviderConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="test-key",
        model="wan2.7-image-pro",
    )
    provider = OpenAICompatibleImageProvider(config)

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {
                "output": {
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {
                                        "type": "image",
                                        "image": "https://example.com/generated.png",
                                    }
                                ]
                            }
                        }
                    ]
                }
            }

        text = ""

    download_response = MagicMock()
    download_response.status_code = 200
    download_response.content = b"image"

    client = MagicMock()
    client.post.return_value = FakeResponse()
    client.get.return_value = download_response
    provider._client = client

    result = provider.generate("sunscreen product hero shot")
    assert result == b"image"
    post_url = client.post.call_args.args[0]
    assert "multimodal-generation/generation" in post_url
