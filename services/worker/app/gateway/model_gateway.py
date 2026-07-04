from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.gateway.chat_timeout import chat_timeout_sec
from app.gateway.config import GatewayConfig
from app.gateway.providers.base import GatewayError
from app.gateway.providers.openai_compatible_chat import OpenAICompatibleChatProvider
from app.gateway.providers.openai_compatible_image import OpenAICompatibleImageProvider
from app.gateway.providers.tts_factory import TTSProviderProtocol, create_tts_provider
from app.gateway.providers.pluggable_video import (
    VideoJobResult,
    VideoProvider,
    create_video_provider,
)
from app.observability.capture import sanitize_messages
from app.observability.model_call_recorder import (
    chat_driver_for_profile,
    image_driver,
    record_model_call,
    tts_driver,
    video_driver,
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
    last_token_usage: dict[str, float] | None = None
    observability: Any | None = None
    _chat_providers: dict[str, OpenAICompatibleChatProvider] = field(
        default_factory=dict, init=False, repr=False
    )
    _tts_provider: TTSProviderProtocol | None = field(
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

    def _sync_chat_usage(self, provider: OpenAICompatibleChatProvider) -> dict[str, float] | None:
        usage = getattr(provider, "last_token_usage", None)
        if not isinstance(usage, dict):
            self.last_token_usage = None
            return None
        normalized = {
            "prompt": float(usage.get("prompt", 0)),
            "completion": float(usage.get("completion", 0)),
        }
        if usage.get("total") is not None:
            normalized["total"] = float(usage["total"])
        else:
            normalized["total"] = normalized["prompt"] + normalized["completion"]
        self.last_token_usage = normalized
        return normalized

    def _chat_usage_units(self) -> dict[str, Any] | None:
        from evaluation.usage_normalize import usage_units_from_tokens

        return usage_units_from_tokens(self.last_token_usage)

    def _chat_provider(self, profile: str) -> OpenAICompatibleChatProvider:
        if profile not in self._chat_providers:
            if profile == "vision":
                provider_config = self.config.vision
            elif profile == "video_understanding":
                provider_config = self.config.video_understanding
            else:
                provider_config = self.config.text
            timeout_sec = chat_timeout_sec(profile)
            client = self.client
            if profile in {"video_understanding", "vision"} and client is not None:
                client = None
            self._chat_providers[profile] = OpenAICompatibleChatProvider(
                provider_config,
                client=client,
                timeout_sec=timeout_sec,
            )
        return self._chat_providers[profile]

    def _tts(self) -> TTSProviderProtocol:
        if self._tts_provider is None:
            self._tts_provider = create_tts_provider(
                self.config.tts_driver,
                self.config.tts,
                tts_preferences=self.config.tts_preferences,
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
        schema_name: str | None = None,
    ) -> list[dict[str, Any]]:
        system_parts: list[str] = []
        if isinstance(inputs.get("systemPrompt"), str) and inputs["systemPrompt"].strip():
            system_parts.append(inputs["systemPrompt"].strip())
        system_parts.append(task)
        if json_only:
            system_parts.append("Respond with valid JSON only.")
            if schema_name:
                system_parts.append(self._schema_prompt_appendix(schema_name))

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
    def _schema_prompt_appendix(schema_name: str) -> str:
        from app.validation.prompt_schema import format_schema_prompt_appendix
        from app.validation.schema_loader import _LOADER

        try:
            schema = _LOADER.get_schema(schema_name)
        except KeyError:
            return f"Validate output against contract `{schema_name}`."
        return format_schema_prompt_appendix(schema_name, schema)

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

    @staticmethod
    def build_asset_inventory_messages(
        *,
        system_prompt: str,
        text_message: dict[str, Any],
        media_parts: list[dict[str, Any]] | None = None,
        json_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Build chat messages for direct multimodal user asset inventory analysis."""
        system_parts = [system_prompt]
        if json_only:
            system_parts.append("Respond with valid JSON only.")

        user_content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": json.dumps(text_message, ensure_ascii=False),
            },
        ]
        for part in media_parts or []:
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type == "video_url" and isinstance(part.get("video_url"), dict):
                user_content.append(part)
            elif part_type == "image_url" and isinstance(part.get("image_url"), dict):
                user_content.append(part)

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
        model = provider.config.model
        started = time.perf_counter()
        input_payload = sanitize_messages(messages)
        output_payload: dict[str, Any] | None = None
        error: Exception | None = None
        try:
            response_format = (
                {"type": "json_object"} if provider.config.supports_json_response_format() else None
            )
            raw = provider.complete(
                messages,
                model=model,
                response_format=response_format,
            )
            self.last_latency_ms = provider.last_latency_ms
            self._sync_chat_usage(provider)
            output_payload = _parse_json_text(raw)
            return output_payload
        except json.JSONDecodeError as exc:
            error = GatewayError(
                code="invalid_json",
                message=f"Model output is not valid JSON: {raw[:2000] if 'raw' in locals() else ''}",
                retryable=False,
            )
            raise error from exc
        except Exception as exc:
            error = exc
            raise
        finally:
            record_model_call(
                self,
                call_kind="chat_json",
                profile=profile,
                model=model,
                driver=chat_driver_for_profile(self, profile),
                input_payload=input_payload,
                started=started,
                output_payload=output_payload,
                output_valid=error is None,
                error=error,
                token_usage=self.last_token_usage,
                usage_units=self._chat_usage_units(),
            )

    def complete_text(
        self,
        task: str,
        inputs: dict[str, Any],
        *,
        profile: str = "text",
    ) -> str:
        provider = self._chat_provider(profile)
        model = provider.config.model
        messages = self._build_messages(task, inputs, json_only=False, profile=profile)
        started = time.perf_counter()
        output_payload: str | None = None
        error: Exception | None = None
        try:
            result = provider.complete(messages, model=model)
            self.last_latency_ms = provider.last_latency_ms
            self._sync_chat_usage(provider)
            output_payload = result
            return result
        except Exception as exc:
            error = exc
            raise
        finally:
            record_model_call(
                self,
                call_kind="chat_text",
                profile=profile,
                model=model,
                driver=chat_driver_for_profile(self, profile),
                input_payload=sanitize_messages(messages),
                started=started,
                output_payload=output_payload,
                output_valid=error is None,
                error=error,
                token_usage=self.last_token_usage,
                usage_units=self._chat_usage_units(),
            )

    def complete_json(
        self,
        task: str,
        inputs: dict[str, Any],
        schema_name: str,
        *,
        profile: str = "text",
    ) -> dict[str, Any]:
        provider = self._chat_provider(profile)
        model = provider.config.model
        messages = self._build_messages(
            task,
            inputs,
            json_only=True,
            profile=profile,
            schema_name=schema_name,
        )
        started = time.perf_counter()
        output_payload: dict[str, Any] | None = None
        error: Exception | None = None
        try:
            response_format = (
                {"type": "json_object"} if provider.config.supports_json_response_format() else None
            )
            raw = provider.complete(
                messages,
                model=model,
                response_format=response_format,
            )
            self.last_latency_ms = provider.last_latency_ms
            self._sync_chat_usage(provider)
            output_payload = _parse_json_text(raw)
            return output_payload
        except json.JSONDecodeError as exc:
            error = GatewayError(
                code="invalid_json",
                message=f"Model output is not valid JSON: {raw[:2000] if 'raw' in locals() else ''}",
                retryable=False,
            )
            raise error from exc
        except Exception as exc:
            error = exc
            raise
        finally:
            record_model_call(
                self,
                call_kind="chat_json",
                profile=profile,
                model=model,
                driver=chat_driver_for_profile(self, profile),
                input_payload=sanitize_messages(messages),
                started=started,
                output_payload=output_payload,
                output_valid=error is None,
                error=error,
                token_usage=self.last_token_usage,
                usage_units=self._chat_usage_units(),
            )

    def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        task: str = "material_author",
        profile: str = "text",
    ) -> dict[str, Any]:
        _ = task
        provider = self._chat_provider(profile)
        model = provider.config.model
        started = time.perf_counter()
        input_payload = {
            "messages": sanitize_messages(messages),
            "tools": tools,
        }
        output_payload: dict[str, Any] | None = None
        error: Exception | None = None
        try:
            message = provider.complete_assistant_message(
                messages,
                model=model,
                tools=tools,
            )
            self.last_latency_ms = provider.last_latency_ms
            self._sync_chat_usage(provider)
            tool_calls_raw = message.get("tool_calls") or []
            tool_calls: list[dict[str, Any]] = []
            for item in tool_calls_raw:
                if not isinstance(item, dict):
                    continue
                fn = item.get("function") if isinstance(item.get("function"), dict) else {}
                raw_args = fn.get("arguments", {})
                if isinstance(raw_args, str):
                    try:
                        parsed_args = json.loads(raw_args) if raw_args.strip() else {}
                    except json.JSONDecodeError:
                        parsed_args = {"raw": raw_args}
                else:
                    parsed_args = raw_args if isinstance(raw_args, dict) else {}
                tool_calls.append(
                    {
                        "id": item.get("id", fn.get("name", "tool")),
                        "name": fn.get("name", ""),
                        "arguments": parsed_args,
                    }
                )
            content = message.get("content")
            parsed_content: dict[str, Any] | str | None = content
            if isinstance(content, str) and content.strip().startswith("{"):
                try:
                    parsed_content = _parse_json_text(content)
                except json.JSONDecodeError:
                    parsed_content = content
            output_payload = {"content": parsed_content, "tool_calls": tool_calls}
            return output_payload
        except Exception as exc:
            error = exc
            raise
        finally:
            record_model_call(
                self,
                call_kind="chat_tools",
                profile=profile,
                model=model,
                driver=chat_driver_for_profile(self, profile),
                input_payload=input_payload,
                started=started,
                output_payload=output_payload,
                output_valid=error is None,
                error=error,
                token_usage=self.last_token_usage,
                usage_units=self._chat_usage_units(),
            )

    def generate_image(self, prompt: str, *, options: dict[str, Any] | None = None) -> bytes:
        provider = self._image()
        model = provider.config.model
        started = time.perf_counter()
        output_payload: dict[str, Any] | None = None
        error: Exception | None = None
        usage_units: dict[str, Any] | None = None
        try:
            result = provider.generate(prompt, options=options)
            self.last_latency_ms = provider.last_latency_ms
            output_payload = {
                "bytes": len(result),
                "mime": "image/png",
            }
            from evaluation.usage_normalize import usage_units_images

            usage_units = usage_units_images(1)
            return result
        except Exception as exc:
            error = exc
            raise
        finally:
            record_model_call(
                self,
                call_kind="image",
                profile="image",
                model=model,
                driver=image_driver(self),
                input_payload={"prompt": prompt, "options": options or {}},
                started=started,
                output_payload=output_payload,
                output_valid=error is None,
                error=error,
                usage_units=usage_units if error is None else None,
            )

    def synthesize_speech(self, text: str, *, options: dict[str, Any] | None = None) -> bytes:
        provider = self._tts()
        model = self.config.tts.model
        started = time.perf_counter()
        output_payload: dict[str, Any] | None = None
        error: Exception | None = None
        merged = dict(options or {})
        usage_units: dict[str, Any] | None = None
        try:
            result = provider.synthesize(text, options=merged or None)
            self.last_latency_ms = provider.last_latency_ms
            output_payload = {
                "bytes": len(result),
                "mime": "audio/wav",
                "charCount": len(text),
            }
            from evaluation.usage_normalize import usage_units_chars

            usage_units = usage_units_chars(len(text))
            return result
        except Exception as exc:
            error = exc
            raise
        finally:
            record_model_call(
                self,
                call_kind="tts",
                profile="tts",
                model=model,
                driver=tts_driver(self),
                input_payload={"text": text, "options": merged},
                started=started,
                output_payload=output_payload,
                output_valid=error is None,
                error=error,
                usage_units=usage_units,
            )

    def submit_video_job(self, prompt: str, *, options: dict[str, Any] | None = None) -> str:
        provider = self._video()
        model = self.config.video.model
        opts = dict(options or {})
        if self.observability is not None and opts.get("slotId"):
            self.observability.slot_id = str(opts["slotId"])
        started = time.perf_counter()
        output_payload: dict[str, Any] | None = None
        error: Exception | None = None
        job_id: str | None = None
        usage_units: dict[str, Any] | None = None
        try:
            job_id = provider.submit(prompt, opts)
            output_payload = {"jobId": job_id}
            from evaluation.usage_normalize import usage_units_video_seconds

            requested = opts.get("durationSec")
            usage_units = usage_units_video_seconds(
                requested=float(requested) if requested is not None else None,
            )
            return job_id
        except Exception as exc:
            error = exc
            raise
        finally:
            record_model_call(
                self,
                call_kind="video_submit",
                profile="video",
                model=model,
                driver=video_driver(self),
                input_payload={"prompt": prompt, "options": opts},
                started=started,
                output_payload=output_payload,
                output_valid=error is None,
                error=error,
                job_id=job_id,
                usage_units=usage_units,
            )

    def poll_video_job(self, job_id: str) -> VideoJobResult:
        provider = self._video()
        model = self.config.video.model
        started = time.perf_counter()
        output_payload: dict[str, Any] | None = None
        error: Exception | None = None
        usage_units: dict[str, Any] | None = None
        try:
            result = provider.poll(job_id)
            self.last_latency_ms = result.latency_ms
            output_payload = {
                "status": result.status,
                "bytes": len(result.video_bytes or b""),
            }
            if result.video_bytes:
                from evaluation.ffprobe_util import probe_video_bytes_duration_sec
                from evaluation.usage_normalize import usage_units_video_seconds

                actual = probe_video_bytes_duration_sec(result.video_bytes)
                if actual is not None:
                    output_payload["durationSec"] = actual
                    usage_units = usage_units_video_seconds(actual=actual)
            return result
        except Exception as exc:
            error = exc
            raise
        finally:
            record_model_call(
                self,
                call_kind="video_poll",
                profile="video",
                model=model,
                driver=video_driver(self),
                input_payload={"jobId": job_id},
                started=started,
                output_payload=output_payload,
                output_valid=error is None,
                error=error,
                job_id=job_id,
                usage_units=usage_units,
            )
