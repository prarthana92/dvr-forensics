import os
import hashlib
import json


def calculate_sha256(file_path):

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        while True:

            data = file.read(1024 * 1024)

            if not data:
                break

            sha256.update(data)

    return sha256.hexdigest()


if __name__ == "__main__":

    candidate_file = "../output/recovered_fragment.mp4"

    report_path = "../output/recovery_candidate.json"

    try:

        if not os.path.exists(candidate_file):

            print("Candidate file not found.")

        else:

            candidate_hash = calculate_sha256(
                candidate_file
            )

            with open(report_path, "r") as file:

                report = json.load(file)

            report["candidate_sha256"] = candidate_hash

            with open(report_path, "w") as file:

                json.dump(
                    report,
                    file,
                    indent=4
                )

            print("\nRECOVERY CANDIDATE HASH")
            print("────────────────────────────")

            print(
                "Candidate:",
                candidate_file
            )

            print(
                "SHA-256:",
                candidate_hash
            )

            print(
                "\nCandidate hash saved successfully!"
            )

            print(
                "Updated:",
                report_path
            )

    except Exception as error:

        print("Error:", error)