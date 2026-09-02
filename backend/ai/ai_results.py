import os
import json


VALID_TYPES = {
    "motion",
    "object",
    "face",
    "anomaly"
}


def validate_ai_results(data):

    if not isinstance(data, dict):
        return False, "AI results must be a JSON object."

    if "events" not in data:
        return False, "Missing 'events' field."

    if not isinstance(data["events"], list):
        return False, "'events' must be a list."

    for index, event in enumerate(data["events"]):

        if not isinstance(event, dict):
            return False, f"Event {index} is not an object."

        if "frame" not in event:
            return False, f"Event {index} is missing 'frame'."

        if "timestamp_seconds" not in event:
            return False, (
                f"Event {index} is missing "
                "'timestamp_seconds'."
            )

        if "detections" not in event:
            return False, (
                f"Event {index} is missing "
                "'detections'."
            )

        if not isinstance(event["detections"], list):
            return False, (
                f"Event {index} 'detections' "
                "must be a list."
            )

        for detection_index, detection in enumerate(
            event["detections"]
        ):

            if not isinstance(detection, dict):
                return False, (
                    f"Detection {detection_index} "
                    f"in event {index} is invalid."
                )

            if "type" not in detection:
                return False, (
                    f"Detection {detection_index} "
                    f"in event {index} is missing 'type'."
                )

            if detection["type"] not in VALID_TYPES:
                return False, (
                    f"Invalid detection type: "
                    f"{detection['type']}"
                )

            if "label" not in detection:
                return False, (
                    f"Detection {detection_index} "
                    f"in event {index} is missing 'label'."
                )

    return True, "AI results are valid."


def load_ai_results(file_path):

    if not os.path.exists(file_path):

        raise FileNotFoundError(
            f"AI results file not found: {file_path}"
        )

    with open(file_path, "r") as file:

        data = json.load(file)

    valid, message = validate_ai_results(data)

    if not valid:

        raise ValueError(message)

    return data


def save_ai_results(data, output_path):

    valid, message = validate_ai_results(data)

    if not valid:

        raise ValueError(message)

    output_folder = os.path.dirname(output_path)

    if output_folder:

        os.makedirs(
            output_folder,
            exist_ok=True
        )

    with open(output_path, "w") as file:

        json.dump(
            data,
            file,
            indent=4
        )


def attach_evidence_information(
    data,
    evidence_id,
    video_file
):

    data["evidence_id"] = evidence_id

    data["video_file"] = video_file

    return data


if __name__ == "__main__":

    backend_folder = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    input_path = os.path.join(
        backend_folder,
        "ai_input",
        "ai_results.json"
    )

    output_path = os.path.join(
        backend_folder,
        "output",
        "ai_results.json"
    )

    try:

        results = load_ai_results(
            input_path
        )

        evidence_id = input(
            "Enter evidence ID: "
        ).strip()

        video_file = input(
            "Enter video file name: "
        ).strip()

        if not evidence_id:

            raise ValueError(
                "Evidence ID cannot be empty."
            )

        if not video_file:

            raise ValueError(
                "Video file name cannot be empty."
            )

        results = attach_evidence_information(
            results,
            evidence_id,
            video_file
        )

        save_ai_results(
            results,
            output_path
        )

        print("\nAI RESULTS IMPORT")
        print("────────────────────────────")

        print(
            "Evidence ID:",
            results["evidence_id"]
        )

        print(
            "Video file:",
            results["video_file"]
        )

        print(
            "Events imported:",
            len(results["events"])
        )

        print(
            "✓ AI results structure is valid."
        )

        print(
            "✓ Evidence information attached."
        )

        print(
            "AI results saved successfully!"
        )

        print(
            "Saved as:",
            output_path
        )

    except Exception as error:

        print("Error:", error)