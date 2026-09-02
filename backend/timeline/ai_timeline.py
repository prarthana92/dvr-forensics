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


def create_timeline(linked_record):

    evidence_id = linked_record["evidence_id"]

    file_name = linked_record["file_name"]

    ai_analysis = linked_record["ai_analysis"]

    events = []

    for event in ai_analysis["events"]:

        frame = event["frame"]

        timestamp = event["timestamp_seconds"]

        for detection in event["detections"]:

            timeline_event = {
                "evidence_id": evidence_id,
                "video_file": file_name,
                "frame": frame,
                "timestamp_seconds": timestamp,
                "type": detection["type"],
                "label": detection["label"],
                "detection": detection
            }

            if "confidence" in detection:

                timeline_event["confidence"] = (
                    detection["confidence"]
                )

            if "region_count" in detection:

                timeline_event["region_count"] = (
                    detection["region_count"]
                )

            events.append(timeline_event)

    events.sort(
        key=lambda event: event["timestamp_seconds"]
    )

    return {
        "evidence_id": evidence_id,
        "video_file": file_name,
        "events": events
    }


if __name__ == "__main__":

    backend_folder = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    print("\nAI → TIMELINE PROCESSOR")
    print("────────────────────────────")

    evidence_id = input(
        "Enter the evidence ID: "
    ).strip()

    if not evidence_id:

        print("❌ Evidence ID cannot be empty.")

        raise SystemExit

    input_path = os.path.join(
        backend_folder,
        "output",
        f"{evidence_id}_analysis.json"
    )

    output_path = os.path.join(
        backend_folder,
        "output",
        f"{evidence_id}_timeline.json"
    )

    try:

        linked_record = load_json(
            input_path
        )

        timeline = create_timeline(
            linked_record
        )

        with open(
            output_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                timeline,
                file,
                indent=4
            )

        print(
            "\n✓ AI analysis loaded."
        )

        print(
            "✓ Timeline events created:",
            len(timeline["events"])
        )

        print(
            "✓ Events sorted by timestamp."
        )

        print(
            "\nTimeline saved as:"
        )

        print(output_path)

    except Exception as error:

        print(
            "\nError:",
            error
        )