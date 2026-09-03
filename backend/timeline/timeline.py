import json
from pathlib import Path


# ============================================================
# BACKEND FOLDER
# ============================================================

BACKEND_FOLDER = Path(__file__).resolve().parent.parent

OUTPUT_FOLDER = BACKEND_FOLDER / "output"

TIMELINE_FOLDER = OUTPUT_FOLDER / "timeline"

TIMELINE_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# LOAD FRAME INDEX
# ============================================================

def load_frame_index(index_path):

    index_path = Path(index_path)

    if not index_path.exists():

        raise FileNotFoundError(
            f"Frame index not found: {index_path}"
        )

    with open(
        index_path,
        "r",
        encoding="utf-8"
    ) as file:

        frame_index = json.load(file)

    if not isinstance(frame_index, list):

        raise ValueError(
            "Frame index must contain a list of frames."
        )

    return frame_index


# ============================================================
# CREATE FRAME TIMELINE
# ============================================================

def create_timeline(frame_index):

    timeline = []

    for frame in frame_index:

        event = {

            "timestamp_seconds":
                frame["timestamp_seconds"],

            "event":
                "Frame extracted",

            "frame":
                frame["frame"]

        }

        timeline.append(event)


    timeline.sort(
        key=lambda event:
        event["timestamp_seconds"]
    )


    return timeline


# ============================================================
# SAVE TIMELINE
# ============================================================

def save_timeline(
    timeline,
    output_path
):

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
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


# ============================================================
# PROCESS ONE EVIDENCE ITEM
# ============================================================

def generate_timeline(evidence_id):

    # --------------------------------------------------------
    # Evidence-specific frame index
    # --------------------------------------------------------

    frame_index_path = (
        OUTPUT_FOLDER
        / "frames"
        / evidence_id
        / "frame_index.json"
    )


    print(
        "\nLoading frame index..."
    )

    print(
        "Frame index:",
        frame_index_path
    )


    # --------------------------------------------------------
    # Load frames
    # --------------------------------------------------------

    frame_index = load_frame_index(
        frame_index_path
    )


    print(
        "Frames found:",
        len(frame_index)
    )


    # --------------------------------------------------------
    # Create timeline
    # --------------------------------------------------------

    print(
        "\nCreating forensic timeline..."
    )

    timeline = create_timeline(
        frame_index
    )


    # --------------------------------------------------------
    # Evidence-specific timeline file
    # --------------------------------------------------------

    timeline_path = (
        TIMELINE_FOLDER
        / f"{evidence_id}_timeline.json"
    )


    # --------------------------------------------------------
    # Save timeline
    # --------------------------------------------------------

    save_timeline(
        timeline,
        timeline_path
    )


    # --------------------------------------------------------
    # Display timeline
    # --------------------------------------------------------

    print(
        "\n" + "=" * 70
    )

    print(
        "                 FORENSIC TIMELINE"
    )

    print(
        "=" * 70
    )

    print(
        "\nEvidence ID:",
        evidence_id
    )

    print(
        "\nTimeline Events:"
    )

    print(
        "-" * 70
    )


    for number, event in enumerate(
        timeline,
        start=1
    ):

        print(
            f"\nEvent {number}"
        )

        print(
            "Timestamp :",
            f"{event['timestamp_seconds']:.2f}s"
        )

        print(
            "Event     :",
            event["event"]
        )

        print(
            "Frame     :",
            event["frame"]
        )


    print(
        "\n" + "=" * 70
    )

    print(
        "✓ Timeline generated successfully."
    )

    print(
        "Saved as:",
        timeline_path
    )

    print(
        "=" * 70
    )


    return timeline_path


# ============================================================
# PROGRAM START
# ============================================================

if __name__ == "__main__":

    print(
        "\n" + "=" * 70
    )

    print(
        "             FORENSIC TIMELINE GENERATOR"
    )

    print(
        "=" * 70
    )


    evidence_id = input(
        "\nEnter evidence ID: "
    ).strip()


    if not evidence_id:

        print(
            "\nEvidence ID cannot be empty."
        )

    else:

        try:

            generate_timeline(
                evidence_id
            )

        except Exception as error:

            print(
                "\nTimeline generation failed:"
            )

            print(
                error
            )