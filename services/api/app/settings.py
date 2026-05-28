from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    database_path: Path
    storage_root: Path
    log_dir: Path | None = None
