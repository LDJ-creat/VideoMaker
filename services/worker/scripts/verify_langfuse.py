from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow `from app.observability...` when invoked as a script.
_WORKER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _WORKER_ROOT not in sys.path:
    sys.path.insert(0, _WORKER_ROOT)

from app.observability.langfuse_config import (  # noqa: E402
    LANGFUSE_CLOUD_REGIONS,
    LANGFUSE_DEFAULT_BASE_URL,
    detect_langfuse_base_url,
    resolve_langfuse_base_url,
    resolve_langfuse_client_kwargs,
)
from app.runtime.worker_python import (  # noqa: E402
    describe_worker_python,
    resolve_worker_python,
    worker_python_has_langfuse,
)


def main() -> int:
    enabled = os.getenv("LANGFUSE_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not enabled:
        print("LANGFUSE_ENABLED is not set to a truthy value.")
        print("Set LANGFUSE_ENABLED=true in services/api/langfuse.env or your shell.")
        return 1

    try:
        from langfuse import Langfuse, propagate_attributes
        from langfuse.api.commons.errors.unauthorized_error import UnauthorizedError
    except ImportError:
        print("langfuse package not installed.")
        print('Run: cd services/worker && .venv\\Scripts\\pip install -e ".[langfuse]"')
        return 1

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    if not public_key or not secret_key:
        print("Missing LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY.")
        return 1

    worker_python = resolve_worker_python()
    if Path(sys.executable).resolve() != Path(worker_python).resolve():
        print("Note: API worker subprocess uses a different Python than this script.")
        print(f"  script_python={describe_worker_python(sys.executable)}")
        print(f"  worker_python={describe_worker_python(worker_python)}")
        print("  Run this script via scripts/verify-langfuse.ps1 to target worker_python.")
        print()

    if not worker_python_has_langfuse(worker_python):
        print("Langfuse SDK is not installed in the worker Python used by API subprocesses.")
        print(f"  worker_python={describe_worker_python(worker_python)}")
        print('  Fix: cd services/api && uv pip install --python .venv\\Scripts\\python.exe "langfuse>=4.0,<5"')
        print("  Or restart via run-dev.ps1 (auto-installs when LANGFUSE_ENABLED=true).")
        return 1

    configured_base_url = resolve_langfuse_base_url()
    client_kwargs = resolve_langfuse_client_kwargs(
        public_key=public_key,
        secret_key=secret_key,
        auto_detect_region=not configured_base_url,
    )
    base_url = client_kwargs.get("base_url", LANGFUSE_DEFAULT_BASE_URL)

    client = Langfuse(**client_kwargs)
    try:
        auth_ok = client.auth_check()
    except UnauthorizedError:
        auth_ok = False

    if not auth_ok:
        detected = detect_langfuse_base_url(public_key, secret_key)
        print("Langfuse auth_check failed for the configured endpoint.")
        print(f"  configured_base_url={configured_base_url or '<unset, defaults to EU>'}")
        print(f"  attempted_base_url={base_url}")
        if detected and detected != base_url:
            print()
            print(f"Your API keys are valid on: {detected}")
            print("Add this line to services/api/langfuse.env:")
            print(f"LANGFUSE_BASE_URL={detected}")
        else:
            print()
            print("Verify the key pair in Langfuse → Project → Settings → API Keys.")
            print("If you use a regional cloud tenant, set LANGFUSE_BASE_URL to one of:")
            for region in LANGFUSE_CLOUD_REGIONS:
                print(f"  {region}")
        return 1

    if not configured_base_url and base_url != LANGFUSE_DEFAULT_BASE_URL:
        print(f"Auto-detected Langfuse cloud region: {base_url}")
        print("Recommended: add to services/api/langfuse.env:")
        print(f"LANGFUSE_BASE_URL={base_url}")
        print()

    trace_id = client.create_trace_id(seed="videomaker-langfuse-verify")
    with propagate_attributes(metadata={"source": "verify_langfuse.py"}):
        observation = client.start_observation(
            name="videomaker_langfuse_verify",
            as_type="generation",
            model="videomaker-verify",
            trace_context={"trace_id": trace_id},
        )
        observation.update(input={"ok": True}, output={"ok": True})
        observation.end()
    client.flush()

    print(f"OK: Langfuse flush succeeded (base_url={base_url})")
    print(f"Check Tracing in your Langfuse project for trace id: {trace_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
