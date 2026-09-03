import os
import json
import uuid
from datetime import datetime


def generate_candidate_id():

    random_part = uuid.uuid4().hex[:8].upper()

    date_part = datetime.now().strftime(
        "%Y%m%d"
    )

    return f"REC-{date_part}-{random_part}"


def create_recovery_candidate(
    source_file,
    file_type,
    signature,
    position,
    extracted_file,
    validation_status,
    evidence_id=None
):

    if validation_status == "READABLE":

        recovery_status = "RECOVERED"

    elif validation_status == "INCOMPLETE":

        recovery_status = "PARTIALLY_RECOVERED"

    else:

        recovery_status = "NOT_RECOVERED"

    candidate = {
        "candidate_id": generate_candidate_id(),
        "evidence_id": evidence_id,
        "source_file": source_file,
        "detected_file_type": file_type,
        "signature": signature,
        "byte_position": position,
        "extracted_file": extracted_file,
        "validation_status": validation_status,
        "recovery_status": recovery_status,
        "created_at": datetime.now().isoformat()
    }

    return candidate


if __name__ == "__main__":

    backend_folder = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    scan_path = os.path.join(
        backend_folder,
        "output",
        "fragment_scan.json"
    )

    extracted_file = os.path.join(
        backend_folder,
        "output",
        "recovered_fragment.mp4"
    )

    output_path = os.path.join(
        backend_folder,
        "output",
        "recovery_candidate.json"
    )

    # Test evidence ID
    evidence_id = "EVD-TEST-RECOVERY"

    try:

        if not os.path.exists(scan_path):

            print(
                "Fragment scan report not found."
            )

            print(
                "Run fragment_scanner.py first."
            )

        else:

            with open(
                scan_path,
                "r",
                encoding="utf-8"
            ) as file:

                scan_data = json.load(
                    file
                )

            results = scan_data.get(
                "results",
                []
            )

            if not results:

                print(
                    "No recovery candidates found."
                )

            else:

                first_result = results[0]

                candidate = create_recovery_candidate(
                    scan_data["scanned_file"],
                    first_result["file_type"],
                    first_result["signature"],
                    first_result["position"],
                    extracted_file,
                    "INCOMPLETE",
                    evidence_id
                )

                with open(
                    output_path,
                    "w",
                    encoding="utf-8"
                ) as file:

                    json.dump(
                        candidate,
                        file,
                        indent=4
                    )

                print(
                    "\nRECOVERY CANDIDATE"
                )

                print(
                    "────────────────────────────"
                )

                print(
                    "Candidate ID:",
                    candidate["candidate_id"]
                )

                print(
                    "Evidence ID:",
                    candidate["evidence_id"]
                )

                print(
                    "Type:",
                    candidate["detected_file_type"]
                )

                print(
                    "Byte position:",
                    candidate["byte_position"]
                )

                print(
                    "Validation:",
                    candidate["validation_status"]
                )

                print(
                    "Recovery status:",
                    candidate["recovery_status"]
                )

                print(
                    "\nRecovery candidate saved successfully!"
                )

                print(
                    "Saved as:",
                    output_path
                )

    except Exception as error:

        print(
            "Error:",
            error
        )