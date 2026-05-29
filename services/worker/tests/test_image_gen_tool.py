from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.tools.image_gen_tool import ImageGenTool, ToolError


def test_generate_writes_bytes_and_returns_artifact_ref(tmp_path: Path) -> None:
    png = b"\x89PNG\r\n\x1a\n\x00"
    gateway = MagicMock()
    gateway.generate_image.return_value = png
    emitted: list[tuple[str, str]] = []

    tool = ImageGenTool(
        gateway=gateway,
        emit_progress=lambda stage, message: emitted.append((stage, message)),
    )
    output_path = tmp_path / "slot-hook.png"
    ref = tool.generate(prompt="product hero shot", output_path=output_path)

    assert output_path.read_bytes() == png
    gateway.generate_image.assert_called_once_with("product hero shot", options=None)
    assert ref["type"] == "image"
    assert Path(ref["uri"]) == output_path.resolve()
    assert emitted == [("generating_image", "Generating image")]


def test_generate_wraps_gateway_errors(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.generate_image.side_effect = RuntimeError("upstream failed")
    tool = ImageGenTool(gateway=gateway)

    with pytest.raises(ToolError) as exc_info:
        tool.generate(prompt="x", output_path=tmp_path / "out.png")

    assert exc_info.value.code == "image_generation_failed"
    assert exc_info.value.retryable is True
