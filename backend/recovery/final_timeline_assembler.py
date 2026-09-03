import json
import subprocess
from pathlib import Path


# ============================================================
# TRACEX FINAL FORENSIC TIMELINE VIDEO ASSEMBLER
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_DIR = (
    BASE_DIR
    / "output"
    / "recovery"
    / "multi_region_damaged"
)

RECONSTRUCTED_DIR = (
    OUTPUT_DIR
    / "reconstructed_regions"
)

MANIFEST_FILE = (
    RECONSTRUCTED_DIR
    / "region_reconstruction_manifest.json"
)

FINAL_VIDEO = (
    OUTPUT_DIR
    / "FINAL_TIMELINE_VIDEO.mp4"
)

FINAL_REPORT = (
    OUTPUT_DIR
    / "FINAL_TIMELINE_VIDEO_REPORT.json"
)

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


# ============================================================
# COMMAND RUNNER
# ============================================================

def run_command(command):

    print()
    print("COMMAND:")
    print(" ".join(str(x) for x in command))

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:

        print()
        print("COMMAND FAILED")
        print(result.stderr)

        raise RuntimeError(
            "FFmpeg/FFprobe command failed."
        )

    return result


# ============================================================
# TIME FORMAT
# ============================================================

def format_time(seconds):

    milliseconds = int(
        round((seconds % 1) * 1000)
    )

    total_seconds = int(seconds)

    hours = total_seconds // 3600

    minutes = (
        total_seconds % 3600
    ) // 60

    secs = total_seconds % 60

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{secs:02d}."
        f"{milliseconds:03d}"
    )


# ============================================================
# GET VIDEO INFORMATION
# ============================================================

def get_video_info(video_file):

    command = [
        FFPROBE,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate",
        "-of",
        "json",
        str(video_file),
    ]

    result = run_command(command)

    data = json.loads(result.stdout)

    if not data.get("streams"):
        raise RuntimeError(
            f"No video stream found in:\n{video_file}"
        )

    stream = data["streams"][0]

    width = int(stream["width"])
    height = int(stream["height"])

    fps_text = stream["r_frame_rate"]

    if "/" in fps_text:

        numerator, denominator = (
            fps_text.split("/")
        )

        fps = (
            float(numerator)
            / float(denominator)
        )

    else:
        fps = float(fps_text)

    return width, height, fps


# ============================================================
# CREATE MISSING REGION
# ============================================================

def create_missing_segment(
    output_file,
    duration,
    width,
    height,
    fps,
    region_number,
    start_time,
    end_time,
):

    duration = max(
        duration,
        0.001,
    )

    text = (
        f"MISSING - REGION {region_number:03d}"
    )

    drawtext = (
        "drawtext="
        "fontcolor=white:"
        "fontsize=42:"
        f"text='{text}':"
        "x=(w-text_w)/2:"
        "y=(h-text_h)/2"
    )

    command = [
        FFMPEG,
        "-y",

        "-f",
        "lavfi",

        "-i",
        (
            f"color=c=black:"
            f"s={width}x{height}:"
            f"r={fps}"
        ),

        "-vf",
        drawtext,

        "-t",
        f"{duration:.6f}",

        "-an",

        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-pix_fmt",
        "yuv420p",

        str(output_file),
    ]

    print()
    print(
        f"Creating missing placeholder:"
    )

    print(
        f"Timeline: "
        f"{format_time(start_time)} → "
        f"{format_time(end_time)}"
    )

    run_command(command)


# ============================================================
# RESOLVE RECOVERED FILE
# ============================================================

def resolve_recovered_file(
    output_file
):

    if not output_file:
        return None

    path = Path(output_file)

    # --------------------------------------------------------
    # Manifest paths are relative to backend
    # --------------------------------------------------------

    if not path.is_absolute():

        path = BASE_DIR / path

    # --------------------------------------------------------
    # Fallback: filename inside reconstructed_regions
    # --------------------------------------------------------

    if not path.exists():

        fallback = (
            RECONSTRUCTED_DIR
            / Path(output_file).name
        )

        if fallback.exists():
            path = fallback

    if path.exists():
        return path

    return None


# ============================================================
# VALIDATE FINAL VIDEO
# ============================================================

def validate_final_video(video_file):

    command = [
        FFPROBE,
        "-v",
        "error",

        "-show_entries",
        "format=duration,size",

        "-show_entries",
        "stream=codec_name,width,height,nb_frames",

        "-of",
        "json",

        str(video_file),
    ]

    result = run_command(command)

    return json.loads(result.stdout)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "       TRACEX FINAL FORENSIC TIMELINE VIDEO"
    )
    print("=" * 70)

    print()
    print("Manifest:")
    print(MANIFEST_FILE)

    # --------------------------------------------------------
    # Check manifest
    # --------------------------------------------------------

    if not MANIFEST_FILE.exists():

        raise FileNotFoundError(
            f"Manifest not found:\n"
            f"{MANIFEST_FILE}"
        )

    with open(
        MANIFEST_FILE,
        "r",
        encoding="utf-8",
    ) as f:

        manifest = json.load(f)

    regions = manifest.get(
        "regions",
        []
    )

    if not regions:

        raise RuntimeError(
            "No regions found in manifest."
        )

    print()
    print(
        f"Total timeline regions: "
        f"{len(regions)}"
    )

    # --------------------------------------------------------
    # Correct fields from YOUR manifest
    # --------------------------------------------------------

    recovered_regions = [
        region
        for region in regions
        if str(
            region.get(
                "scanner_status",
                ""
            )
        ).upper() == "RECOVERED"
    ]

    missing_regions = [
        region
        for region in regions
        if str(
            region.get(
                "scanner_status",
                ""
            )
        ).upper() != "RECOVERED"
    ]

    print(
        f"Recovered regions: "
        f"{len(recovered_regions)}"
    )

    print(
        f"Missing regions: "
        f"{len(missing_regions)}"
    )

    # --------------------------------------------------------
    # Find first recovered video
    # --------------------------------------------------------

    first_video = None

    for region in recovered_regions:

        candidate = resolve_recovered_file(
            region.get("output_file")
        )

        if candidate is not None:

            first_video = candidate
            break

    if first_video is None:

        raise RuntimeError(
            "No reconstructed recovered region "
            "video was found."
        )

    # --------------------------------------------------------
    # Video properties
    # --------------------------------------------------------

    width, height, fps = get_video_info(
        first_video
    )

    print()
    print("VIDEO FORMAT")
    print(
        "────────────────────────────────────────────────────────"
    )

    print(
        f"Resolution: "
        f"{width} x {height}"
    )

    print(
        f"FPS: {fps:.6f}"
    )

    # --------------------------------------------------------
    # Temporary directory
    # --------------------------------------------------------

    temp_dir = (
        OUTPUT_DIR
        / "final_timeline_temp"
    )

    temp_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    concat_file = (
        temp_dir
        / "timeline_concat.txt"
    )

    segment_files = []

    # --------------------------------------------------------
    # Build timeline
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("BUILDING COMPLETE TIMELINE")
    print("=" * 70)

    for index, region in enumerate(
        regions,
        start=1,
    ):

        region_number = int(
            region.get(
                "region_number",
                index,
            )
        )

        status = str(
            region.get(
                "scanner_status",
                "UNKNOWN",
            )
        ).upper()

        start_time = float(
            region.get(
                "original_time_start_seconds",
                0,
            )
        )

        end_time = float(
            region.get(
                "original_time_end_seconds",
                start_time,
            )
        )

        duration = max(
            end_time - start_time,
            0,
        )

        print()
        print(
            f"REGION-{region_number:03d}"
        )

        print(
            f"Original position: "
            f"{format_time(start_time)} → "
            f"{format_time(end_time)}"
        )

        print(
            f"Duration: "
            f"{duration:.6f} seconds"
        )

        print(
            f"Status: {status}"
        )

        # ----------------------------------------------------
        # RECOVERED
        # ----------------------------------------------------

        if status == "RECOVERED":

            recovered_file = (
                resolve_recovered_file(
                    region.get(
                        "output_file"
                    )
                )
            )

            if recovered_file is None:

                raise RuntimeError(
                    f"Recovered file missing "
                    f"for REGION-{region_number:03d}"
                )

            print(
                f"Using recovered evidence: "
                f"{recovered_file.name}"
            )

            segment_files.append(
                recovered_file
            )

        # ----------------------------------------------------
        # MISSING
        # ----------------------------------------------------

        else:

            missing_file = (
                temp_dir
                / (
                    f"REGION-"
                    f"{region_number:03d}"
                    f"_MISSING.mp4"
                )
            )

            create_missing_segment(
                output_file=missing_file,
                duration=duration,
                width=width,
                height=height,
                fps=fps,
                region_number=region_number,
                start_time=start_time,
                end_time=end_time,
            )

            segment_files.append(
                missing_file
            )

    # --------------------------------------------------------
    # Create concat file
    # --------------------------------------------------------

    with open(
        concat_file,
        "w",
        encoding="utf-8",
    ) as f:

        for segment in segment_files:

            path = str(
                segment.resolve()
            )

            path = path.replace(
                "\\",
                "/",
            )

            path = path.replace(
                "'",
                "'\\''",
            )

            f.write(
                f"file '{path}'\n"
            )

    print()
    print(
        "Timeline segments created: "
        f"{len(segment_files)}"
    )

    # --------------------------------------------------------
    # Assemble final video
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("ASSEMBLING FINAL TIMELINE VIDEO")
    print("=" * 70)

    command = [

        FFMPEG,
        "-y",

        "-f",
        "concat",

        "-safe",
        "0",

        "-i",
        str(concat_file),

        "-an",

        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-pix_fmt",
        "yuv420p",

        str(FINAL_VIDEO),
    ]

    run_command(command)

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("VALIDATING FINAL TIMELINE VIDEO")
    print("=" * 70)

    validation = validate_final_video(
        FINAL_VIDEO
    )

    format_info = validation.get(
        "format",
        {}
    )

    final_duration = float(
        format_info.get(
            "duration",
            0,
        )
    )

    final_size = int(
        format_info.get(
            "size",
            0,
        )
    )

    print()
    print("FINAL VIDEO")
    print(
        "────────────────────────────────────────────────────────"
    )

    print(
        f"File: {FINAL_VIDEO}"
    )

    print(
        f"Size: {final_size:,} bytes"
    )

    print(
        f"Duration: "
        f"{final_duration:.6f} seconds"
    )

    # --------------------------------------------------------
    # Expected timeline duration
    # --------------------------------------------------------

    expected_start = float(
        regions[0].get(
            "original_time_start_seconds",
            0,
        )
    )

    expected_end = float(
        regions[-1].get(
            "original_time_end_seconds",
            0,
        )
    )

    expected_duration = (
        expected_end - expected_start
    )

    duration_difference = abs(
        final_duration
        - expected_duration
    )

    # --------------------------------------------------------
    # Save report
    # --------------------------------------------------------

    report = {

        "tool": "TraceX",

        "operation":
            "FINAL_FORENSIC_TIMELINE_VIDEO",

        "source_manifest":
            str(MANIFEST_FILE),

        "final_video":
            str(FINAL_VIDEO),

        "total_timeline_regions":
            len(regions),

        "recovered_regions":
            len(recovered_regions),

        "missing_regions":
            len(missing_regions),

        "expected_timeline_duration_seconds":
            expected_duration,

        "actual_final_video_duration_seconds":
            final_duration,

        "duration_difference_seconds":
            duration_difference,

        "synthetic_content_added":
            True,

        "synthetic_content_description":
            (
                "Black video placeholders labelled "
                "MISSING were inserted for timeline "
                "regions where recoverable source "
                "video data was unavailable. "
                "These placeholders are synthetic "
                "presentation content and are not "
                "forensic evidence."
            ),

        "original_recovered_region_files_preserved":
            True,

        "timeline_order_preserved":
            True,

        "forensic_warning":
            (
                "The final video is a timeline "
                "presentation artifact. The original "
                "reconstructed region files and "
                "region reconstruction manifest "
                "remain the authoritative forensic "
                "artifacts."
            ),

        "validated":
            True,

        "regions": [
            {
                "region_number":
                    region.get(
                        "region_number"
                    ),

                "status":
                    region.get(
                        "scanner_status"
                    ),

                "original_time_start":
                    region.get(
                        "original_time_start"
                    ),

                "original_time_end":
                    region.get(
                        "original_time_end"
                    ),

                "original_time_start_seconds":
                    region.get(
                        "original_time_start_seconds"
                    ),

                "original_time_end_seconds":
                    region.get(
                        "original_time_end_seconds"
                    ),
            }
            for region in regions
        ],
    }

    with open(
        FINAL_REPORT,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            report,
            f,
            indent=4,
        )

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("TRACEX FINAL TIMELINE COMPLETE")
    print("=" * 70)

    print()
    print(
        f"Recovered regions: "
        f"{len(recovered_regions)}"
    )

    print(
        f"Missing regions: "
        f"{len(missing_regions)}"
    )

    print(
        "Synthetic placeholders: YES"
    )

    print(
        "Original recovered files preserved: YES"
    )

    print()
    print(
        f"Final video:\n"
        f"{FINAL_VIDEO}"
    )

    print()
    print(
        f"Final report:\n"
        f"{FINAL_REPORT}"
    )


if __name__ == "__main__":
    main()