from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from composition.paths import detect_repo_root, skills_private_dir, skills_public_dir


@dataclass(frozen=True)
class SkillEntry:
    name: str
    description: str
    location: str


SKILL_DESCRIPTIONS: dict[str, str] = {
    "hyperframes": "HF 槽位 HTML 合成与 data-* 时间轴。触发：template=composition、包装 slot。",
    "gsap": "GSAP 确定性 timeline。触发：composition.timelineScript、场景动画。",
    "hyperframes-registry": "registry 区块安装与 wiring。触发：registryBlocks 字段。",
    "hyperframes-cli": "lint/render CLI 调试。触发：composition_lint_draft 失败排查。",
    "css-animations": "CSS 帧动画适配。触发：纯 CSS 动效、无 GSAP。",
    "lottie": "Lottie 动画嵌入。触发：composition 含 lottie 层。",
    "three": "Three.js WebGL 场景。触发：3D/粒子/visualizer 槽位。",
    "waapi": "Web Animations API。触发：element.animate 动效。",
    "animejs": "Anime.js 时间轴。触发：非 GSAP 的 anime 动画。",
    "videomaker-composition": "VideoMaker MaterialSpec 交卷约束。触发：任何 material 任务。",
    "videomaker-visual-craft": "槽位画面审美与反 AI 视觉指纹。触发：template=composition、HF 包装 slot。",
}


def _parse_frontmatter_description(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end < 0:
        return None
    frontmatter = text[3:end]
    match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def _skill_description(name: str, skill_md: Path, *, scope: str) -> str:
    if name in SKILL_DESCRIPTIONS:
        return SKILL_DESCRIPTIONS[name]
    if skill_md.is_file():
        parsed = _parse_frontmatter_description(skill_md.read_text(encoding="utf-8"))
        if parsed:
            return parsed[:120]
    if scope == "private":
        return "私有 skill。触发：VideoMaker 环境约束与交卷规则。"
    return f"HyperFrames 相关 skill。触发：槽位动效与 {name} 技术栈。"


class SkillCatalog:
    def __init__(self, *, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or detect_repo_root()).resolve()

    def _discover_dir(self, base: Path, *, scope: str) -> list[SkillEntry]:
        entries: list[SkillEntry] = []
        if not base.is_dir():
            return entries
        for child in sorted(base.iterdir()):
            skill_md = child / "SKILL.md"
            if not child.is_dir() or not skill_md.is_file():
                continue
            rel = skill_md.relative_to(self.repo_root).as_posix()
            name = child.name
            desc = _skill_description(name, skill_md, scope=scope)
            entries.append(SkillEntry(name=name, description=desc, location=rel))
        return entries

    def list_entries(self, extra: list[SkillEntry] | None = None) -> list[SkillEntry]:
        entries = self._discover_dir(skills_public_dir(self.repo_root), scope="public")
        entries.extend(self._discover_dir(skills_private_dir(self.repo_root), scope="private"))
        if not entries:
            private_skills = {"videomaker-composition", "videomaker-visual-craft"}
            entries = [
                SkillEntry(
                    name=name,
                    description=desc,
                    location=(
                        f"skills/private/{name}/SKILL.md"
                        if name in private_skills
                        else f"skills/public/{name}/SKILL.md"
                    ),
                )
                for name, desc in (
                    ("hyperframes", SKILL_DESCRIPTIONS["hyperframes"]),
                    ("gsap", SKILL_DESCRIPTIONS["gsap"]),
                    ("hyperframes-registry", SKILL_DESCRIPTIONS["hyperframes-registry"]),
                    ("videomaker-composition", SKILL_DESCRIPTIONS["videomaker-composition"]),
                    ("videomaker-visual-craft", SKILL_DESCRIPTIONS["videomaker-visual-craft"]),
                )
            ]
        if extra:
            entries.extend(extra)
        return entries

    def render_available_skills_xml(self, extra: list[SkillEntry] | None = None) -> str:
        lines = ["<available_skills>"]
        for entry in self.list_entries(extra=extra):
            lines.extend(
                [
                    "  <skill>",
                    f"    <name>{entry.name}</name>",
                    f"    <description>{entry.description}</description>",
                    f"    <location>{entry.location}</location>",
                    "  </skill>",
                ]
            )
        lines.append("</available_skills>")
        return "\n".join(lines)

    @staticmethod
    def skill_usage_rule_xml() -> str:
        from composition.skills.usage_requirements import (
            REQUIRED_PRIVATE_SKILL_PATHS,
            REQUIRED_VISUAL_CRAFT_REFERENCE_PATHS,
            VISUAL_BIBLE_EXTRA_READ_PATHS,
        )

        required_reads = list(REQUIRED_PRIVATE_SKILL_PATHS) + list(REQUIRED_VISUAL_CRAFT_REFERENCE_PATHS)
        return "\n".join(
            [
                "<skill_usage_rule>",
                "Before submit_material_spec, skill_view ALL required paths (enforced):",
                *[f"- {path}" for path in required_reads],
                f"- {VISUAL_BIBLE_EXTRA_READ_PATHS[0]} when visualStyleBible is in the user payload",
                "Also skill_view plausibly-relevant public skills (hyperframes, gsap, registry).",
                "</skill_usage_rule>",
            ]
        )
