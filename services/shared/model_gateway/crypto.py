from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet


def key_file_path(storage_root: Path) -> Path:
    return storage_root / "global" / "model-gateway.key"


def load_or_create_fernet(storage_root: Path) -> Fernet:
    path = key_file_path(storage_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        raw = path.read_bytes().strip()
    else:
        raw = Fernet.generate_key()
        path.write_bytes(raw)
    return Fernet(raw)


def encrypt_api_key(storage_root: Path, api_key: str) -> bytes:
    if not api_key:
        return b""
    return load_or_create_fernet(storage_root).encrypt(api_key.encode("utf-8"))


def decrypt_api_key(storage_root: Path, ciphertext: bytes | None) -> str:
    if not ciphertext:
        return ""
    return load_or_create_fernet(storage_root).decrypt(ciphertext).decode("utf-8")
