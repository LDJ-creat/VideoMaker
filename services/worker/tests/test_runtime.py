from pathlib import Path

import pytest

from app.runtime.artifact_store import ArtifactStore
from app.runtime.task_context import TaskContext


def test_artifact_store_writes_under_project_scope(tmp_path: Path) -> None:
    store = ArtifactStore(storage_root=tmp_path, project_id="proj-1")

    written = store.write_json(
        "samples/sample-1/metadata.json",
        {"durationSec": 3.2},
    )

    assert written.exists()
    assert written.is_file()
    assert written.is_relative_to(tmp_path / "projects" / "proj-1")


@pytest.mark.parametrize(
    "unsafe_relpath",
    [
        "../escape.json",
        "..\\escape.json",
        "samples/../../escape.json",
    ],
)
def test_artifact_store_rejects_path_traversal(
    tmp_path: Path, unsafe_relpath: str
) -> None:
    store = ArtifactStore(storage_root=tmp_path, project_id="proj-1")

    with pytest.raises(ValueError):
        store.resolve(unsafe_relpath)


def test_task_context_uses_project_scoped_artifact_store(tmp_path: Path) -> None:
    context = TaskContext(project_id="proj-1", task_id="task-1", storage_root=tmp_path)

    output_path = context.artifacts.write_text(
        "samples/sample-1/note.txt",
        "ok",
    )

    assert output_path.read_text(encoding="utf-8") == "ok"
    assert output_path.is_relative_to(tmp_path / "projects" / "proj-1")
