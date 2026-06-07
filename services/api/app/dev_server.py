from __future__ import annotations

from pathlib import Path

import uvicorn

from app.logging_config import configure_logging


def main() -> None:
    storage_root = Path.cwd() / "storage"
    log_dir = configure_logging(storage_root)
    print(f"VideoMaker API logs: {log_dir / 'api.log'} (worker: {log_dir / 'worker.log'})")

    # Watch API app + shared Python modules (model_gateway, stock_media, …).
    # Runtime writes under storage/ must not trigger reload.
    app_dir = Path(__file__).resolve().parent
    shared_dir = app_dir.parents[1] / "shared"

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(app_dir), str(shared_dir)],
        # Dev reload waits for open connections (e.g. task SSE from the web UI).
        # Without a cap, "Waiting for connections to close" can hang until Ctrl+C.
        timeout_graceful_shutdown=2,
    )


if __name__ == "__main__":
    main()
