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


def create_summary(timeline):

    summary_events = []

    for event in timeline["events"]:

        summary_event = {
            "timestamp_seconds": event[
                "timestamp_seconds"
            ],
            "frame": event["frame"],
            "type": event["type"],
            "label": event["label"]
        }

        if "confidence" in event:

            summary_event["confidence"] = (
                event["confidence"]
            )

        if "region_count" in event:

            summary_event["region_count"] = (
                event["region_count"]
            )

        summary_events.append(
            summary_event
        )

    return {
        "evidence_id": timeline["evidence_id"],
        "video_file": timeline["video_file"],
        "total_events": len(summary_events),
        "events": summary_events
    }


if __name__ == "__main__":

    backend_folder = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    evidence_id = input(
        "Enter the evidence ID: "
    ).strip()

    if not evidence_id:

        print(
            "❌ Evidence ID cannot be empty."
        )

        raise SystemExit

    input_path = os.path.join(
        backend_folder,
        "output",
        f"{evidence_id}_timeline.json"
    )

    output_path = os.path.join(
        backend_folder,
        "output",
        f"{evidence_id}_timeline_summary.json"
    )

    try:

        timeline = load_json(
            input_path
        )

        summary = create_summary(
            timeline
        )

        with open(
            output_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                summary,
                file,
                indent=4
            )

        print(
            "\nTIMELINE SUMMARY"
        )

        print(
            "────────────────────────────"
        )

        print(
            "Evidence ID:",
            summary["evidence_id"]
        )

        print(
            "Video:",
            summary["video_file"]
        )

        print(
            "Total events:",
            summary["total_events"]
        )

        print(
            "✓ Timeline summary created."
        )

        print(
            "\nSaved as:"
        )

        print(output_path)

    except Exception as error:

        print(
            "\nError:",
            error
        )