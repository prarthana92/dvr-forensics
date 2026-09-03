from pathlib import Path
import json


def load_ai_results(ai_results_path):

    ai_file = Path(ai_results_path)

    if not ai_file.exists():

        raise FileNotFoundError(
            f"AI results not found: {ai_file}"
        )

    with open(
        ai_file,
        "r",
        encoding="utf-8"
    ) as file:

        ai_results = json.load(file)

    if not isinstance(ai_results, dict):

        raise ValueError(
            "AI results must be a JSON object."
        )

    if "events" not in ai_results:

        raise ValueError(
            "AI results do not contain 'events'."
        )

    if not isinstance(
        ai_results["events"],
        list
    ):

        raise ValueError(
            "'events' must be a list."
        )

    return ai_results


def connect_ai_to_evidence(
    ai_results_path,
    evidence_id,
    forensic_copy_path,
    output_path
):

    ai_results = load_ai_results(
        ai_results_path
    )

    connected_results = {

        "evidence_id": evidence_id,

        "video_file": Path(
            forensic_copy_path
        ).name,

        "events": ai_results[
            "events"
        ]
    }

    output_file = Path(
        output_path
    )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            connected_results,
            file,
            indent=4
        )

    return connected_results


if __name__ == "__main__":

    ai_results_path = (
        "output/ai_results.json"
    )

    evidence_id = input(
        "Enter Evidence ID: "
    ).strip()

    forensic_copy_path = input(
        "Enter forensic copy path: "
    ).strip()

    output_path = (
        "output/ai_evidence_results.json"
    )

    try:

        result = connect_ai_to_evidence(
            ai_results_path,
            evidence_id,
            forensic_copy_path,
            output_path
        )

        print(
            "\n✓ AI results connected "
            "to evidence successfully."
        )

        print(
            "Evidence ID:",
            result["evidence_id"]
        )

        print(
            "Video:",
            result["video_file"]
        )

        print(
            "Events:",
            len(result["events"])
        )

        print(
            "Saved to:",
            output_path
        )

    except Exception as error:

        print(
            "\n❌ AI integration failed:"
        )

        print(error)