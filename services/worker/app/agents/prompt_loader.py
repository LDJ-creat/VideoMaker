from __future__ import annotations

import hashlib
import os
from pathlib import Path


class PromptLoader:
    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root = repo_root or detect_repo_root()
        self._prompts_dir = self._repo_root / "packages" / "prompts" / "agents"
        self._cache: dict[str, str] = {}

    def load(self, agent_name: str) -> str:
        if agent_name not in self._cache:
            prompt_path = self._prompts_dir / f"{agent_name}.md"
            if not prompt_path.is_file():
                raise FileNotFoundError(f"Agent prompt not found: {prompt_path}")
            self._cache[agent_name] = prompt_path.read_text(encoding="utf-8")
        return self._cache[agent_name]

    def version(self, agent_name: str) -> str:
        content = self.load(agent_name)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]


def detect_repo_root() -> Path:
    env_root = os.getenv("VIDEOMAKER_REPO_ROOT")
    if env_root:
        return Path(env_root).resolve()

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "packages" / "prompts" / "agents").is_dir():
            return parent
    raise FileNotFoundError("Could not detect VideoMaker repo root")
