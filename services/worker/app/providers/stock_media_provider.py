from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from app.agents.stock_query_author import resolve_stock_search_query
from app.providers.material_types import MaterialContext, MaterialResult
from app.stock.stock_eligibility import completion_slot_for_stock, stock_max_candidates, stock_search_preferences
from app.stock.stock_scorer import pick_best_candidate
from app.stock.stock_segment_planner import StockSegment, build_stock_segments
from app.tools.ffmpeg_tool import FFmpegTool
from app.tools.image_gen_tool import ToolError
from app.tools.pexels_tool import PexelsTool, best_photo_src, best_video_file


class StockMediaProvider:
    name = "stock_media_search"

    def __init__(
        self,
        *,
        pexels_tool: PexelsTool | None = None,
        ffmpeg_tool: FFmpegTool | None = None,
    ) -> None:
        self._pexels = pexels_tool or PexelsTool()
        self._ffmpeg = ffmpeg_tool or FFmpegTool()

    def execute(self, action: dict[str, Any], ctx: MaterialContext) -> MaterialResult:
        slot_id = str(action["slotId"])
        structure_slot = _slot_for_id(slot_id, ctx.structure)
        if structure_slot is None:
            return _error(action, slot_id, "stock_slot_not_found", "Structure slot not found", fallback="image_generation")

        brief = (ctx.inventory or {}).get("userBrief") or {}
        brief_dict = brief if isinstance(brief, dict) else {}
        slot = completion_slot_for_stock(structure_slot, brief=brief_dict)
        scene = _scene_for_slot(slot_id, ctx.storyboard)
        gap_item = {"reason": str(action.get("reason", "")), "impact": "medium"}
        prefs = stock_search_preferences(
            slot,
            scene=scene,
            brief=brief_dict,
            aspect_ratio=ctx.aspect_ratio,
        )
        prefer_video = bool(prefs.get("preferVideo"))
        orientation = prefs.get("orientation")

        cached_query = action.get("stockSearchQuery")
        query_payload = resolve_stock_search_query(
            slot=slot,
            gap_item=gap_item,
            storyboard=ctx.storyboard,
            brief=brief_dict,
            prefer_video=prefer_video,
            orientation=orientation if isinstance(orientation, str) else None,
            runner=ctx.runner,
            context=ctx.task_context,
            generation_id=ctx.generation_id,
            cached=cached_query if isinstance(cached_query, dict) else None,
        )

        queries = [str(query_payload.get("primaryQuery", "")).strip()]
        queries.extend(
            str(item).strip()
            for item in (query_payload.get("fallbackQueries") or [])
            if str(item).strip()
        )
        queries = [query for query in queries if query]
        if not queries:
            return _error(
                action,
                slot_id,
                "stock_empty_query",
                "No stock search query available",
                fallback=_fallback_provider(prefer_video, ctx, slot_id),
            )

        target_duration = None
        if scene:
            target_duration = max(0.5, float(scene["endSec"]) - float(scene["startSec"]))

        segments = build_stock_segments(
            slot=slot,
            scene=scene,
            primary_query=queries[0],
            target_duration_sec=target_duration or 3.0,
        )
        fallback_queries = queries[1:]

        try:
            if len(segments) == 1:
                artifact_ref, attribution = self._materialize_segment(
                    segments[0],
                    slot_id=slot_id,
                    prefer_video=prefer_video,
                    orientation=orientation if isinstance(orientation, str) else None,
                    fallback_queries=fallback_queries,
                    output_path=ctx.generated_root / f"{slot_id}-stock.mp4",
                    photo_output_path=ctx.generated_root / f"{slot_id}-stock.jpg",
                    allow_photo_output=True,
                )
            else:
                artifact_ref, attribution = self._materialize_segmented_video(
                    segments,
                    slot_id=slot_id,
                    prefer_video=prefer_video,
                    orientation=orientation if isinstance(orientation, str) else None,
                    fallback_queries=fallback_queries,
                    generated_root=ctx.generated_root,
                )
        except ToolError as exc:
            return {
                "ok": False,
                "actionId": action["id"],
                "slotId": slot_id,
                "provider": self.name,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "retryable": exc.retryable,
                    "fallbackProvider": _fallback_provider(prefer_video, ctx, slot_id),
                },
            }

        registered = ctx.register_artifact(artifact_ref["type"], artifact_ref["uri"])
        return {
            "ok": True,
            "actionId": action["id"],
            "slotId": slot_id,
            "provider": self.name,
            "artifactRef": registered,
            "stockAttribution": attribution,
            "stockSearchQuery": query_payload,
            "generatedBy": {
                "provider": self.name,
                "source": "pexels",
                "photographer": attribution["photographer"],
                "pageUrl": attribution["pageUrl"],
            },
        }

    def _pick_candidate(
        self,
        *,
        queries: list[str],
        prefer_video: bool,
        orientation: str | None,
        target_duration_sec: float | None,
    ) -> tuple[dict[str, Any], str, str]:
        per_page = stock_max_candidates()
        min_duration = None
        if target_duration_sec is not None and target_duration_sec > 0:
            min_duration = max(1, math.ceil(target_duration_sec))
        for query in queries:
            photos = self._pexels.search_photos(
                query,
                orientation=orientation,
                per_page=per_page,
            )
            videos = self._pexels.search_videos(
                query,
                orientation=orientation,
                per_page=per_page,
                min_duration=min_duration,
            )
            candidate, media_type, _score = pick_best_candidate(
                query=query,
                photos=photos,
                videos=videos,
                prefer_video=prefer_video,
                target_duration_sec=target_duration_sec,
                orientation=orientation,
            )
            if candidate is not None and media_type is not None:
                return candidate, media_type, query
        raise ToolError(
            code="pexels_no_results",
            message="No suitable Pexels media found for slot",
            retryable=False,
        )

    def _materialize_segment(
        self,
        segment: StockSegment,
        *,
        slot_id: str,
        prefer_video: bool,
        orientation: str | None,
        fallback_queries: list[str],
        output_path: Path,
        photo_output_path: Path,
        allow_photo_output: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        queries = [segment.query, *fallback_queries]
        item, media_type, query = self._pick_candidate(
            queries=queries,
            prefer_video=prefer_video,
            orientation=orientation,
            target_duration_sec=segment.duration_sec,
        )
        if media_type == "video":
            raw_path = output_path.parent / f"{slot_id}-stock-raw-{segment.label or 'single'}.mp4"
            return self._materialize_video(
                item,
                slot_id=slot_id,
                query=query,
                raw_path=raw_path,
                output_path=output_path,
                duration_sec=segment.duration_sec,
            )
        if not allow_photo_output:
            raise ToolError(
                code="pexels_no_video_file",
                message="Segmented stock composition requires video clips",
                retryable=False,
            )
        return self._materialize_photo(item, slot_id=slot_id, query=query, output_path=photo_output_path)

    def _materialize_segmented_video(
        self,
        segments: list[StockSegment],
        *,
        slot_id: str,
        prefer_video: bool,
        orientation: str | None,
        fallback_queries: list[str],
        generated_root: Path,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        clip_paths: list[Path] = []
        photographers: list[str] = []
        page_urls: list[str] = []
        for index, segment in enumerate(segments):
            label = segment.label or f"seg-{index + 1}"
            clip_path = generated_root / f"{slot_id}-stock-part-{label}.mp4"
            artifact_ref, attribution = self._materialize_segment(
                segment,
                slot_id=slot_id,
                prefer_video=True,
                orientation=orientation,
                fallback_queries=fallback_queries,
                output_path=clip_path,
                photo_output_path=generated_root / f"{slot_id}-stock-part-{label}.jpg",
                allow_photo_output=True,
            )
            if artifact_ref["type"] == "image":
                image_video_path = generated_root / f"{slot_id}-stock-part-{label}.mp4"
                still_result = self._ffmpeg.still_image_to_video(
                    artifact_ref["uri"],
                    image_video_path,
                    duration_sec=segment.duration_sec,
                )
                if still_result.get("code"):
                    raise ToolError(
                        code=str(still_result.get("code", "stock_still_to_video_failed")),
                        message=str(still_result.get("message", "ffmpeg still-to-video failed")),
                        retryable=bool(still_result.get("retryable", True)),
                    )
                clip_paths.append(image_video_path)
            else:
                clip_paths.append(Path(artifact_ref["uri"]))
            photographers.append(str(attribution.get("photographer", "Pexels Contributor")))
            page_urls.append(str(attribution.get("pageUrl", "https://www.pexels.com")))

        output_path = generated_root / f"{slot_id}-stock.mp4"
        concat_result = self._ffmpeg.concat_clips(clip_paths, output_path)
        if concat_result.get("code"):
            raise ToolError(
                code=str(concat_result.get("code", "stock_concat_failed")),
                message=str(concat_result.get("message", "ffmpeg concat failed")),
                retryable=bool(concat_result.get("retryable", True)),
            )
        attribution = {
            "source": "pexels",
            "mediaId": 0,
            "pageUrl": page_urls[0] if page_urls else "https://www.pexels.com",
            "photographer": ", ".join(dict.fromkeys(photographers)),
            "query": " | ".join(segment.query for segment in segments),
            "mediaType": "video",
            "segmentCount": len(segments),
        }
        return {"type": "video", "uri": str(output_path.resolve())}, attribution

    def _materialize_video(
        self,
        item: dict[str, Any],
        *,
        slot_id: str,
        query: str,
        raw_path: Path,
        output_path: Path,
        duration_sec: float,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        video_file = best_video_file(item)
        if video_file is None or not str(video_file.get("link", "")).strip():
            raise ToolError(
                code="pexels_no_video_file",
                message="Pexels video has no downloadable file",
                retryable=False,
            )
        self._pexels.download(str(video_file["link"]), raw_path)
        trim_result = self._ffmpeg.trim_clip(
            raw_path,
            output_path,
            start_sec=0.0,
            duration_sec=duration_sec,
        )
        if trim_result.get("code"):
            raise ToolError(
                code=str(trim_result.get("code", "stock_trim_failed")),
                message=str(trim_result.get("message", "ffmpeg trim failed")),
                retryable=bool(trim_result.get("retryable", True)),
            )
        photographer = str((item.get("user") or {}).get("name", "Pexels Contributor"))
        attribution = {
            "source": "pexels",
            "mediaId": int(item.get("id") or 0),
            "pageUrl": str(item.get("url", "https://www.pexels.com")),
            "photographer": photographer,
            "query": query,
            "mediaType": "video",
        }
        return {"type": "video", "uri": str(output_path.resolve())}, attribution

    def _materialize_photo(
        self,
        item: dict[str, Any],
        *,
        slot_id: str,
        query: str,
        output_path: Path,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        src = best_photo_src(item)
        if not src:
            raise ToolError(
                code="pexels_no_photo_src",
                message="Pexels photo has no downloadable source",
                retryable=False,
            )
        self._pexels.download(src, output_path)
        photographer = str(item.get("photographer", "Pexels Contributor"))
        attribution = {
            "source": "pexels",
            "mediaId": int(item.get("id") or 0),
            "pageUrl": str(item.get("url", "https://www.pexels.com")),
            "photographer": photographer,
            "query": query,
            "mediaType": "photo",
        }
        return {"type": "image", "uri": str(output_path.resolve())}, attribution


def _fallback_provider(prefer_video: bool, ctx: MaterialContext, slot_id: str) -> str:
    if prefer_video and ctx.quota.can_generate_for_slot(slot_id):
        return "video_generation"
    return "image_generation"


def _error(
    action: dict[str, Any],
    slot_id: str,
    code: str,
    message: str,
    *,
    fallback: str,
) -> MaterialResult:
    return {
        "ok": False,
        "actionId": action["id"],
        "slotId": slot_id,
        "provider": "stock_media_search",
        "error": {
            "code": code,
            "message": message,
            "retryable": False,
            "fallbackProvider": fallback,
        },
    }


def _slot_for_id(slot_id: str, structure: dict[str, Any]) -> dict[str, Any] | None:
    for slot in structure.get("slots", []):
        if isinstance(slot, dict) and slot.get("id") == slot_id:
            return slot
    return None


def _scene_for_slot(slot_id: str, storyboard: list[dict[str, Any]]) -> dict[str, Any] | None:
    for scene in storyboard:
        if scene.get("slotId") == slot_id:
            return scene
    return None
