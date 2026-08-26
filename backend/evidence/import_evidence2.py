from pathlib import Path
from datetime import datetime
import hashlib
import uuid
import json


def calculate_hash(file_path, algorithm):
    hash_function = hashlib.new(algorithm)

    with open(file_path, "rb") as file:
        while chunk := file.read(1024 * 1024):
            hash_function.update(chunk)

    return hash_function.hexdigest()


def identify_evidence_type(file_path):
    extension = Path(file_path).suffix.lower()

    video_extensions = [".mp4", ".avi", ".mkv", ".mov", ".dav", ".264", ".265"]
    image_extensions = [".jpg", ".jpeg", ".png", ".bmp"]
    archive_extensions = [".zip", ".rar", ".7z"]
    disk_extensions = [".dd", ".img", ".e01", ".raw"]

    if extension in video_extensions:
        return "VIDEO"

    elif extension in image_extensions:
        return "IMAGE"

    elif extension in archive_extensions:
        return "ARCHIVE"

    elif extension in disk_extensions:
        return "DISK IMAGE"

    else:
        return "UNKNOWN"


def import_evidence(file_path):
    evidence = Path(file_path)

    if not evidence.exists():
        print("❌ Evidence file not found.")
        return

    # Generate unique Evidence ID
    evidence_id = (
        "EVD-"
        + datetime.now().strftime("%Y%m%d")
        + "-"
        + str(uuid.uuid4())[:8].upper()
    )

    # Basic file information
    file_name = evidence.name
    file_size = evidence.stat().st_size
    file_type = evidence.suffix.lower() if evidence.suffix else "Unknown"

    # Identify evidence category
    evidence_type = identify_evidence_type(file_path)

    # Record acquisition time
    acquisition_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Record file modification time
    modification_time = datetime.fromtimestamp(
        evidence.stat().st_mtime
    ).strftime("%Y-%m-%d %H:%M:%S")

    # Calculate cryptographic hashes
    print("\nCalculating MD5 and SHA-256...")
    md5_hash = calculate_hash(evidence, "md5")
    sha256_hash = calculate_hash(evidence, "sha256")

    # Create evidence record
    evidence_record = {
        "evidence_id": evidence_id,
        "file_name": file_name,
        "file_size_bytes": file_size,
        "file_extension": file_type,
        "evidence_type": evidence_type,
        "acquisition_time": acquisition_time,
        "modification_time": modification_time,
        "md5": md5_hash,
        "sha256": sha256_hash
    }

    # Create folder for evidence records
    records_folder = Path("evidence_records")
    records_folder.mkdir(exist_ok=True)

    # Create JSON file for this evidence
    record_file = records_folder / f"{evidence_id}.json"

    with open(record_file, "w", encoding="utf-8") as file:
        json.dump(evidence_record, file, indent=4)

    # Display forensic intake report
    print("\n" + "=" * 60)
    print("        SMART EVIDENCE INTAKE REPORT")
    print("=" * 60)

    print("Evidence ID       :", evidence_id)
    print("File Name         :", file_name)
    print("File Size         :", file_size, "bytes")
    print("File Type         :", file_type)
    print("Evidence Category :", evidence_type)
    print("Acquisition Time  :", acquisition_time)
    print("Modified Time     :", modification_time)

    print("\nMD5               :", md5_hash)
    print("SHA-256           :", sha256_hash)

    # Preliminary timestamp check
    if modification_time > acquisition_time:
        print("\n⚠️ WARNING: File modification time is after acquisition time.")
    else:
        print("\n✓ Preliminary integrity check completed.")

    print("\n✓ Evidence record saved to:", record_file)

    print("=" * 60)
    print("Evidence successfully registered.")
    print("=" * 60)


file_path = input("Enter the path of the evidence file: ")

import_evidence(file_path)