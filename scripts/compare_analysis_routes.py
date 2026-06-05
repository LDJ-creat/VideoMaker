from __future__ import annotations

import json
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8000"
TRADITIONAL = "bcb1f29b-cad4-4756-b049-13e64de7d093"
DIRECT = "d73eb213-23e8-4c3e-a1c5-1fcc16d01a5a"
PROJECT = "cb39c1b3-f3f3-4a21-ada0-f1c9938df0be"


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{API}{path}") as resp:
        return json.loads(resp.read())


def summarize(label: str, sample_id: str) -> dict:
    analysis = get(f"/api/samples/{sample_id}/sample-analysis")
    structure = get(f"/api/samples/{sample_id}/structure")
    segments = (structure.get("narrative") or {}).get("segments") or []
    slots = structure.get("slots") or []
    warnings = (structure.get("analysisQuality") or {}).get("warnings") or []
    roles = [s.get("role") for s in segments if isinstance(s, dict)]
    deep_fields = {
        "transcriptExcerpt": sum(1 for s in segments if (s.get("transcriptExcerpt") or "").strip()),
        "voStyle": sum(1 for s in segments if isinstance(s.get("voStyle"), dict)),
        "visualSpec": sum(1 for s in segments if isinstance(s.get("visualSpec"), dict)),
    }
    migration = sum(
        1 for slot in slots if len(str(slot.get("migrationTemplate") or "").strip()) >= 8
    )
    return {
        "label": label,
        "sampleId": sample_id,
        "route": analysis.get("structureAnalysisRoute", "map_reduce"),
        "batchDigests": len(analysis.get("keyframeBatchDigests") or []),
        "onScreenTextFacts": len(analysis.get("onScreenTextFacts") or []),
        "segmentCount": len(segments),
        "slotCount": len(slots),
        "roles": roles,
        "deepFields": deep_fields,
        "migrationTemplates": migration,
        "warnings": warnings,
        "summary": (structure.get("narrative") or {}).get("summary", "")[:120],
        "confidence": structure.get("confidence"),
    }


def main() -> None:
    trad = summarize("traditional", TRADITIONAL)
    direct = summarize("direct", DIRECT)
    print(json.dumps({"traditional": trad, "direct": direct}, ensure_ascii=False, indent=2))

    storage = Path(__file__).resolve().parents[1] / "services" / "api" / "storage"
    for sample_id in (TRADITIONAL, DIRECT):
        analysis_dir = storage / "projects" / PROJECT / "samples" / sample_id / "analysis"
        if not analysis_dir.exists():
            continue
        artifacts = sorted(p.name for p in analysis_dir.iterdir())
        print(f"\n{sample_id} artifacts:", artifacts)
        batch_dir = analysis_dir / "batch-digests"
        print(f"  batch-digests exists: {batch_dir.is_dir()}")


if __name__ == "__main__":
    main()
