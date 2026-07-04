from __future__ import annotations

import re
from pathlib import Path

# Keep in sync with HyperFrames CLI (`hyperframes init --tailwind`).
TAILWIND_BROWSER_VERSION = "4.2.4"
TAILWIND_BROWSER_SRC = (
    f"https://cdn.jsdelivr.net/npm/@tailwindcss/browser@{TAILWIND_BROWSER_VERSION}"
    "/dist/index.global.js"
)
TAILWIND_BROWSER_INTEGRITY = (
    "sha384-v5YF9xS+gLRWdvrQ0u/WRbCkjSIH0NjHIPe8tBL1ZRrmI7PiSH6LLdzs0aAIMCuh"
)

_TAILWIND_CLASS_HINT = re.compile(
    r"""class=["'][^"']*(?:
        \b(?:flex|grid|absolute|relative|inset-0|w-full|h-full|object-cover|
        overflow-hidden|justify-|items-|place-|gap-|max-w-|min-h-|
        text-(?:xs|sm|base|lg|xl|2xl|3xl|[0-9]xl|white|gray|black)|
        bg-(?:black|white|blue|gray|gradient|transparent)|
        rounded(?:-2xl|-xl|-lg|-full|\b)|
        backdrop-blur|drop-shadow|border(?:-white|-black|\b)|
        font-(?:bold|black|medium|semibold|sans|mono)|
        opacity-|from-|via-|to-|px-|py-|p-\d|pt-|pb-|pl-|pr-|
        mt-|mb-|mx-|my-|leading-|tracking-|uppercase|lowercase|
        pointer-events-none|blur-sm|shadow-lg|shadow-xl|safe-area|
        col-span-|grid-cols-|translate-y-|scale-|z-\d+)
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def html_uses_tailwind_classes(html: str) -> bool:
    """Heuristic: material_author often emits Tailwind utility classes without runtime."""
    if not html.strip():
        return False
    if 'type="text/tailwindcss"' in html or "type='text/tailwindcss'" in html:
        return True
    if "@theme" in html or "@utility" in html:
        return True
    return bool(_TAILWIND_CLASS_HINT.search(html))


def inject_tailwind_browser_script(html: str) -> str:
    """Inject Tailwind v4 browser runtime + __tailwindReady gate (HyperFrames contract)."""
    if TAILWIND_BROWSER_SRC in html or "window.__tailwindReady" in html:
        return html
    script = "\n".join(
        [
            "<script>",
            "window.__tailwindReady=new Promise(function(resolve){",
            'var loaded=document.readyState==="complete";',
            "var resolved=false;",
            "var observer;",
            'function readTailwindCss(){var styles=document.querySelectorAll("style");'
            'for(var i=styles.length-1;i>=0;i--){var text=styles[i].textContent||"";'
            'if(text.indexOf("tailwindcss v")!==-1)return text;}return "";}',
            "function finish(){if(resolved||!loaded||!readTailwindCss())return;"
            "resolved=true;if(observer)observer.disconnect();resolve(true);}",
            "observer=new MutationObserver(finish);",
            "observer.observe(document.documentElement,"
            "{childList:true,subtree:true,characterData:true});",
            'if(loaded){finish();}else{window.addEventListener("load",function(){'
            'loaded=true;finish();},{once:true});}',
            "});",
            "</script>",
            f'<script src="{TAILWIND_BROWSER_SRC}" '
            f'integrity="{TAILWIND_BROWSER_INTEGRITY}" crossorigin="anonymous"></script>',
        ]
    )
    if re.search(r"</head>", html, re.IGNORECASE):
        return re.sub(
            r"</head>",
            f"\n{script}\n</head>",
            html,
            count=1,
            flags=re.IGNORECASE,
        )
    return f"{script}\n{html}"


def ensure_tailwind_runtime_in_index(index_path: Path) -> bool:
    """Patch an existing composition index.html when Tailwind utilities are present."""
    html = index_path.read_text(encoding="utf-8")
    if not html_uses_tailwind_classes(html):
        return False
    updated = inject_tailwind_browser_script(html)
    if updated == html:
        return False
    index_path.write_text(updated, encoding="utf-8")
    return True
