
import json
from pathlib import Path


# ============================================================
# BACKEND FOLDER
# ============================================================

BACKEND_FOLDER = Path(__file__).resolve().parent.parent


# ============================================================
# AI RESULTS FOLDER
# ============================================================

AI_RESULTS_FILE = (
    BACKEND_FOLDER
    / "output"
    / "ai_results.json"
)


# ============================================================
# OUTPUT FOLDER
# ============================================================

OUTPUT_FOLDER = (
    BACKEND_FOLDER
    / "output"
    / "timeline"
)

OUTPUT_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# LOAD AI RESULTS
# ============================================================

def load_ai_results():

    if not AI_RESULTS_FILE.exists():

        raise FileNotFoundError(
            f"AI results file not found: {AI_RESULTS_FILE}"
        )

    with open(
        AI_RESULTS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    if not isinstance(data, dict):

        raise ValueError(
            "AI results must be a JSON object."
        )

    if "events" not in data:

        raise ValueError(
            "AI results do not contain 'events'."
        )

    if not isinstance(
        data["events"],
        list
    ):

        raise ValueError(
            "'events' must be a list."
        )

    return data


# ============================================================
# CALCULATE DETECTION STATISTICS
# ============================================================

def calculate_statistics(ai_results):

    statistics = {

        "motion_events": 0,

        "object_events": 0,

        "face_events": 0,

        "anomaly_events": 0

    }


    # --------------------------------------------------------
    # GO THROUGH EACH AI EVENT
    # --------------------------------------------------------

    for event in ai_results["events"]:

        detections = event.get(
            "detections",
            []
        )

        if not isinstance(
            detections,
            list
        ):

            continue


        # ----------------------------------------------------
        # COUNT EACH DETECTION TYPE
        # ----------------------------------------------------

        for detection in detections:

            if not isinstance(
                detection,
                dict
            ):

                continue

            detection_type = detection.get(
                "type"
            )

            if detection_type == "motion":

                statistics[
                    "motion_events"
                ] += 1

            elif detection_type == "object":

                statistics[
                    "object_events"
                ] += 1

            elif detection_type == "face":

                statistics[
                    "face_events"
                ] += 1

            elif detection_type == "anomaly":

                statistics[
                    "anomaly_events"
                ] += 1


    # --------------------------------------------------------
    # TOTAL DETECTIONS
    # --------------------------------------------------------

    total_events = (

        statistics["motion_events"]

        + statistics["object_events"]

        + statistics["face_events"]

        + statistics["anomaly_events"]

    )


    # --------------------------------------------------------
    # FINAL STATISTICS
    # --------------------------------------------------------

    return {

        "evidence_id":
            ai_results.get(
                "evidence_id",
                "UNKNOWN"
            ),

        "video_file":
            ai_results.get(
                "video_file",
                "UNKNOWN"
            ),

        "total_events":
            total_events,

        "motion_events":
            statistics[
                "motion_events"
            ],

        "object_events":
            statistics[
                "object_events"
            ],

        "face_events":
            statistics[
                "face_events"
            ],

        "anomaly_events":
            statistics[
                "anomaly_events"
            ]

    }


# ============================================================
# SAVE STATISTICS
# ============================================================

def save_statistics(
    statistics,
    evidence_id
):

    output_file = (

        OUTPUT_FOLDER

        / f"{evidence_id}_detection_statistics.json"

    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            statistics,
            file,
            indent=4
        )

    return output_file


# ============================================================
# DISPLAY STATISTICS
# ============================================================

def display_statistics(
    statistics
):

    print("\n" + "=" * 70)

    print(
        "             DETECTION STATISTICS"
    )

    print("=" * 70)

    print(
        "\nEvidence ID:",
        statistics["evidence_id"]
    )

    print(
        "Video File:",
        statistics["video_file"]
    )

    print(
        "\nDetection Summary:"
    )

    print("-" * 70)

    print(
        "Total Events   :",
        statistics["total_events"]
    )

    print(
        "Motion Events  :",
        statistics["motion_events"]
    )

    print(
        "Object Events  :",
        statistics["object_events"]
    )

    print(
        "Face Events    :",
        statistics["face_events"]
    )

    print(
        "Anomaly Events :",
        statistics["anomaly_events"]
    )

    print("=" * 70)


# ============================================================
# MAIN PROGRAM
# ============================================================

if __name__ == "__main__":

    print("\n" + "=" * 70)

    print(
        "             DETECTION STATISTICS GENERATOR"
    )

    print("=" * 70)


    try:

        # ----------------------------------------------------
        # LOAD AI RESULTS
        # ----------------------------------------------------

        print(
            "\nLoading AI results..."
        )

        ai_results = load_ai_results()

        evidence_id = ai_results.get(
            "evidence_id",
            "UNKNOWN"
        )

        print(
            "Evidence ID:",
            evidence_id
        )

        print(
            "AI Events:",
            len(
                ai_results["events"]
            )
        )


        # ----------------------------------------------------
        # CALCULATE STATISTICS
        # ----------------------------------------------------

        print(
            "\nCalculating detection statistics..."
        )

        statistics = calculate_statistics(
            ai_results
        )


        # ----------------------------------------------------
        # DISPLAY
        # ----------------------------------------------------

        display_statistics(
            statistics
        )


        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        output_file = save_statistics(

            statistics,

            evidence_id

        )

        print(
            "\n✓ Detection statistics generated."
        )

        print(
            "Saved as:",
            output_file
        )

        print(
            "=" * 70
        )


    except Exception as error:

        print(
            "\nERROR:"
        )

        print(
            error
        )

