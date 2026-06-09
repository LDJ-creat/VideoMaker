from __future__ import annotations

import os
from pathlib import Path


def detect_repo_root() -> Path:
    env_root = os.getenv("VIDEOMAKER_REPO_ROOT")
    if env_root:
        return Path(env_root).resolve()
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "packages" / "contracts").is_dir():
            return parent
    raise FileNotFoundError("Could not detect VideoMaker repo root")


def skills_public_dir(repo_root: Path | None = None) -> Path:
    return (repo_root or detect_repo_root()) / "skills" / "public"


def skills_private_dir(repo_root: Path | None = None) -> Path:
    return (repo_root or detect_repo_root()) / "skills" / "private"


def resolve_storage_path(storage_root: Path, relative_uri: str) -> Path:
    root = storage_root.resolve()
    candidate = (root / relative_uri).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Storage path escapes storage root")
    return candidate
