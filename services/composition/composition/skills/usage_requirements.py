from __future__ import annotations

REQUIRED_PRIVATE_SKILL_PATHS: tuple[str, ...] = (
    "skills/private/videomaker-composition/SKILL.md",
    "skills/private/videomaker-visual-craft/SKILL.md",
)

REQUIRED_VISUAL_CRAFT_REFERENCE_PATHS: tuple[str, ...] = (
    "skills/private/videomaker-visual-craft/references/ANTI-AI-FINGERPRINTS.md",
    "skills/private/videomaker-visual-craft/references/SLOT-VISUAL-CRAFT.md",
)

VISUAL_BIBLE_EXTRA_READ_PATHS: tuple[str, ...] = (
    "skills/private/videomaker-visual-craft/references/PALETTE-FROM-BIBLE.md",
)


def normalize_skill_location(location: str) -> str:
    return str(location or "").replace("\\", "/").strip()


def record_skill_view(viewed: set[str], location: str) -> None:
    normalized = normalize_skill_location(location)
    if normalized:
        viewed.add(normalized)


def skill_view_requirement_error(
    viewed: set[str],
    *,
    has_visual_style_bible: bool,
) -> str | None:
    for path in REQUIRED_PRIVATE_SKILL_PATHS:
        if path not in viewed:
            return (
                "skill_usage_rule: must skill_view both private skills before submit_material_spec; "
                f"missing {path}"
            )
    for path in REQUIRED_VISUAL_CRAFT_REFERENCE_PATHS:
        if path not in viewed:
            return (
                "skill_usage_rule: must skill_view visual-craft references before submit_material_spec; "
                f"missing {path}"
            )
    if has_visual_style_bible:
        for path in VISUAL_BIBLE_EXTRA_READ_PATHS:
            if path not in viewed:
                return (
                    "skill_usage_rule: visualStyleBible present — must skill_view "
                    f"{path} before submit_material_spec"
                )
    return None


def visual_craft_bootstrap_section() -> str:
    return "\n".join(
        [
            "# Visual design (videomaker-visual-craft)",
            "Priority: visualStyleBible.avoid > visualStyleBible > videomaker-visual-craft > hyperframes house-style.",
            "hyperframes house-style allows intentional exceptions; VideoMaker slot packaging does NOT — no purple-pink diagonal gradients, no left-border accent cards.",
            "",
            "Before submit_material_spec you MUST skill_view:",
            f"- {REQUIRED_PRIVATE_SKILL_PATHS[0]}",
            f"- {REQUIRED_PRIVATE_SKILL_PATHS[1]}",
            f"- {REQUIRED_VISUAL_CRAFT_REFERENCE_PATHS[0]}",
            f"- {REQUIRED_VISUAL_CRAFT_REFERENCE_PATHS[1]}",
            f"- {VISUAL_BIBLE_EXTRA_READ_PATHS[0]} when user payload includes visualStyleBible",
            "",
            "In composition.styles declare :root { --vm-bg; --vm-fg; --vm-accent; --vm-muted; } and use var(--vm-*) — no default AI purple hex.",
            "At least one content-driven motion beat per slot (not only fade/blur). Hold the final frame through slotTiming.durationSec.",
        ]
    )
