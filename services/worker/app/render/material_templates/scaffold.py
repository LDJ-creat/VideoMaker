from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path
from typing import Any

from app.validation.schema_loader import ValidationResult, validate_contract

_TEMPLATES_DIR = Path(__file__).resolve().parent
_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_INJECTION_MARKERS = ("<", ">", "javascript:")


class MaterialScaffoldError(ValueError):
    """Raised when MaterialSpec or template rendering is invalid."""


def sanitize_string(value: str) -> str:
    cleaned = value
    for marker in _INJECTION_MARKERS:
        cleaned = cleaned.replace(marker, "")
    return cleaned.strip()


def sanitize_params(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_string(value)
    if isinstance(value, list):
        return [sanitize_params(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_params(item) for key, item in value.items()}
    return value


def _sanitize_color(value: Any, *, fallback: str) -> str:
    if isinstance(value, str) and _HEX_COLOR.match(value):
        return value
    return fallback


def _load_fragment(name: str) -> str:
    path = _TEMPLATES_DIR / name
    if not path.exists():
        raise MaterialScaffoldError(f"Missing template fragment: {path.name}")
    return path.read_text(encoding="utf-8")


def _render_bullets(bullets: list[Any]) -> str:
    items: list[str] = []
    for index, bullet in enumerate(bullets):
        text = sanitize_string(str(bullet))
        if not text:
            continue
        items.append(
            f'<li class="bullet" style="--i:{index}">{html.escape(text)}</li>'
        )
    return "\n      ".join(items)


def _resolve_asset_path(
    asset_ref: dict[str, Any],
    *,
    asset_root: Path | None,
    composition_dir: Path,
) -> str:
    uri = str(asset_ref.get("uri", "")).strip()
    if not uri:
        raise MaterialScaffoldError("ken-burns requires assetRefs[0].uri")

    assets_dir = composition_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    if asset_root is not None:
        source = (asset_root / uri).resolve()
        root = asset_root.resolve()
        if not source.is_relative_to(root):
            raise MaterialScaffoldError("assetRef uri escapes asset sandbox")
        if not source.exists():
            raise MaterialScaffoldError(f"assetRef not found: {uri}")
        destination = assets_dir / source.name
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
        return f"assets/{destination.name}"

    if uri.startswith("assets/"):
        return uri
    raise MaterialScaffoldError("ken-burns requires asset_root to resolve assetRefs")


def _build_styles(
    *,
    primary: str,
    background: str,
    text: str,
    canvas_width: int,
    canvas_height: int,
) -> str:
    return f"""
      .card {{
        width: {canvas_width}px;
        height: {canvas_height}px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: {background};
        color: {text};
        font-family: Arial, sans-serif;
      }}
      .card-inner {{
        width: 72%;
        padding: 48px 56px;
        border-radius: 28px;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.12);
        box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
      }}
      .card-title {{
        font-size: 72px;
        line-height: 1.1;
        margin-bottom: 36px;
        color: {primary};
      }}
      .card-bullets {{
        list-style: none;
        padding: 0;
        margin: 0;
        display: grid;
        gap: 18px;
      }}
      .card-bullets .bullet {{
        font-size: 42px;
        opacity: 0;
        transform: translateY(24px);
        animation-name: bullet-in;
        animation-duration: 700ms;
        animation-timing-function: cubic-bezier(0.2, 0, 0, 1);
        animation-fill-mode: both;
        animation-delay: calc(400ms + (var(--i) * 180ms));
      }}
      @keyframes bullet-in {{
        from {{ opacity: 0; transform: translateY(24px); }}
        to {{ opacity: 1; transform: translateY(0); }}
      }}
      .lower-third {{
        width: {canvas_width}px;
        height: {canvas_height}px;
        position: relative;
        background: {background};
        color: {text};
        font-family: Arial, sans-serif;
      }}
      .lower-third-bar {{
        position: absolute;
        left: 96px;
        right: 96px;
        bottom: 120px;
        padding: 28px 36px;
        border-left: 8px solid {primary};
        background: rgba(0, 0, 0, 0.55);
        backdrop-filter: blur(8px);
        opacity: 0;
        transform: translateY(32px);
        animation-name: lower-third-in;
        animation-duration: 800ms;
        animation-timing-function: cubic-bezier(0.2, 0, 0, 1);
        animation-fill-mode: both;
        animation-delay: 200ms;
      }}
      .lower-third-title {{
        font-size: 56px;
        font-weight: 700;
        margin-bottom: 8px;
      }}
      .lower-third-subtitle {{
        font-size: 34px;
        opacity: 0.88;
      }}
      @keyframes lower-third-in {{
        from {{ opacity: 0; transform: translateY(32px); }}
        to {{ opacity: 1; transform: translateY(0); }}
      }}
      .ken-burns {{
        width: {canvas_width}px;
        height: {canvas_height}px;
        overflow: hidden;
        background: {background};
      }}
      .ken-burns-image {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        transform: scale(1);
        animation-name: ken-burns-zoom;
        animation-duration: var(--ken-duration, 4s);
        animation-timing-function: linear;
        animation-fill-mode: both;
      }}
      @keyframes ken-burns-zoom {{
        from {{ transform: scale(1); }}
        to {{ transform: scale(1.15); }}
      }}
    """


def _build_timeline_script(template: str, *, duration_sec: float) -> str:
    if template == "benefit-card":
        return """
      tl.from(".card-inner", { opacity: 0, y: 24, duration: 0.6 }, 0);
    """
    if template == "title-lower-third":
        return """
      tl.from(".lower-third-bar", { opacity: 0, y: 32, duration: 0.8 }, 0.2);
    """
    if template == "ken-burns":
        return f"""
      tl.to(".ken-burns-image", {{ scale: 1.15, duration: {duration_sec:g}, ease: "none" }}, 0);
    """
    return """
      tl.from(".card-inner", { opacity: 0, y: 24, duration: 0.6 }, 0);
    """


def _render_body(
    spec: dict[str, Any],
    *,
    asset_root: Path | None,
    composition_dir: Path,
    canvas_width: int,
    canvas_height: int,
) -> tuple[str, str, str]:
    template = spec["template"]
    params = sanitize_params(spec.get("params", {}))
    duration_sec = float(spec["durationSec"])
    duration = f"{duration_sec:g}"

    colors = params.get("colors") if isinstance(params.get("colors"), dict) else {}
    primary = _sanitize_color(colors.get("primary"), fallback="#2563eb")
    background = _sanitize_color(colors.get("background"), fallback="#0b0d12")
    text = _sanitize_color(colors.get("text"), fallback="#ffffff")
    title = sanitize_string(str(params.get("title", ""))) or "VideoMaker"
    subtitle = sanitize_string(str(params.get("subtitle", ""))) or ""

    if template == "benefit-card":
        bullets = params.get("bullets") if isinstance(params.get("bullets"), list) else []
        fragment = (
            _load_fragment("benefit_card.html")
            .replace("{{DURATION}}", duration)
            .replace("{{TITLE}}", html.escape(title))
            .replace("{{BULLETS}}", _render_bullets(bullets))
        )
    elif template == "title-lower-third":
        fragment = (
            _load_fragment("title_lower_third.html")
            .replace("{{DURATION}}", duration)
            .replace("{{TITLE}}", html.escape(title))
            .replace("{{SUBTITLE}}", html.escape(subtitle or title))
        )
    elif template == "ken-burns":
        asset_refs = params.get("assetRefs")
        if not isinstance(asset_refs, list) or not asset_refs:
            raise MaterialScaffoldError("ken-burns requires params.assetRefs[0]")
        image_src = _resolve_asset_path(
            asset_refs[0],
            asset_root=asset_root,
            composition_dir=composition_dir,
        )
        fragment = (
            _load_fragment("ken_burns.html")
            .replace("{{DURATION}}", duration)
            .replace("{{IMAGE_SRC}}", html.escape(image_src, quote=True))
        )
    elif template == "custom":
        fragment = (
            _load_fragment("benefit_card.html")
            .replace("{{DURATION}}", duration)
            .replace("{{TITLE}}", html.escape(title))
            .replace("{{BULLETS}}", "")
        )
    else:
        raise MaterialScaffoldError(f"Unsupported template: {template}")

    styles = _build_styles(
        primary=primary,
        background=background,
        text=text,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )
    timeline_script = _build_timeline_script(template, duration_sec=duration_sec)
    return fragment, styles, timeline_script


def _write_hyperframes_json(composition_dir: Path) -> None:
    payload = {
        "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
        "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
        "paths": {
            "blocks": "compositions",
            "components": "compositions/components",
            "assets": "assets",
        },
    }
    (composition_dir / "hyperframes.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_index_html(
    *,
    composition_dir: Path,
    body_html: str,
    styles: str,
    timeline_script: str,
    duration_sec: float,
    canvas_width: int,
    canvas_height: int,
) -> None:
    html_doc = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={canvas_width}, height={canvas_height}" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }}
      html,
      body {{
        margin: 0;
        width: {canvas_width}px;
        height: {canvas_height}px;
        overflow: hidden;
        background: #000;
      }}
      {styles}
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="{duration_sec:g}"
      data-width="{canvas_width}"
      data-height="{canvas_height}"
    >
      {body_html}
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      {timeline_script}
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
    (composition_dir / "index.html").write_text(html_doc, encoding="utf-8")


def validate_material_spec(spec: dict[str, Any]) -> ValidationResult:
    return validate_contract("material-spec", spec)


def ensure_paths_in_project_sandbox(project_root: Path, *paths: Path) -> None:
    root = project_root.resolve()
    for path in paths:
        candidate = path.resolve()
        if not candidate.is_relative_to(root):
            raise MaterialScaffoldError(f"Path escapes project sandbox: {path}")


def build_composition(
    spec: dict[str, Any],
    output_dir: Path,
    *,
    asset_root: Path | None = None,
    project_root: Path | None = None,
    aspect_ratio: str = "9:16",
) -> Path:
    from app.render.aspect_ratio import render_dimensions

    canvas_width, canvas_height = render_dimensions(aspect_ratio)
    validation = validate_material_spec(spec)
    if not validation.valid:
        messages = "; ".join(error.message for error in validation.errors)
        raise MaterialScaffoldError(f"Invalid MaterialSpec: {messages}")

    output_dir = output_dir.resolve()
    if project_root is not None:
        sandbox_paths = [output_dir]
        if asset_root is not None:
            sandbox_paths.append(asset_root.resolve())
        ensure_paths_in_project_sandbox(project_root, *sandbox_paths)

    output_dir.mkdir(parents=True, exist_ok=True)

    body_html, styles, timeline_script = _render_body(
        spec,
        asset_root=asset_root,
        composition_dir=output_dir,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )
    _write_hyperframes_json(output_dir)
    _write_index_html(
        composition_dir=output_dir,
        body_html=body_html,
        styles=styles,
        timeline_script=timeline_script,
        duration_sec=float(spec["durationSec"]),
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )
    return output_dir
