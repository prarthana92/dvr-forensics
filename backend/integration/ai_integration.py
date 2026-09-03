import os
import json


def load_json(file_path):

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def create_linked_record(
    evidence_record,
    ai_results
):

    linked_record = {
        "evidence_id": evidence_record["evidence_id"],
        "file_name": evidence_record["file_name"],
        "evidence_type": evidence_record["evidence_type"],
        "evidence_sha256": evidence_record["sha256"],
        "ai_analysis": ai_results
    }

    return linked_record


if __name__ == "__main__":

    backend_folder = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    ai_results_path = os.path.join(
        backend_folder,
        "output",
        "ai_results.json"
    )

    print("\nAI ↔ EVIDENCE INTEGRATION")
    print("────────────────────────────")

    print(
        "AI results file:",
        ai_results_path
    )

    try:

        ai_results = load_json(
            ai_results_path
        )

        evidence_records_folder = os.path.join(
            backend_folder,
            "evidence_records"
        )

        evidence_id = input(
            "\nEnter the evidence ID to link: "
        ).strip()

        if not evidence_id:
            raise ValueError(
                "Evidence ID cannot be empty."
            )

        evidence_record_path = os.path.join(
            evidence_records_folder,
            f"{evidence_id}.json"
        )

        evidence_record = load_json(
            evidence_record_path
        )

        linked_record = create_linked_record(
            evidence_record,
            ai_results
        )

        output_folder = os.path.join(
            backend_folder,
            "output"
        )

        os.makedirs(
            output_folder,
            exist_ok=True
        )

        output_path = os.path.join(
            output_folder,
            f"{evidence_id}_analysis.json"
        )

        with open(
            output_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                linked_record,
                file,
                indent=4
            )

        print(
            "\n✓ Evidence record loaded."
        )

        print(
            "✓ AI results loaded."
        )

        print(
            "✓ AI results linked to evidence."
        )

        print(
            "\nEvidence ID:",
            evidence_id
        )

        print(
            "Video:",
            evidence_record["file_name"]
        )

        print(
            "Analysis events:",
            len(ai_results["events"])
        )

        print(
            "\nCombined analysis saved as:"
        )

        print(output_path)

    except Exception as error:

        print(
            "\nError:",
            error
        )