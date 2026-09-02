import subprocess
import json
import os


FFPROBE_PATH = r"C:\ffmpeg\ffmpeg-9.0.1-essentials_build\bin\ffprobe.exe"


def extract_metadata(video_path):

    command = [
        FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video_path)
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Could not read video metadata"
        )

    data = json.loads(
        result.stdout
    )

    metadata = {
        "file": os.path.basename(video_path),
        "format": data["format"].get(
            "format_name"
        ),
        "size_bytes": data["format"].get(
            "size"
        ),
        "duration_seconds": data["format"].get(
            "duration"
        )
    }

    for stream in data["streams"]:

        if stream["codec_type"] == "video":

            metadata["width"] = stream.get(
                "width"
            )

            metadata["height"] = stream.get(
                "height"
            )

            metadata["video_codec"] = stream.get(
                "codec_name"
            )

            metadata["frame_rate"] = stream.get(
                "r_frame_rate"
            )

            break

    return metadata


if __name__ == "__main__":

    video_path = "device/hikvision_test.mp4"

    try:

        metadata = extract_metadata(
            video_path
        )

        print("\nVIDEO METADATA")
        print("=" * 50)

        for key, value in metadata.items():

            print(
                f"{key:<18}: {value}"
            )

    except Exception as error:

        print(
            "Error:",
            error
        )