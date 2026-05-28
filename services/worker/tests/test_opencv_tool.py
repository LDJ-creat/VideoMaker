from __future__ import annotations

from pathlib import Path

from app.tools.opencv_tool import OpenCVTool, build_shot_boundaries, score_keyframe_candidates


def test_detect_shots_returns_fallback_when_opencv_missing(tmp_path: Path) -> None:
    tool = OpenCVTool(cv2_module=None)
    result = tool.detect_shots(tmp_path / "missing.mp4", duration_sec=6.0)

    assert len(result["shots"]) == 1
    assert result["shots"][0]["startSec"] == 0.0
    assert result["shots"][0]["endSec"] == 6.0
    assert result["warning"]["code"] == "opencv_missing"
    assert result["warning"]["retryable"] is True


def test_build_shot_boundaries_detects_cut_from_distances() -> None:
    distances = [0.02, 0.03, 0.62, 0.04]
    sample_times = [0.0, 0.5, 1.0, 1.5, 2.0]
    shots = build_shot_boundaries(distances, sample_times, duration_sec=2.0)

    assert len(shots) == 2
    assert shots[0]["startSec"] == 0.0
    assert shots[0]["endSec"] == 1.5
    assert shots[1]["startSec"] == 1.5
    assert shots[1]["endSec"] == 2.0


def test_keyframe_scoring_picks_sharpest_candidate() -> None:
    candidates = [
        {"timeSec": 1.0, "sharpness": 10.0, "entropy": 0.2, "meanBrightness": 127.0},
        {"timeSec": 1.5, "sharpness": 200.0, "entropy": 0.5, "meanBrightness": 127.0},
        {"timeSec": 2.0, "sharpness": 30.0, "entropy": 0.7, "meanBrightness": 127.0},
    ]
    best = score_keyframe_candidates(candidates)

    assert best is not None
    assert best["timeSec"] == 1.5


def test_detect_shots_finds_boundary_from_synthetic_frames() -> None:
    class _Capture:
        def __init__(self) -> None:
            self._position = 0
            self._frames = [0, 0, 1]

        def isOpened(self) -> bool:
            return True

        def get(self, prop: int) -> float:
            if prop == 1:
                return 3.0
            if prop == 2:
                return float(len(self._frames))
            return 0.0

        def set(self, prop: int, value: float) -> None:
            if prop == 3:
                self._position = int(value)

        def read(self):
            if self._position >= len(self._frames):
                return False, None
            frame = self._frames[self._position]
            return True, frame

        def release(self) -> None:
            return None

    class _Hist:
        def __init__(self, value: float) -> None:
            self.value = value

        def flatten(self) -> float:
            return self.value

    class _FakeCv2:
        CAP_PROP_FPS = 1
        CAP_PROP_FRAME_COUNT = 2
        CAP_PROP_POS_FRAMES = 3
        COLOR_BGR2HSV = 10
        HISTCMP_CORREL = 20

        def VideoCapture(self, _: str) -> _Capture:  # noqa: N802
            return _Capture()

        def cvtColor(self, frame: int, _: int) -> int:  # noqa: N802
            return frame

        def calcHist(self, images, channels, mask, hist_size, ranges):  # noqa: N802, ANN001
            return _Hist(float(images[0]))

        def normalize(self, histogram: _Hist, _: _Hist) -> _Hist:  # noqa: N802
            return histogram

        def compareHist(self, prev: float, curr: float, method: int) -> float:  # noqa: N802, ARG002
            return 1.0 if prev == curr else 0.0

    tool = OpenCVTool(cv2_module=_FakeCv2())
    result = tool.detect_shots("synthetic.mp4", duration_sec=1.2)

    assert len(result["shots"]) == 2
    assert result["shots"][0]["startSec"] == 0.0
    assert result["shots"][1]["startSec"] > 0.0
