from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ID = "cb39c1b3-f3f3-4a21-ada0-f1c9938df0be"
VIDEO_PATH = Path(r"c:\Users\FLDJ\Downloads\抖音202665-044495.mp4")
API_BASE = "http://127.0.0.1:8000"
RETRY_TASK_ID = "63e440e0-e85a-4fa6-bb28-e86c949de0cc"
RETRY_SAMPLE_ID = "d73eb213-23e8-4c3e-a1c5-1fcc16d01a5a"


def _post_multipart(url: str, field_name: str, file_path: Path) -> dict:
    boundary = "----VideoMakerBoundary"
    filename = file_path.name
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: video/mp4\r\n\r\n"
    ).encode("utf-8")
    body += file_path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())


def _post_json(url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read())


def main() -> int:
    if not VIDEO_PATH.is_file():
        print(f"Missing video: {VIDEO_PATH}", file=sys.stderr)
        return 1

    status = _get_json(f"{API_BASE}/api/settings/model-gateway")
    print(
        "route preview:",
        status.get("analysisRoutePreview"),
        "prefs:",
        status.get("preferences"),
    )

    if RETRY_TASK_ID and RETRY_SAMPLE_ID:
        sample_id = RETRY_SAMPLE_ID
        task = _post_json(f"{API_BASE}/api/tasks/{RETRY_TASK_ID}/retry")
        task_id = task.get("taskId") or RETRY_TASK_ID
        print("retry task:", task_id)
    else:
        sample = _post_multipart(
            f"{API_BASE}/api/projects/{PROJECT_ID}/samples/upload",
            "file",
            VIDEO_PATH,
        )
        sample_id = sample["id"]
        print("uploaded sample:", sample_id, sample.get("status"))

        task = _post_json(f"{API_BASE}/api/samples/{sample_id}/analyze")
        task_id = task.get("taskId") or task.get("id")
        print("analyze task:", task_id, task.get("status"))

    final: dict | None = None
    for tick in range(180):
        time.sleep(5)
        state = _get_json(f"{API_BASE}/api/tasks/{task_id}")
        print(
            f"[{tick * 5}s] status={state.get('status')} "
            f"stage={state.get('stage')} progress={state.get('progress')} "
            f"message={state.get('message')!r}",
        )
        if state.get("status") in {"succeeded", "failed", "cancelled"}:
            final = state
            break

    if final is None:
        print("Timed out waiting for task", file=sys.stderr)
        return 2

    if final.get("status") != "succeeded":
        print("FAILED:", json.dumps(final, ensure_ascii=False, indent=2))
        return 3

    analysis = _get_json(f"{API_BASE}/api/samples/{sample_id}/sample-analysis")
    structure = _get_json(f"{API_BASE}/api/samples/{sample_id}/structure")
    print("structureAnalysisRoute:", analysis.get("structureAnalysisRoute"))
    warnings = (structure.get("analysisQuality") or {}).get("warnings") or []
    print("warnings count:", len(warnings))
    print("route warnings:", [w for w in warnings if "analysis_route" in w or "direct" in w])
    print("segment count:", len((structure.get("narrative") or {}).get("segments") or []))
    print("slot count:", len(structure.get("slots") or []))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
