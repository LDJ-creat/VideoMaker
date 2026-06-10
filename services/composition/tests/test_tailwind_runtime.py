from __future__ import annotations

from composition.build.composition_shell import write_index_html
from composition.build.tailwind_runtime import (
    TAILWIND_BROWSER_SRC,
    html_uses_tailwind_classes,
    inject_tailwind_browser_script,
)


def test_html_uses_tailwind_classes_detects_utilities() -> None:
    html = '<div class="w-full h-full flex items-center bg-black/30 rounded-2xl">x</div>'
    assert html_uses_tailwind_classes(html)


def test_html_uses_tailwind_classes_ignores_plain_css_classes() -> None:
    assert not html_uses_tailwind_classes('<div class="benefit-card scene-label">x</div>')


def test_inject_tailwind_browser_script_adds_ready_gate() -> None:
    html = "<html><head></head><body></body></html>"
    injected = inject_tailwind_browser_script(html)
    assert "window.__tailwindReady" in injected
    assert TAILWIND_BROWSER_SRC in injected


def test_write_index_html_injects_tailwind_for_utility_markup(tmp_path) -> None:
    write_index_html(
        composition_dir=tmp_path,
        body_html=(
            '<div class="w-full h-full flex flex-col justify-center items-center '
            'bg-black/30"><p class="text-2xl font-bold text-white">章节</p></div>'
        ),
        styles="",
        timeline_script='tl.set("#root", { autoAlpha: 1 }, 0);',
        duration_sec=3.0,
        canvas_width=1080,
        canvas_height=1920,
    )
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "window.__tailwindReady" in html
    assert TAILWIND_BROWSER_SRC in html
