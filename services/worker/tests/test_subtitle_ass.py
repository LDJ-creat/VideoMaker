from __future__ import annotations

from pathlib import Path

from app.render.timeline_compiler.subtitle_ass import collect_subtitle_clips, write_ass_subtitles


def test_write_ass_subtitles_from_timeline(tmp_path: Path) -> None:
    timeline = {
        "durationSec": 10,
        "tracks": [
            {
                "id": "text",
                "type": "text",
                "clips": [
                    {
                        "id": "subtitle-master-1",
                        "startSec": 0.0,
                        "endSec": 2.5,
                        "content": "你好，世界",
                        "styleRef": "style://subtitle/clean",
                    },
                    {
                        "id": "subtitle-master-2",
                        "startSec": 2.5,
                        "endSec": 5.0,
                        "content": "Second line {test}",
                        "styleRef": "style://subtitle/bold",
                    },
                ],
            }
        ],
    }

    clips = collect_subtitle_clips(timeline)
    assert len(clips) == 2

    ass_path = tmp_path / "subtitles.ass"
    assert write_ass_subtitles(timeline, ass_path, aspect_ratio="9:16") is True
    content = ass_path.read_text(encoding="utf-8-sig")
    assert "Dialogue:" in content
    assert "你好，世界" in content
    assert "\\{test\\}" in content
    assert "Subtitle_clean" in content
    assert "Subtitle_bold" in content


def test_write_ass_returns_false_when_no_subtitles(tmp_path: Path) -> None:
    timeline = {"durationSec": 1, "tracks": [{"id": "text", "type": "text", "clips": []}]}
    assert write_ass_subtitles(timeline, tmp_path / "empty.ass") is False
