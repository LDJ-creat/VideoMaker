from __future__ import annotations

from pathlib import Path

import uvicorn

from app.logging_config import configure_logging


def main() -> None:
    storage_root = Path.cwd() / "storage"
    log_dir = configure_logging(storage_root)
    print(f"VideoMaker API logs: {log_dir / 'api.log'} (worker: {log_dir / 'worker.log'})")

    # Only watch application source. Runtime writes under storage/ must not trigger reload.
    app_dir = Path(__file__).resolve().parent

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(app_dir)],
    )


if __name__ == "__main__":
    main()
