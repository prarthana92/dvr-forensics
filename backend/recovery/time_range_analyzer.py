import os
import cv2
import json
from datetime import datetime


def analyze_recovered_time_range(video_path):
    """
    Analyze the successfully decoded portion of a damaged/recovered video.

    This function records:
    - FPS
    - reported frame count
    - successfully decoded frame count
    - first successful frame
    - last successful frame
    - estimated recovered duration
    - estimated recovered time range

    IMPORTANT:
    This does NOT create or invent any missing frames.
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
    reported_frame_count = int(
        video.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    if fps <= 0:
        fps = None


    decoded_frames = 0
    first_frame_index = None
    last_frame_index = None

    first_timestamp_seconds = None
    last_timestamp_seconds = None


    while True:

        success, frame = video.read()

        if not success:
            break


        current_frame_index = decoded_frames

        # Ask OpenCV for the timestamp of the frame just decoded.
        timestamp_ms = video.get(
            cv2.CAP_PROP_POS_MSEC
        )

        if timestamp_ms is not None and timestamp_ms >= 0:
            timestamp_seconds = timestamp_ms / 1000.0
        elif fps:
            timestamp_seconds = current_frame_index / fps
        else:
            timestamp_seconds = None


        if first_frame_index is None:
            first_frame_index = current_frame_index
            first_timestamp_seconds = timestamp_seconds


        last_frame_index = current_frame_index
        last_timestamp_seconds = timestamp_seconds

        decoded_frames += 1


    video.release()


    # Calculate estimated duration from decoded frame count.
    if fps and fps > 0:
        recovered_duration_seconds = decoded_frames / fps
    else:
        recovered_duration_seconds = None


    # Convert seconds into HH:MM:SS.mmm
    def format_timestamp(seconds):

        if seconds is None:
            return None

        hours = int(seconds // 3600)

        minutes = int(
            (seconds % 3600) // 60
        )

        remaining_seconds = seconds % 60

        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{remaining_seconds:06.3f}"
        )


    result = {
        "video_file": video_path,

        "analysis_timestamp": datetime.now().isoformat(),

        "fps": fps,

        "reported_frame_count": reported_frame_count,

        "actually_decoded_frames": decoded_frames,

        "first_decoded_frame": first_frame_index,

        "last_decoded_frame": last_frame_index,

        "first_decoded_timestamp_seconds":
            first_timestamp_seconds,

        "last_decoded_timestamp_seconds":
            last_timestamp_seconds,

        "first_decoded_timestamp":
            format_timestamp(
                first_timestamp_seconds
            ),

        "last_decoded_timestamp":
            format_timestamp(
                last_timestamp_seconds
            ),

        "estimated_recovered_duration_seconds":
            recovered_duration_seconds,

        "estimated_recovered_duration":
            format_timestamp(
                recovered_duration_seconds
            ),

        "recovered_time_range": {
            "start": "00:00:00.000",
            "end": format_timestamp(
                recovered_duration_seconds
            )
        },

        "synthetic_frames_created": 0,

        "synthetic_content_added": False,

        "analysis_note": (
            "Recovered time range is estimated from "
            "successfully decoded frames and FPS. "
            "It does not represent invented or "
            "reconstructed footage."
        )
    }


    return result


def save_time_range_report(video_path, output_json):

    result = analyze_recovered_time_range(
        video_path
    )

    output_directory = os.path.dirname(
        output_json
    )

    if output_directory:
        os.makedirs(
            output_directory,
            exist_ok=True
        )


    with open(
        output_json,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            indent=4
        )


    return result


if __name__ == "__main__":

    VIDEO_PATH = os.path.join(
        "recovery",
        "test_data",
        "damaged_test.mp4"
    )

    OUTPUT_PATH = os.path.join(
        "output",
        "recovery",
        "EVD-TEST-RECOVERY",
        "time_range_analysis.json"
    )


    print("=" * 65)
    print("              TIME RANGE ANALYZER")
    print("=" * 65)

    print()
    print("Video:")
    print(os.path.abspath(VIDEO_PATH))

    print()
    print("Analyzing successfully decoded frames...")

    result = save_time_range_report(
        VIDEO_PATH,
        OUTPUT_PATH
    )

    print()
    print("-" * 65)

    print(
        f"FPS: {result['fps']}"
    )

    print(
        f"Reported frames: "
        f"{result['reported_frame_count']}"
    )

    print(
        f"Actually decoded frames: "
        f"{result['actually_decoded_frames']}"
    )

    print(
        f"First decoded timestamp: "
        f"{result['first_decoded_timestamp']}"
    )

    print(
        f"Last decoded timestamp: "
        f"{result['last_decoded_timestamp']}"
    )

    print(
        f"Estimated recovered duration: "
        f"{result['estimated_recovered_duration']}"
    )

    print()
    print("Recovered time range:")

    print(
        f"{result['recovered_time_range']['start']}"
        f" → "
        f"{result['recovered_time_range']['end']}"
    )

    print()
    print(
        "Synthetic frames created: "
        f"{result['synthetic_frames_created']}"
    )

    print(
        "Synthetic content added: "
        f"{result['synthetic_content_added']}"
    )

    print()
    print("Report:")
    print(os.path.abspath(OUTPUT_PATH))

    print()
    print("=" * 65)