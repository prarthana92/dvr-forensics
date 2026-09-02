import os
import shutil
import hashlib
import json
from datetime import datetime


def create_forensic_copy(source_path, destination_path):

    if not os.path.exists(source_path):
        raise FileNotFoundError(
            f"Source evidence not found: {source_path}"
        )

    if os.path.exists(destination_path):
        raise FileExistsError(
            f"Forensic copy already exists: {destination_path}"
        )

    shutil.copy2(source_path, destination_path)

    return destination_path


def calculate_sha256(file_path):

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        while True:

            data = file.read(1024 * 1024)

            if not data:
                break

            sha256.update(data)

    return sha256.hexdigest()


def save_verification_report(
    source_path,
    copy_path,
    original_hash,
    copy_hash,
    report_path
):

    verification_result = (
        original_hash == copy_hash
    )

    verification_time = datetime.now().isoformat()

    if verification_result:
        status = "VERIFIED"
    else:
        status = "FAILED"

    report = {
        "original_file": source_path,
        "forensic_copy": copy_path,
        "original_sha256": original_hash,
        "copy_sha256": copy_hash,
        "hash_match": verification_result,
        "status": status,
        "verified_at": verification_time
    }

    with open(
        report_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=4
        )

    return verification_time


def check_copy_integrity(
    copy_path,
    report_path
):

    if not os.path.exists(copy_path):
        raise FileNotFoundError(
            f"Forensic copy not found: {copy_path}"
        )

    if not os.path.exists(report_path):
        raise FileNotFoundError(
            f"Verification report not found: {report_path}"
        )

    with open(
        report_path,
        "r",
        encoding="utf-8"
    ) as file:

        report = json.load(file)

    recorded_hash = report["copy_sha256"]

    current_hash = calculate_sha256(
        copy_path
    )

    return recorded_hash == current_hash


def process_forensic_copy(
    source_path,
    output_folder,
    evidence_id
):

    os.makedirs(
        output_folder,
        exist_ok=True
    )

    source_path = os.path.abspath(
        source_path
    )

    file_extension = os.path.splitext(
        source_path
    )[1]

    destination_path = os.path.join(
        output_folder,
        f"{evidence_id}_forensic_copy{file_extension}"
    )

    report_path = os.path.join(
        output_folder,
        f"{evidence_id}_verification.json"
    )

    if os.path.exists(destination_path):

        print(
            "\nExisting forensic copy found."
        )

        copied_file = destination_path

    else:

        copied_file = create_forensic_copy(
            source_path,
            destination_path
        )

        print(
            "\n✓ Forensic copy created."
        )

    original_hash = calculate_sha256(
        source_path
    )

    copy_hash = calculate_sha256(
        copied_file
    )

    print("\nSHA-256 VERIFICATION")
    print("────────────────────────────")

    print(
        "Original :",
        original_hash
    )

    print(
        "Copy     :",
        copy_hash
    )

    if original_hash == copy_hash:

        print("\n✓ HASH MATCH")
        print(
            "The forensic copy matches the original."
        )

    else:

        print("\n✗ HASH MISMATCH")
        print(
            "The forensic copy does not match "
            "the original."
        )

    verification_time = save_verification_report(
        source_path,
        copied_file,
        original_hash,
        copy_hash,
        report_path
    )

    integrity_ok = check_copy_integrity(
        copied_file,
        report_path
    )

    print("\nINTEGRITY CHECK")
    print("────────────────────────────")

    if integrity_ok:

        print("✓ INTEGRITY VERIFIED")
        print(
            "The forensic copy has not changed."
        )

    else:

        print("✗ INTEGRITY FAILURE")
        print(
            "The forensic copy has changed."
        )

    if (
        integrity_ok
        and original_hash == copy_hash
    ):

        status = "VERIFIED"

    else:

        status = "FAILED"

    print("\nRECOVERY STATUS")
    print("────────────────────────────")
    print("STATUS:", status)

    return {
        "forensic_copy": copied_file,
        "verification_report": report_path,
        "original_sha256": original_hash,
        "copy_sha256": copy_hash,
        "hash_match": original_hash == copy_hash,
        "integrity_verified": integrity_ok,
        "status": status,
        "verified_at": verification_time
    }


if __name__ == "__main__":

    source_path = "device/hikvision_test.mp4"

    output_folder = "../output"

    evidence_id = "TEST"

    try:

        process_forensic_copy(
            source_path,
            output_folder,
            evidence_id
        )

    except Exception as error:

        print(
            "Error:",
            error
        )