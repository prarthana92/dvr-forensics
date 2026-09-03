import cv2
import os
import json


def clean_output_folder(output_folder):

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        return

    for filename in os.listdir(output_folder):

        file_path = os.path.join(
            output_folder,
            filename
        )

        if os.path.isfile(file_path):
            os.remove(file_path)


def extract_frames(
    video_path,
    output_folder,
    interval_seconds=1
):

    if not os.path.exists(video_path):

        raise FileNotFoundError(
            f"Video file not found: {video_path}"
        )

    if interval_seconds <= 0:

        raise ValueError(
            "Interval must be greater than 0 seconds"
        )

    video = cv2.VideoCapture(
        video_path
    )

    if not video.isOpened():

        raise RuntimeError(
            "Could not open the video"
        )

    os.makedirs(
        output_folder,
        exist_ok=True
    )

    fps = video.get(
        cv2.CAP_PROP_FPS
    )

    if fps <= 0:

        video.release()

        raise RuntimeError(
            "Could not determine video frame rate"
        )

    frame_interval = max(
        1,
        int(fps * interval_seconds)
    )

    frame_number = 0
    saved_count = 0

    frame_index = []

    while True:

        success, frame = video.read()

        if not success:
            break

        if frame_number % frame_interval == 0:

            timestamp = (
                frame_number / fps
            )

            filename = os.path.join(
                output_folder,
                f"frame_{saved_count + 1:03d}.jpg"
            )

            cv2.imwrite(
                filename,
                frame
            )

            frame_index.append({
                "frame": os.path.basename(
                    filename
                ),
                "timestamp_seconds": round(
                    timestamp,
                    2
                )
            })

            print(
                f"Saved {filename} "
                f"at {timestamp:.2f} seconds"
            )

            saved_count += 1

        frame_number += 1

    video.release()

    index_path = os.path.join(
        output_folder,
        "frame_index.json"
    )

    with open(
        index_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            frame_index,
            file,
            indent=4
        )

    return saved_count


if __name__ == "__main__":

    video_path = "device/hikvision_test.mp4"
    output_folder = "output/frames"

    clean_output_folder(
        output_folder
    )

    try:

        count = extract_frames(
            video_path,
            output_folder,
            1
        )

        print(
            "\nFrames extracted successfully!"
        )

        print(
            "Total frames saved:",
            count
        )

        print(
            "Frame index created!"
        )

    except Exception as error:

        print(
            "Error:",
            error
        )