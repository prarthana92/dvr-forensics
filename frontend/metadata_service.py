import subprocess
import json
import os


# Reads from an environment variable first (works on any machine/server);
# falls back to just "ffprobe" (works if it's on the system PATH, e.g. after
# `apt install ffmpeg` on a Linux host); her original hardcoded Windows path
# is now only the last-resort fallback for local dev on her machine.
FFPROBE_PATH = os.environ.get("FFPROBE_PATH", "ffprobe")


def extract_metadata(video_path):
    command = [
        FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video_path)
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError(
            f"ffprobe not found at '{FFPROBE_PATH}'. Set the FFPROBE_PATH "
            "environment variable, or install ffmpeg so 'ffprobe' is on your PATH."
        )

    if result.returncode != 0:
        raise RuntimeError(f"Could not read video metadata: {result.stderr.strip()}")

    data = json.loads(result.stdout)

    metadata = {
        "file": os.path.basename(video_path),
        "format": data["format"].get("format_name"),
        "size_bytes": data["format"].get("size"),
        "duration_seconds": data["format"].get("duration"),
    }

    for stream in data["streams"]:
        if stream["codec_type"] == "video":
            metadata["width"] = stream.get("width")
            metadata["height"] = stream.get("height")
            metadata["video_codec"] = stream.get("codec_name")
            metadata["frame_rate"] = stream.get("r_frame_rate")
            break

    return metadata