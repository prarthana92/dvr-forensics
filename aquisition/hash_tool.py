
import hashlib

def compute_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

if __name__ == "__main__":
    test_file = "data/sample.txt"
    print("SHA-256:", compute_sha256(test_file))