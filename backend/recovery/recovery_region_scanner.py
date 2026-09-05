import os
import cv2
from datetime import datetime


def scan_recovery_regions(video_path):
    """
    Scan a damaged video frame-by-frame and record
    successfully decoded regions.

    No frames are created or modified.
    """

    if not os.path.exists(video_path):
        raise FileNotFoundError(
            f"Video file not found: {video_path}"
        )

    video = cv2.VideoCapture(video_path)

    if not video.isOpened():
        raise RuntimeError(
            f"Could not open video: {video_path}"
        )

    fps = video.get(cv2.CAP_PROP_FPS)

    if fps <= 0:
        fps = None

    reported_frames = int(
        video.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    successful_frames = []

    frame_index = 0

    while True:

        success, frame = video.read()

        if not success:
            break

        timestamp_ms = video.get(
            cv2.CAP_PROP_POS_MSEC
        )

        if timestamp_ms is not None and timestamp_ms >= 0:
            timestamp_seconds = timestamp_ms / 1000.0
        elif fps:
            timestamp_seconds = frame_index / fps
        else:
            timestamp_seconds = None

        successful_frames.append({
            "frame_index": frame_index,
            "timestamp_seconds": timestamp_seconds
        })

        frame_index += 1

    video.release()

    # ---------------------------------------------------------
    # Build recovered region
    # ---------------------------------------------------------

    regions = []

    if successful_frames:

        first = successful_frames[0]
        last = successful_frames[-1]

        if fps:
            end_seconds = (
                last["frame_index"] + 1
            ) / fps
        else:
            end_seconds = last["timestamp_seconds"]

        regions.append({
            "region_id": "REC-REGION-001",

            "status": "RECOVERED",

            "start_frame":
                first["frame_index"],

            "end_frame":
                last["frame_index"],

            "start_timestamp":
                format_timestamp(
                    first["timestamp_seconds"]
                ),

            "end_timestamp":
                format_timestamp(
                    end_seconds
                ),

            "decoded_frames":
                len(successful_frames),

            "synthetic_frames":
                0,

            "synthetic_content":
                False
        })


    # ---------------------------------------------------------
    # Calculate recovery percentage
    # ---------------------------------------------------------

    if reported_frames > 0:

        recovery_percentage = (
            len(successful_frames)
            / reported_frames
        ) * 100

    else:

        recovery_percentage = 0


    # ---------------------------------------------------------
    # Determine status
    # ---------------------------------------------------------

    if len(successful_frames) == 0:

        overall_status = "NOT_RECOVERED"

    elif (
        reported_frames > 0
        and len(successful_frames) >= reported_frames
    ):

        overall_status = "FULLY_RECOVERED"

    else:

        overall_status = "PARTIALLY_RECOVERED"


    result = {

        "video_file": os.path.abspath(video_path),

        "analysis_timestamp":
            datetime.now().isoformat(),

        "fps": fps,

        "reported_frame_count":
            reported_frames,

        "successfully_decoded_frames":
            len(successful_frames),

        "recovery_percentage":
            round(
                recovery_percentage,
                2
            ),

        "overall_status":
            overall_status,

        "recovered_regions":
            regions,

        "synthetic_frames_created":
            0,

        "synthetic_content_added":
            False,

        "forensic_note":
            (
                "Only successfully decoded frames "
                "are classified as recovered. "
                "No synthetic frames were created."
            )
    }

    return result


def format_timestamp(seconds):

    if seconds is None:
        return None

    hours = int(seconds // 3600)

    minutes = int(
        (seconds % 3600) // 60
    )

    remaining = seconds % 60

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{remaining:06.3f}"
    )


if __name__ == "__main__":

    VIDEO_PATH = os.path.join(
        "recovery",
        "test_data",
        "damaged_test.mp4"
    )

    print("=" * 65)
    print("             RECOVERY REGION SCANNER")
    print("=" * 65)

    print()
    print("Video:")
    print(os.path.abspath(VIDEO_PATH))

    print()
    print("Scanning decoded frame regions...")

    result = scan_recovery_regions(
        VIDEO_PATH
    )

    print()
    print("-" * 65)

    print(
        f"Reported frames: "
        f"{result['reported_frame_count']}"
    )

    print(
        f"Successfully decoded: "
        f"{result['successfully_decoded_frames']}"
    )

    print(
        f"Recovery percentage: "
        f"{result['recovery_percentage']}%"
    )

    print(
        f"Overall status: "
        f"{result['overall_status']}"
    )

    print()

    for region in result["recovered_regions"]:

        print(
            f"Region: "
            f"{region['region_id']}"
        )

        print(
            f"Status: "
            f"{region['status']}"
        )

        print(
            f"Time: "
            f"{region['start_timestamp']}"
            f" → "
            f"{region['end_timestamp']}"
        )

        print(
            f"Decoded frames: "
            f"{region['decoded_frames']}"
        )

        print(
            f"Synthetic frames: "
            f"{region['synthetic_frames']}"
        )

    print()

    print(
        "Synthetic content added: "
        f"{result['synthetic_content_added']}"
    )

    print()

    print("=" * 65)