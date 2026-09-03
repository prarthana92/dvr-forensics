import os
import json
import subprocess
from datetime import datetime


# ============================================================
# TRACE X
# FFPROBE TECHNICAL ANALYSIS
# ============================================================


def find_ffprobe():
    """
    Finds FFprobe from the normal Windows installation path
    used in this project.
    """

    possible_paths = [
        r"C:\ffmpeg\ffmpeg-9.0.1-essentials_build\bin\ffprobe.exe",
        r"C:\ffmpeg\bin\ffprobe.exe",
        "ffprobe"
    ]

    for path in possible_paths:

        if path == "ffprobe":
            return path

        if os.path.exists(path):
            return path

    return None


def run_ffprobe(file_path):
    """
    Runs FFprobe and returns standardized JSON information.
    """

    ffprobe = find_ffprobe()

    if ffprobe is None:
        raise FileNotFoundError(
            "FFprobe executable was not found."
        )

    command = [
        ffprobe,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        file_path
    ]

    process = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if process.returncode != 0:
        raise RuntimeError(
            process.stderr.strip()
            or "FFprobe failed to analyze the file."
        )

    try:
        return json.loads(process.stdout)

    except json.JSONDecodeError:
        raise RuntimeError(
            "FFprobe returned invalid JSON."
        )


def analyze_ffprobe(file_path):
    """
    Performs technical FFprobe analysis.

    IMPORTANT:
    This function collects technical characteristics.
    It does NOT claim that codec/resolution/etc. proves
    a particular CCTV vendor.
    """

    if not os.path.exists(file_path):

        raise FileNotFoundError(
            f"Evidence file not found: {file_path}"
        )

    data = run_ffprobe(file_path)

    format_data = data.get(
        "format",
        {}
    )

    streams = data.get(
        "streams",
        []
    )

    video_stream = None

    for stream in streams:

        if stream.get("codec_type") == "video":

            video_stream = stream
            break

    result = {

        "available": True,

        "analyzed_at":
            datetime.now().isoformat(),

        "format": {

            "format_name":
                format_data.get(
                    "format_name"
                ),

            "duration":
                format_data.get(
                    "duration"
                ),

            "bit_rate":
                format_data.get(
                    "bit_rate"
                ),

            "size":
                format_data.get(
                    "size"
                )
        },

        "video": {

            "codec_name":
                video_stream.get(
                    "codec_name"
                )
                if video_stream
                else None,

            "codec_long_name":
                video_stream.get(
                    "codec_long_name"
                )
                if video_stream
                else None,

            "codec_tag_string":
                video_stream.get(
                    "codec_tag_string"
                )
                if video_stream
                else None,

            "width":
                video_stream.get(
                    "width"
                )
                if video_stream
                else None,

            "height":
                video_stream.get(
                    "height"
                )
                if video_stream
                else None,

            "pix_fmt":
                video_stream.get(
                    "pix_fmt"
                )
                if video_stream
                else None,

            "r_frame_rate":
                video_stream.get(
                    "r_frame_rate"
                )
                if video_stream
                else None,

            "avg_frame_rate":
                video_stream.get(
                    "avg_frame_rate"
                )
                if video_stream
                else None
        },

        "raw_stream_count":
            len(streams),

        "vendor_identified":
            False,

        "forensic_note":
            (
                "FFprobe characteristics are standardized "
                "technical evidence. Codec, resolution, "
                "frame rate, and container format alone "
                "must not be treated as vendor-specific proof."
            )
    }

    return result


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print(
        "       TRACE X FFPROBE ANALYSIS TEST"
    )
    print("=" * 60)

    print()

    file_path = input(
        "Enter evidence/video path: "
    ).strip().strip('"')

    try:

        result = analyze_ffprobe(
            file_path
        )

        print()
        print("FORMAT")
        print("────────────────────────────")

        print(
            result["format"]["format_name"]
        )

        print()
        print("DURATION")
        print("────────────────────────────")

        print(
            result["format"]["duration"]
        )

        print()
        print("BIT RATE")
        print("────────────────────────────")

        print(
            result["format"]["bit_rate"]
        )

        print()
        print("VIDEO")
        print("────────────────────────────")

        print(
            "Codec:",
            result["video"]["codec_name"]
        )

        print(
            "Codec tag:",
            result["video"]["codec_tag_string"]
        )

        print(
            "Resolution:",
            f'{result["video"]["width"]}'
            f'x'
            f'{result["video"]["height"]}'
        )

        print(
            "Pixel format:",
            result["video"]["pix_fmt"]
        )

        print(
            "Frame rate:",
            result["video"]["r_frame_rate"]
        )

        print()
        print(
            "FFprobe available: True"
        )

        print()
        print("=" * 60)
        print("              TEST COMPLETE")
        print("=" * 60)

    except Exception as error:

        print()
        print(
            "FFprobe Error:",
            error
        )