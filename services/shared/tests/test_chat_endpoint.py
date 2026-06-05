from __future__ import annotations

from model_gateway.chat_endpoint import resolve_chat_completions_url


def test_resolve_appends_suffix_for_openai_style_base() -> None:
    assert (
        resolve_chat_completions_url("https://api.openai.com/v1")
        == "https://api.openai.com/v1/chat/completions"
    )


def test_resolve_preserves_full_volcengine_endpoint() -> None:
    assert (
        resolve_chat_completions_url(
            "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        )
        == "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    )


def test_resolve_trims_trailing_slash_before_check() -> None:
    assert (
        resolve_chat_completions_url(
            "https://ark.cn-beijing.volces.com/api/v3/chat/completions/"
        )
        == "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    )
