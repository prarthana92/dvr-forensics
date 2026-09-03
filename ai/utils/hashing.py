
import hashlib

def compute_sha256(file_path: str) -> str:
    """Computes the SHA-256 hash of a file, reading it in chunks so large
    video files don't get loaded fully into memory."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()