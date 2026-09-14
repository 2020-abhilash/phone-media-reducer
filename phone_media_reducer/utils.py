import hashlib
from pathlib import Path
from typing import Union


def compute_file_hash(file_path: Union[str, Path], chunk_size: int = 65536) -> str:
    """Computes the SHA-256 hash of a file using chunked streaming."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()
