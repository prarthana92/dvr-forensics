import hashlib
import mysql.connector

def compute_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def log_to_database(filename, sha256_hash):
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="PRar7T2*",
        database="dvrdb"
    )
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO hash_log (filename, sha256_hash) VALUES (%s, %s)",
        (filename, sha256_hash)
    )
    conn.commit()
    conn.close()

if __name__ == "__main__":
    test_file = "../data/sample.txt"
    hash_value = compute_sha256(test_file)
    print("SHA-256:", hash_value)
    log_to_database(test_file, hash_value)
    print("Logged to database successfully.")