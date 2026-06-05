from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.gateway.config import GatewayConfig
from app.gateway.providers.base import GatewayError
from app.gateway.providers.openai_compatible_chat import OpenAICompatibleChatProvider
from app.gateway.providers.openai_compatible_image import OpenAICompatibleImageProvider
from app.gateway.providers.openai_compatible_tts import OpenAICompatibleTTSProvider
from app.gateway.providers.pluggable_video import (
    VideoJobResult,
    VideoProvider,
    create_video_provider,
)


def _parse_json_text(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    raise json.JSONDecodeError("Unable to parse JSON object from model output", text, 0)


@dataclass
class ModelGateway:
    config: GatewayConfig
    client: httpx.Client | None = None
    last_latency_ms: int | None = None
    _chat_providers: dict[str, OpenAICompatibleChatProvider] = field(
        default_factory=dict, init=False, repr=False
    )
    _tts_provider: OpenAICompatibleTTSProvider | None = field(
        default=None, init=False, repr=False
    )
    _image_provider: OpenAICompatibleImageProvider | None = field(
        default=None, init=False, repr=False
    )
    _video_provider: VideoProvider | None = field(
        default=None, init=False, repr=False
    )

    @classmethod
    def from_store(cls, store: Any) -> ModelGateway:
        from model_gateway.store import ModelGatewayStore

        if not isinstance(store, ModelGatewayStore):
            raise TypeError("store must be a ModelGatewayStore")
        return cls(config=GatewayConfig.from_store(store))

    def _chat_provider(self, profile: str) -> OpenAICompatibleChatProvider:
        if profile not in self._chat_providers:
            if profile == "vision":
                provider_config = self.config.vision
            elif profile == "video_understanding":
                provider_config = self.config.video_understanding
            else:
                provider_config = self.config.text
            self._chat_providers[profile] = OpenAICompatibleChatProvider(
                provider_config,
                client=self.client,
            )
        return self._chat_providers[profile]

    def _tts(self) -> OpenAICompatibleTTSProvider:
        if self._tts_provider is None:
            self._tts_provider = OpenAICompatibleTTSProvider(
                self.config.tts,
                client=self.client,
            )
        return self._tts_provider

    def _image(self) -> OpenAICompatibleImageProvider:
        if self._image_provider is None:
            self._image_provider = OpenAICompatibleImageProvider(
                self.config.image,
                client=self.client,
            )
        return self._image_provider

    def _video(self) -> VideoProvider:
        if self._video_provider is None:
            self._video_provider = create_video_provider(
                self.config.video_driver,
                self.config.video,
                client=self.client,
                poll_interval_sec=self.config.poll_interval_sec,
                max_poll_sec=self.config.max_poll_sec,
            )
        return self._video_provider

    def _build_messages(
        self,
        task: str,
        inputs: dict[str, Any],
        *,
        json_only: bool,
        profile: str = "text",
    ) -> list[dict[str, Any]]:
        system_parts: list[str] = []
        if isinstance(inputs.get("systemPrompt"), str) and inputs["systemPrompt"].strip():
            system_parts.append(inputs["systemPrompt"].strip())
        system_parts.append(task)
        if json_only:
            system_parts.append("Respond with valid JSON only.")

        user_inputs = inputs.get("inputs", inputs)
        if profile == "vision":
            user_message = self._build_vision_user_message(user_inputs)
        else:
            user_message = {
                "role": "user",
                "content": (
                    "Produce the requested JSON output from these inputs. "
                    "Do not echo the inputs; return the output schema only.\n"
                    f"{json.dumps(user_inputs, ensure_ascii=False)}"
                ),
            }

        return [
            {"role": "system", "content": "\n\n".join(system_parts)},
            user_message,
        ]

    def _build_vision_user_message(self, user_inputs: dict[str, Any]) -> dict[str, Any]:
        payload = dict(user_inputs)
        moments = payload.get("moments")
        content_parts: list[dict[str, Any]] = []

        if isinstance(moments, list):
            sanitized_moments: list[dict[str, Any]] = []
            for moment in moments:
                if not isinstance(moment, dict):
                    continue
                sanitized = {
                    key: value
                    for key, value in moment.items()
                    if key != "keyframeBase64"
                }
                sanitized_moments.append(sanitized)
                keyframe = moment.get("keyframeBase64")
                if isinstance(keyframe, str) and keyframe.strip():
                    content_parts.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{keyframe.strip()}",
                            },
                        }
                    )
            payload["moments"] = sanitized_moments

        content_parts.insert(
            0,
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False),
            },
        )
        return {"role": "user", "content": content_parts}

    @staticmethod
    def build_structure_messages(
        *,
        system_prompt: str,
        text_payload: dict[str, Any],
        keyframes: list[dict[str, Any]] | None = None,
        json_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Build chat messages for StructureAnalyst (text or multimodal)."""
        system_parts = [system_prompt]
        if json_only:
            system_parts.append("Respond with valid JSON only.")
        if keyframes:
            user_content: list[dict[str, Any]] = [
                {"type": "text", "text": json.dumps(text_payload, ensure_ascii=False)},
            ]
            for frame in keyframes:
                image_b64 = frame.get("imageBase64")
                if not image_b64:
                    continue
                mime_type = frame.get("mimeType", "image/jpeg")
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    }
                )
            user_message: dict[str, Any] = {"role": "user", "content": user_content}
        else:
            user_message = {
                "role": "user",
                "content": json.dumps(text_payload, ensure_ascii=False),
            }
        return [
            {"role": "system", "content": "\n\n".join(system_parts)},
            user_message,
        ]

    @staticmethod
    def build_video_structure_messages(
        *,
        system_prompt: str,
        text_payload: dict[str, Any],
        text_message: dict[str, Any],
        video_path: Path | str,
        json_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Build chat messages for direct multimodal video structure analysis."""
        system_parts = [system_prompt]
        if json_only:
            system_parts.append("Respond with valid JSON only.")

        video_file = Path(video_path)
        video_bytes = video_file.read_bytes()
        video_b64 = base64.b64encode(video_bytes).decode("ascii")
        user_content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": json.dumps(text_message, ensure_ascii=False),
            },
            {
                "type": "text",
                "text": json.dumps({"sampleFacts": text_payload}, ensure_ascii=False),
            },
            {
                "type": "video_url",
                "video_url": {"url": f"data:video/mp4;base64,{video_b64}"},
            },
        ]
        return [
            {"role": "system", "content": "\n\n".join(system_parts)},
            {"role": "user", "content": user_content},
        ]

    def complete_json_messages(
        self,
        messages: list[dict[str, Any]],
        *,
        profile: str = "text",
    ) -> dict[str, Any]:
        """Complete a chat request and parse the model response as JSON."""
        provider = self._chat_provider(profile)
        response_format = (
            {"type": "json_object"} if provider.config.supports_json_response_format() else None
        )
        raw = provider.complete(
            messages,
            model=provider.config.model,
            response_format=response_format,
        )
        self.last_latency_ms = provider.last_latency_ms
        try:
            return _parse_json_text(raw)
        except json.JSONDecodeError as exc:
            raise GatewayError(
                code="invalid_json",
                message=f"Model output is not valid JSON: {raw[:2000]}",
                retryable=False,
            ) from exc

    def complete_text(
        self,
        task: str,
        inputs: dict[str, Any],
        *,
        profile: str = "text",
    ) -> str:
        provider = self._chat_provider(profile)
        messages = self._build_messages(task, inputs, json_only=False, profile=profile)
        result = provider.complete(messages, model=provider.config.model)
        self.last_latency_ms = provider.last_latency_ms
        return result

    def complete_json(
        self,
        task: str,
        inputs: dict[str, Any],
        schema_name: str,
        *,
        profile: str = "text",
    ) -> dict[str, Any]:
        _ = schema_name
        provider = self._chat_provider(profile)
        messages = self._build_messages(task, inputs, json_only=True, profile=profile)
        response_format = (
            {"type": "json_object"} if provider.config.supports_json_response_format() else None
        )
        raw = provider.complete(
            messages,
            model=provider.config.model,
            response_format=response_format,
        )
        self.last_latency_ms = provider.last_latency_ms
        try:
            return _parse_json_text(raw)
        except json.JSONDecodeError as exc:
            raise GatewayError(
                code="invalid_json",
                message=f"Model output is not valid JSON: {raw[:2000]}",
                retryable=False,
            ) from exc

    def generate_image(self, prompt: str, *, options: dict[str, Any] | None = None) -> bytes:
        provider = self._image()
        result = provider.generate(prompt, options=options)
        self.last_latency_ms = provider.last_latency_ms
        return result

    def synthesize_speech(self, text: str, *, options: dict[str, Any] | None = None) -> bytes:
        provider = self._tts()
        result = provider.synthesize(text, options=options)
        self.last_latency_ms = provider.last_latency_ms
        return result

    def submit_video_job(self, prompt: str, *, options: dict[str, Any] | None = None) -> str:
        provider = self._video()
        return provider.submit(prompt, options or {})

    def poll_video_job(self, job_id: str) -> VideoJobResult:
        provider = self._video()
        result = provider.poll(job_id)
        self.last_latency_ms = result.latency_ms
        return result
