from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    api_key: str
    model: str

    def supports_json_response_format(self) -> bool:
        """Some OpenAI-compatible hosts (e.g. Volcengine Ark) reject response_format=json_object."""
        host = self.base_url.lower()
        if "volces.com" in host or "volcengine" in host:
            return False
        return True


class GatewayError(RuntimeError):
    """Raised when a gateway provider call fails."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
