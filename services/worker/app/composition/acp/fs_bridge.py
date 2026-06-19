from __future__ import annotations

from pathlib import Path

from knowledge.paths import assert_under_storage_root


class PathConfinementError(ValueError):
    pass


class FsBridge:
    """Scope ACP filesystem access to allowed workspace roots."""

    def __init__(self, *, allowed_roots: list[Path]) -> None:
        resolved = [root.resolve() for root in allowed_roots if root]
        if not resolved:
            raise ValueError("FsBridge requires at least one allowed root")
        self._allowed_roots = resolved

    def _resolve_allowed(self, path: str) -> Path:
        candidate = Path(path).resolve()
        for root in self._allowed_roots:
            try:
                assert_under_storage_root(candidate, root)
                return candidate
            except ValueError:
                continue
        raise PathConfinementError(f"path_escape_allowed_roots: {path}")

    def read_text(self, path: str) -> str:
        target = self._resolve_allowed(path)
        return target.read_text(encoding="utf-8")

    def write_text(self, path: str, content: str) -> None:
        target = self._resolve_allowed(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
