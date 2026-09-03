
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path


# ================================================================
# TRACE X RECOVERY WORKFLOW
# ================================================================

try:
    from .recovery_scanner import scan_for_video_files
    from .fragment_scanner import scan_for_video_signatures
except ImportError:
    from recovery_scanner import scan_for_video_files
    from fragment_scanner import scan_for_video_signatures

try:
    from .fragment_extractor import extract_fragment
except ImportError:
    from recovery.fragment_extractor import extract_fragment

try:
    from .recovery_candidate import create_recovery_candidate
except ImportError:
    from recovery.recovery_candidate import create_recovery_candidate

try:
    from .candidate_hash import calculate_sha256
except ImportError:
    from recovery.candidate_hash import calculate_sha256

try:
    from .mp4_sample_recovery_scanner import scan_video
except ImportError:
    from recovery.mp4_sample_recovery_scanner import scan_video

try:
    from .timeline_reconstructor import build_original_timeline
except ImportError:
    from recovery.timeline_reconstructor import build_original_timeline

try:
    from .region_reconstructor import reconstruct_recovered_regions
except ImportError:
    from recovery.region_reconstructor import reconstruct_recovered_regions

# ================================================================
# PATHS
# ================================================================

BACKEND_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

FFMPEG_PATH = (
    Path(r"C:\ffmpeg\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe")
)

FFPROBE_PATH = (
    Path(r"C:\ffmpeg\ffmpeg-9.0.1-essentials_build\bin\ffprobe.exe")
)


# ================================================================
# BASIC COMMAND RUNNER
# ================================================================

def run_command(command):

    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    return (
        process.returncode == 0,
        process.stdout,
        process.stderr
    )


# ================================================================
# TOOL CHECK
# ================================================================

def check_ffmpeg_tools():

    missing = []

    if not FFMPEG_PATH.exists():
        missing.append(str(FFMPEG_PATH))

    if not FFPROBE_PATH.exists():
        missing.append(str(FFPROBE_PATH))

    return {
        "available": len(missing) == 0,
        "missing": missing
    }


# ================================================================
# TIME HELPERS
# ================================================================

def parse_time_value(value, default=0.0):

    if value is None:
        return default

    if isinstance(value, (int, float)):
        return float(value)

    try:
        return float(value)

    except Exception:
        pass

    text = str(value).strip()

    if not text:
        return default

    try:
        if ":" in text:

            parts = text.split(":")

            if len(parts) == 3:

                hours = float(parts[0])
                minutes = float(parts[1])
                seconds = float(parts[2])

                return (
                    hours * 3600
                    +
                    minutes * 60
                    +
                    seconds
                )

    except Exception:
        pass

    return default


def format_time(seconds):

    seconds = max(
        float(seconds),
        0.0
    )

    hours = int(seconds // 3600)

    minutes = int(
        (seconds % 3600)
        // 60
    )

    remaining = (
        seconds
        -
        hours * 3600
        -
        minutes * 60
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{remaining:06.3f}"
    )


# ================================================================
# SIGNATURE NORMALIZATION
# ================================================================

def normalize_signature(signature):

    if not isinstance(signature, dict):
        return signature

    normalized = dict(signature)

    if "position" not in normalized:

        for key in (
            "offset",
            "start_position",
            "start_offset"
        ):

            if key in normalized:

                normalized["position"] = (
                    normalized[key]
                )

                break

    return normalized


# ================================================================
# VIDEO VALIDATION
# ================================================================

def validate_video(video_file):

    video_file = Path(video_file)

    result = {
        "status": "DAMAGED_OR_UNREADABLE",
        "decoded_frames": 0,
        "reported_frames": 0,
        "fps": 0.0,
        "duration": 0.0,
        "file_size": (
            video_file.stat().st_size
            if video_file.exists()
            else 0
        )
    }

    if not video_file.exists():
        return result

    # ------------------------------------------------------------
    # FFPROBE METADATA
    # ------------------------------------------------------------

    command = [
        str(FFPROBE_PATH),
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=nb_frames,r_frame_rate,duration",
        "-show_entries",
        "format=duration",
        "-of", "json",
        str(video_file)
    ]

    ok, stdout, stderr = run_command(command)

    probe = {}

    if ok:
        try:
            probe = json.loads(stdout)
        except Exception:
            probe = {}

    streams = probe.get("streams", [])
    stream = streams[0] if streams else {}

    # ------------------------------------------------------------
    # REPORTED FRAME COUNT
    # ------------------------------------------------------------

    reported_frames = 0

    try:
        reported_frames = int(
            stream.get("nb_frames", 0) or 0
        )
    except Exception:
        reported_frames = 0

    # ------------------------------------------------------------
    # FPS
    # ------------------------------------------------------------

    fps = 0.0

    frame_rate = stream.get("r_frame_rate")

    if frame_rate:
        try:
            if "/" in str(frame_rate):
                numerator, denominator = str(
                    frame_rate
                ).split("/")

                denominator = float(denominator)

                if denominator != 0:
                    fps = (
                        float(numerator)
                        / denominator
                    )
            else:
                fps = float(frame_rate)

        except Exception:
            fps = 0.0

    # ------------------------------------------------------------
    # DURATION
    # ------------------------------------------------------------

    duration = parse_time_value(
        stream.get("duration"),
        0.0
    )

    if duration <= 0:
        duration = parse_time_value(
            probe.get("format", {}).get("duration"),
            0.0
        )

    # ------------------------------------------------------------
    # ACTUAL DECODING TEST
    #
    # IMPORTANT:
    # Do NOT use nb_frames as the decoded-frame count.
    # A damaged/truncated video may report the original frame
    # count even though FFmpeg can decode only part of it.
    # ------------------------------------------------------------

    showinfo_command = [
        str(FFMPEG_PATH),
        "-v", "info",
        "-i", str(video_file),
        "-map", "0:v:0",
        "-vf", "showinfo",
        "-f", "null",
        "-"
    ]

    show_ok, show_stdout, show_stderr = run_command(
        showinfo_command
    )

    combined_output = (
        (show_stdout or "")
        + "\n"
        + (show_stderr or "")
    )

    # FFmpeg showinfo produces one Parsed_showinfo line
    # for every frame that was actually decoded.
    decoded_frames = combined_output.count(
        "Parsed_showinfo"
    )

    # Compatibility fallback for older FFmpeg output.
    if decoded_frames <= 0:
        decoded_frames = combined_output.count(
            "showinfo"
        )

    # ------------------------------------------------------------
    # RESULT
    # ------------------------------------------------------------

    result["decoded_frames"] = decoded_frames
    result["reported_frames"] = reported_frames
    result["fps"] = fps

    if duration > 0:
        result["duration"] = duration

    elif fps > 0 and decoded_frames > 0:
        result["duration"] = (
            decoded_frames / fps
        )

    # ------------------------------------------------------------
    # STATUS
    # ------------------------------------------------------------

    if decoded_frames <= 0:
        result["status"] = "DAMAGED_OR_UNREADABLE"

    elif reported_frames > 0 and decoded_frames < reported_frames:
        result["status"] = "INCOMPLETE"

    else:
        result["status"] = "READABLE"

    return result

# FFMPEG SALVAGE
# ================================================================

def repair_video_with_ffmpeg(
    input_file,
    output_file
):

    input_file = Path(
        input_file
    )

    output_file = Path(
        output_file
    )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    command = [

        str(FFMPEG_PATH),

        "-y",

        "-err_detect",
        "ignore_err",

        "-i",
        str(input_file),

        "-map",
        "0:v:0",

        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-an",

        str(output_file)

    ]

    ok, stdout, stderr = run_command(
        command
    )

    return {

        "success":
            ok and output_file.exists(),

        "input_file":
            str(input_file),

        "output_file":
            str(output_file),

        "stderr":
            stderr,

        "stdout":
            stdout

    }


# ================================================================
# LEGACY RECOVERED-ONLY ASSEMBLY
# ================================================================

def assemble_final_video(
    recovered_files,
    output_file
):

    output_file = Path(
        output_file
    )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if not recovered_files:

        return {

            "success":
                False,

            "output_file":
                str(output_file),

            "reason":
                "No recovered video files."

        }

    temp_dir = (
        output_file.parent
        /
        "_legacy_concat_temp"
    )

    temp_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    concat_file = (
        temp_dir
        /
        "concat.txt"
    )

    with open(
        concat_file,
        "w",
        encoding="utf-8"
    ) as f:

        for video in recovered_files:

            video = Path(video)

            path = str(
                video.resolve()
            ).replace(
                "\\",
                "/"
            )

            f.write(
                f"file '{path}'\n"
            )

    command = [

        str(FFMPEG_PATH),

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

        str(output_file)

    ]

    ok, stdout, stderr = run_command(
        command
    )

    return {

        "success":
            ok and output_file.exists(),

        "output_file":
            str(output_file),

        "stderr":
            stderr,

        "stdout":
            stdout

    }


# ================================================================
# DYNAMIC SAMPLE ANALYSIS
# ================================================================

def run_dynamic_sample_analysis(
    source_file,
    output_folder
):

    output_folder = Path(
        output_folder
    )

    output_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    try:

        result = (
            scan_video(
                str(source_file)
            )
        )

    except TypeError:

        result = (
            scan_video(
                source_file
            )
        )

    if result is None:
        result = {}

    scanner_report_file = (
        output_folder
        /
        "mp4_sample_recovery_scan.json"
    )

    if isinstance(result, dict):

        report = result

    else:

        report = {
            "samples": [],
            "gops": [],
            "regions": []
        }

    with open(
        scanner_report_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            indent=4
        )

    print()
    print("=" * 70)
    print(
        "DYNAMIC MP4 SAMPLE / GOP ANALYSIS"
    )
    print("=" * 70)

    physical_stats = report.get(
        "physical_sample_availability",
        {}
    )

    if isinstance(
        physical_stats,
        dict
    ):

        print(
            f"Mapped samples: "
            f"{physical_stats.get('mapped_sample_count', 0)}"
        )

        print(
            f"Physically present: "
            f"{physical_stats.get('fully_present', 0)}"
        )

        print(
            f"Zero-filled: "
            f"{physical_stats.get('zero_filled', 0)}"
        )

        print(
            f"Suspicious: "
            f"{physical_stats.get('suspicious', 0)}"
        )

        print(
            f"Outside mdat: "
            f"{physical_stats.get('outside_mdat', 0)}"
        )

    print()
    print(
        "REPORT saved to"
    )

    print(
        scanner_report_file
    )

    return {

        "report":
            report,

        "samples":
            report.get(
                "samples",
                []
            ),

        "gops":
            report.get(
                "gops",
                []
            ),

        "regions":
            report.get(
                "regions",
                []
            ),

        "file":
            scanner_report_file

    }


# ================================================================
# DYNAMIC FORENSIC TIMELINE
# ================================================================

def build_dynamic_forensic_timeline(
    dynamic_report,
    output_folder
):

    output_folder = Path(
        output_folder
    )

    samples = dynamic_report.get(
        "samples",
        []
    )

    gops = dynamic_report.get(
        "gops",
        []
    )

    regions = dynamic_report.get(
        "regions",
        []
    )

    # ------------------------------------------------------------
    # FIX:
    # Use the scanner's authoritative physical counters.
    # The scanner stores sample status as "physical_status",
    # not "status".
    # ------------------------------------------------------------

    physical_stats = (
        dynamic_report.get(
            "physical_sample_availability",
            {}
        )
    )

    if (
        isinstance(
            physical_stats,
            dict
        )
        and
        physical_stats
    ):

        total_samples = int(
            physical_stats.get(
                "mapped_sample_count",
                physical_stats.get(
                    "sample_count",
                    len(samples)
                )
            )
            or
            0
        )

        physically_present = int(
            physical_stats.get(
                "fully_present",
                0
            )
            or
            0
        )

        zero_filled = int(
            physical_stats.get(
                "zero_filled",
                0
            )
            or
            0
        )

        suspicious = int(
            physical_stats.get(
                "suspicious",
                0
            )
            or
            0
        )

        outside_mdat = int(
            physical_stats.get(
                "outside_mdat",
                0
            )
            or
            0
        )

    else:

        total_samples = len(
            samples
        )

        physically_present = 0
        zero_filled = 0
        suspicious = 0
        outside_mdat = 0

        for sample in samples:

            status = str(
                sample.get(
                    "physical_status",
                    sample.get(
                        "status",
                        ""
                    )
                )
            ).upper()

            if status in {

                "PHYSICALLY_PRESENT",
                "PRESENT",
                "USABLE"

            }:

                physically_present += 1

            elif status in {

                "ZERO_FILLED",
                "ZERO"

            }:

                zero_filled += 1

            elif status in {

                "LIKELY_CORRUPTED",
                "STRUCTURALLY_SUSPICIOUS",
                "SUSPICIOUS"

            }:

                suspicious += 1

            elif status in {

                "OUTSIDE_MDAT",
                "OUTSIDE_FILE",
                "OUT_OF_FILE"

            }:

                outside_mdat += 1

    physical_percentage = (

        (
            physically_present
            /
            total_samples
            *
            100
        )

        if total_samples > 0

        else 0.0

    )

    print()
    print(
        "PHYSICAL SAMPLE AVAILABILITY"
    )

    print(
        f"Samples physically present: "
        f"{physically_present}/"
        f"{total_samples}"
    )

    print(
        f"Physical sample availability: "
        f"{physical_percentage:.2f}%"
    )

    # ------------------------------------------------------------
    # BUILD TIMELINE REPORT
    # ------------------------------------------------------------

    timeline_regions = []

    for region in regions:

        timeline_regions.append({

            "region_number":
                region.get(
                    "region_number"
                ),

            "scanner_status":
                region.get(
                    "status"
                ),

            "sample_start":
                region.get(
                    "sample_start"
                ),

            "sample_end":
                region.get(
                    "sample_end"
                ),

            "original_time_start":
                region.get(
                    "time_start"
                ),

            "original_time_end":
                region.get(
                    "time_end"
                ),

            "original_time_start_seconds":
                region.get(
                    "time_start_seconds"
                ),

            "original_time_end_seconds":
                region.get(
                    "time_end_seconds"
                ),

            "bad_samples":
                region.get(
                    "bad_samples",
                    []
                ),

            "reason":
                region.get(
                    "reason"
                ),

            "synthetic_content_added":
                region.get(
                    "synthetic_content_added",
                    False
                )

        })

        print(
            f"TIMELINE-REGION-"
            f"{int(region.get('region_number', 0)):03d} "
            f"| "
            f"{region.get('status')} "
            f"| "
            f"{region.get('time_start')} "
            f"â†’ "
            f"{region.get('time_end')}"
        )

    timeline_report = {

        "tool":
            "TraceX",

        "operation":
            "ORIGINAL_FORENSIC_TIMELINE",

        "total_samples":
            total_samples,

        "physically_present_samples":
            physically_present,

        "zero_filled_samples":
            zero_filled,

        "suspicious_samples":
            suspicious,

        "outside_mdat_samples":
            outside_mdat,

        "physical_sample_availability_percentage":
            physical_percentage,

        "total_gops":
            len(gops),

        "total_regions":
            len(timeline_regions),

        "regions":
            timeline_regions,

        "original_timeline_preserved":
            True,

        "synthetic_content_added":
            False

    }

    timeline_file = (
        output_folder
        /
        "original_timeline_mapping.json"
    )

    with open(
        timeline_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            timeline_report,
            f,
            indent=4
        )

    print()
    print(
        "Original timeline mapping saved:"
    )

    print(
        timeline_file
    )

    return timeline_report


# ================================================================
# DECODER REGION ANALYSIS
# ================================================================

def run_decoder_region_analysis(
    source_file,
    output_folder
):

    output_folder = Path(
        output_folder
    )

    decoder_region_file = (
        output_folder
        /
        "decoder_recovery_regions.json"
    )

    validation = validate_video(
        source_file
    )

    decoded_frames = int(
        validation.get(
            "decoded_frames",
            0
        )
        or
        0
    )

    reported_frames = int(
        validation.get(
            "reported_frames",
            0
        )
        or
        0
    )

    fps = float(
        validation.get(
            "fps",
            0.0
        )
        or
        0.0
    )

    duration = float(
        validation.get(
            "duration",
            0.0
        )
        or
        0.0
    )

    regions = []

    if (
        decoded_frames > 0
        and
        fps > 0
    ):

        recovered_duration = (
            decoded_frames
            /
            fps
        )

        recovered_duration = min(
            recovered_duration,
            duration
            if duration > 0
            else recovered_duration
        )

        regions.append({

            "region_number":
                1,

            "scanner_status":
                "RECOVERED",

            "original_time_start_seconds":
                0.0,

            "original_time_end_seconds":
                recovered_duration,

            "recovery_basis":
                "DECODER_OBSERVED",

            "decoded_frames":
                decoded_frames,

            "reported_frames":
                reported_frames,

            "decoder_validated":
                True

        })

        if (
            duration > recovered_duration
        ):

            regions.append({

                "region_number":
                    2,

                "scanner_status":
                    "MISSING",

                "original_time_start_seconds":
                    recovered_duration,

                "original_time_end_seconds":
                    duration,

                "recovery_basis":
                    "DECODER_OBSERVED",

                "decoder_validated":
                    True

            })

    report = {

        "tool":
            "TraceX",

        "operation":
            "DECODER_OBSERVED_RECOVERY_REGIONS",

        "source_file":
            str(source_file),

        "decoded_frames":
            decoded_frames,

        "reported_frames":
            reported_frames,

        "fps":
            fps,

        "duration":
            duration,

        "regions":
            regions,

        "synthetic_content_added":
            False

    }

    with open(
        decoder_region_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            indent=4
        )

    print()
    print(
        "DECODER-OBSERVED RECOVERY REGION ANALYSIS"
    )

    return (
        report,
        decoder_region_file
    )


# ================================================================
# DECODER FALLBACK MANIFEST
# ================================================================

def build_decoder_fallback_manifest(
    salvage_validation,
    salvaged_video,
    output_folder,
    evidence_id,
    source_validation,
    decoder_region_analysis
):

    salvaged_video = Path(
        salvaged_video
    )

    if not salvaged_video.exists():
        return None

    reconstructed_dir = (
        Path(output_folder)
        /
        "reconstructed_regions"
    )

    reconstructed_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    recovered_duration = parse_time_value(
        salvage_validation.get(
            "duration",
            0.0
        ),
        0.0
    )

    if recovered_duration <= 0:

        decoded_frames = int(
            salvage_validation.get(
                "decoded_frames",
                0
            )
            or
            0
        )

        fps = float(
            salvage_validation.get(
                "fps",
                0.0
            )
            or
            0.0
        )

        if fps > 0:

            recovered_duration = (
                decoded_frames
                /
                fps
            )

    source_duration = parse_time_value(
        source_validation.get(
            "duration",
            0.0
        ),
        0.0
    )

    recovered_region_file = (
        reconstructed_dir
        /
        "DECODER-OBSERVED-REGION-001.mp4"
    )

    copy_command = [

        str(FFMPEG_PATH),

        "-y",

        "-i",
        str(salvaged_video),

        "-map",
        "0:v:0",

        "-c:v",
        "copy",

        "-an",

        str(recovered_region_file)

    ]

    ok, stdout, stderr = run_command(
        copy_command
    )

    if not ok:

        return None

    regions = [

        {

            "region_number":
                1,

            "scanner_status":
                "RECOVERED",

            "original_time_start_seconds":
                0.0,

            "original_time_end_seconds":
                recovered_duration,

            "output_file":
                str(recovered_region_file),

            "recovery_basis":
                "DECODER_OBSERVED",

            "structural_gop_recovery":
                False,

            "decoder_validated":
                True

        }

    ]

    if (
        source_duration > recovered_duration
    ):

        regions.append({

            "region_number":
                2,

            "scanner_status":
                "MISSING",

            "original_time_start_seconds":
                recovered_duration,

            "original_time_end_seconds":
                source_duration,

            "output_file":
                None,

            "recovery_basis":
                "DECODER_OBSERVED",

            "structural_gop_recovery":
                False,

            "decoder_validated":
                True

        })

    manifest = {

        "tool":
            "TraceX",

        "operation":
            "DECODER_OBSERVED_REGION_RECONSTRUCTION",

        "evidence_id":
            evidence_id,

        "source_file":
            str(
                source_validation.get(
                    "source_file",
                    ""
                )
            ),

        "successfully_reconstructed":
            1,

        "regions":
            regions,

        "synthetic_content_added":
            False,

        "forensic_note":
            (
                "Decoder-observed recovery is based "
                "only on frames actually decoded from "
                "the salvaged video. Absence of a later "
                "region does not prove that no later "
                "recoverable fragment exists."
            )

    }

    return manifest


# ================================================================
# FINAL TIMELINE VIDEO
# ================================================================

def create_final_timeline_video(
    region_manifest,
    output_folder
):

    output_folder = Path(
        output_folder
    )

    regions = (
        region_manifest.get(
            "regions",
            []
        )
    )

    if not regions:

        raise RuntimeError(
            "Region reconstruction manifest "
            "contains no regions."
        )

    first_recovered = None

    for region in regions:

        if str(
            region.get(
                "scanner_status",
                ""
            )
        ).upper() != "RECOVERED":

            continue

        output_file = region.get(
            "output_file"
        )

        if not output_file:
            continue

        candidate = Path(
            output_file
        )

        if not candidate.is_absolute():

            candidate = (
                BACKEND_DIR
                /
                candidate
            )

        if candidate.exists():

            first_recovered = candidate

            break

    if first_recovered is None:

        raise RuntimeError(
            "No recovered region video exists."
        )

    # ------------------------------------------------------------
    # Probe recovered region.
    # ------------------------------------------------------------

    command = [

        str(FFPROBE_PATH),

        "-v",
        "error",

        "-select_streams",
        "v:0",

        "-show_entries",
        "stream=width,height,r_frame_rate",

        "-of",
        "json",

        str(first_recovered)

    ]

    ok, stdout, stderr = run_command(
        command
    )

    if not ok:

        raise RuntimeError(
            "Could not probe recovered region:\n"
            +
            stderr
        )

    probe = json.loads(
        stdout
    )

    stream = (
        probe.get(
            "streams",
            [{}]
        )[0]
    )

    width = int(
        stream.get(
            "width",
            0
        )
        or
        0
    )

    height = int(
        stream.get(
            "height",
            0
        )
        or
        0
    )

    fps_text = stream.get(
        "r_frame_rate",
        "30/1"
    )

    fps = 30.0

    try:

        if "/" in str(fps_text):

            numerator, denominator = (
                str(fps_text).split("/")
            )

            denominator = float(
                denominator
            )

            if denominator != 0:

                fps = (
                    float(numerator)
                    /
                    denominator
                )

        else:

            fps = float(
                fps_text
            )

    except Exception:

        fps = 30.0

    print(
        f"Resolution: "
        f"{width} x {height}"
    )

    print(
        f"FPS: "
        f"{fps:.6f}"
    )

    temp_dir = (
        output_folder
        /
        "_final_timeline_temp"
    )

    temp_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    final_video = (
        output_folder
        /
        "FINAL_TIMELINE_VIDEO.mp4"
    )

    final_report = (
        output_folder
        /
        "FINAL_TIMELINE_VIDEO_REPORT.json"
    )

    segment_files = []

    # ------------------------------------------------------------
    # Create segments.
    # ------------------------------------------------------------

    for region in regions:

        region_number = int(
            region.get(
                "region_number",
                0
            )
        )

        status = str(
            region.get(
                "scanner_status",
                ""
            )
        ).upper()

        start = parse_time_value(
            region.get(
                "original_time_start_seconds",
                region.get(
                    "original_time_start",
                    0
                )
            ),
            0.0
        )

        end = parse_time_value(
            region.get(
                "original_time_end_seconds",
                region.get(
                    "original_time_end",
                    start
                )
            ),
            start
        )

        duration = max(
            end - start,
            0.0
        )

        print()
        print(
            f"REGION-{region_number:03d}"
        )

        print(
            f"Timeline: "
            f"{format_time(start)} "
            f"â†’ "
            f"{format_time(end)}"
        )

        print(
            f"Status: "
            f"{status}"
        )

        if status == "RECOVERED":

            output_file = region.get(
                "output_file"
            )

            if not output_file:

                raise RuntimeError(
                    f"Recovered REGION-{region_number:03d} "
                    "has no output_file."
                )

            recovered_file = Path(
                output_file
            )

            if not recovered_file.is_absolute():

                recovered_file = (
                    BACKEND_DIR
                    /
                    recovered_file
                )

            if not recovered_file.exists():

                raise FileNotFoundError(
                    "Recovered region file not found:\n"
                    +
                    str(recovered_file)
                )

            print(
                "Using recovered evidence:"
            )

            print(
                recovered_file
            )

            print(
                "Recovery basis:",
                region.get(
                    "recovery_basis",
                    "STRUCTURAL"
                )
            )

            segment_files.append(
                recovered_file
            )

        else:

            # ----------------------------------------------------
            # Synthetic black placeholder.
            # ----------------------------------------------------

            missing_file = (
                temp_dir
                /
                (
                    f"REGION-"
                    f"{region_number:03d}"
                    f"_MISSING.mp4"
                )
            )

            text = (
                f"MISSING - REGION "
                f"{region_number:03d}"
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

                str(FFMPEG_PATH),

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

                str(missing_file)

            ]

            ok, _, stderr = run_command(
                command
            )

            if not ok:

                raise RuntimeError(
                    "Could not create missing "
                    "timeline placeholder:\n"
                    +
                    stderr
                )

            segment_files.append(
                missing_file
            )

            print(
                "Synthetic placeholder created."
            )

    if not segment_files:

        raise RuntimeError(
            "No timeline segments were created."
        )

    # ------------------------------------------------------------
    # Concatenate timeline segments.
    # ------------------------------------------------------------

    concat_file = (
        temp_dir
        /
        "timeline_concat.txt"
    )

    with open(
        concat_file,
        "w",
        encoding="utf-8"
    ) as f:

        for segment in segment_files:

            path = str(
                segment.resolve()
            ).replace(
                "\\",
                "/"
            )

            path = path.replace(
                "'",
                "'\\''"
            )

            f.write(
                f"file '{path}'\n"
            )

    command = [

        str(FFMPEG_PATH),

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

        str(final_video)

    ]

    ok, stdout, stderr = run_command(
        command
    )

    if not ok:

        raise RuntimeError(
            "Final timeline video assembly failed:\n"
            +
            stderr
        )

    # ------------------------------------------------------------
    # Validate final timeline.
    # ------------------------------------------------------------

    command = [

        str(FFPROBE_PATH),

        "-v",
        "error",

        "-show_entries",
        "format=duration,size",

        "-show_entries",
        "stream=codec_name,width,height,nb_frames",

        "-of",
        "json",

        str(final_video)

    ]

    ok, stdout, stderr = run_command(
        command
    )

    if not ok:

        raise RuntimeError(
            "Final timeline validation failed:\n"
            +
            stderr
        )

    validation = json.loads(
        stdout
    )

    format_info = validation.get(
        "format",
        {}
    )

    final_duration = parse_time_value(
        format_info.get(
            "duration",
            0
        ),
        0.0
    )

    try:

        final_size = int(
            float(
                format_info.get(
                    "size",
                    0
                )
            )
        )

    except Exception:

        final_size = 0

    expected_start = parse_time_value(
        regions[0].get(
            "original_time_start_seconds",
            regions[0].get(
                "original_time_start",
                0
            )
        ),
        0.0
    )

    expected_end = parse_time_value(
        regions[-1].get(
            "original_time_end_seconds",
            regions[-1].get(
                "original_time_end",
                expected_start
            )
        ),
        expected_start
    )

    expected_duration = max(
        expected_end - expected_start,
        0.0
    )

    duration_difference = abs(
        final_duration
        -
        expected_duration
    )

    recovered_count = sum(

        1

        for region in regions

        if str(
            region.get(
                "scanner_status",
                ""
            )
        ).upper()
        == "RECOVERED"

    )

    missing_count = (
        len(regions)
        -
        recovered_count
    )

    report = {

        "tool":
            "TraceX",

        "operation":
            "FINAL_FORENSIC_TIMELINE_VIDEO",

        "source_manifest":
            str(
                output_folder
                /
                "reconstructed_regions"
                /
                "region_reconstruction_manifest.json"
            ),

        "final_video":
            str(final_video),

        "total_timeline_regions":
            len(regions),

        "recovered_regions":
            recovered_count,

        "missing_regions":
            missing_count,

        "expected_timeline_duration_seconds":
            expected_duration,

        "actual_final_video_duration_seconds":
            final_duration,

        "duration_difference_seconds":
            duration_difference,

        "synthetic_content_added":
            missing_count > 0,

        "synthetic_content_description":
            (
                "Black video placeholders labelled "
                "MISSING were inserted for timeline "
                "regions where recoverable source video "
                "data was unavailable. These placeholders "
                "are synthetic presentation content and "
                "are not forensic evidence."
            ),

        "original_recovered_region_files_preserved":
            True,

        "timeline_order_preserved":
            True,

        "timeline_positions_authoritative_source":
            (
                "region_reconstruction_manifest.json"
            ),

        "forensic_warning":
            (
                "The final video is a timeline "
                "presentation artifact. Original recovered "
                "region files and the region reconstruction "
                "manifest remain the authoritative forensic "
                "artifacts."
            ),

        "validated":
            True,

        "final_file_size_bytes":
            final_size,

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

                "recovery_basis":
                    region.get(
                        "recovery_basis"
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
                    )

            }

            for region in regions

        ]

    }

    with open(
        final_report,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            indent=4
        )

    print()
    print(
        "FINAL TIMELINE CREATED"
    )

    print("â”€" * 70)

    print(
        f"File: {final_video}"
    )

    print(
        f"Size: {final_size:,} bytes"
    )

    print(
        f"Duration: "
        f"{final_duration:.6f} seconds"
    )

    print()
    print(
        "Final timeline report:"
    )

    print(
        final_report
    )

    return {

        "video":
            final_video,

        "report":
            final_report,

        "validation":
            validation

    }


# ================================================================
# MAIN RECOVERY WORKFLOW
# ================================================================

def run_recovery_workflow(
    source_file,
    output_folder,
    evidence_id
):

    source_file = Path(
        source_file
    )

    output_folder = Path(
        output_folder
    )

    output_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    print()
    print("=" * 70)
    print(
        "             TRACEX RECOVERY WORKFLOW"
    )
    print("=" * 70)

    print()
    print(
        f"Evidence ID: {evidence_id}"
    )

    print(
        f"Source: {source_file}"
    )

    print(
        f"Output: {output_folder}"
    )

    if not source_file.exists():

        raise FileNotFoundError(
            f"Source file not found:\n"
            f"{source_file}"
        )

    # ============================================================
    # TOOL CHECK
    # ============================================================

    tool_check = check_ffmpeg_tools()

    if not tool_check["available"]:

        raise RuntimeError(
            "FFmpeg/FFprobe tools are missing:\n"
            +
            "\n".join(
                tool_check["missing"]
            )
        )

    # ============================================================
    # 1. SOURCE VALIDATION
    # ============================================================

    print()
    print(
        "[1/8] SOURCE VALIDATION"
    )

    source_validation = validate_video(
        source_file
    )

    source_validation["source_file"] = (
        str(source_file)
    )

    print(
        f"Status: "
        f"{source_validation['status']}"
    )

    print(
        f"Actually decoded frames: "
        f"{source_validation['decoded_frames']}"
    )

    print(
        f"Reported frames: "
        f"{source_validation['reported_frames']}"
    )

    print(
        f"FPS: "
        f"{source_validation['fps']}"
    )

    print(
        f"Duration: "
        f"{source_validation['duration']}"
    )

    # ============================================================
    # 2. SIGNATURE SCAN
    # ============================================================

    print()
    print(
        "[2/8] VIDEO SIGNATURE SCAN"
    )

    try:

        signatures = scan_for_video_signatures(
            str(source_file)
        )

    except Exception as exc:

        signatures = {
            "error": str(exc)
        }

    signature_file = (
        output_folder
        /
        "video_signatures.json"
    )

    with open(
        signature_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            signatures,
            f,
            indent=4
        )

    if isinstance(signatures, list):

        print(
            f"Signatures found: "
            f"{len(signatures)}"
        )

    else:

        print(
            "Signature scan completed."
        )

    # ============================================================
    # 2A. DYNAMIC SAMPLE/GOP ANALYSIS
    # ============================================================

    dynamic_result = (
        run_dynamic_sample_analysis(
            source_file,
            output_folder
        )
    )

    dynamic_report = (
        dynamic_result["report"]
    )

    # ============================================================
    # 2B. ORIGINAL FORENSIC TIMELINE
    # ============================================================

    print()
    print(
        "[2B] BUILDING ORIGINAL FORENSIC TIMELINE"
    )

    timeline = (
        build_dynamic_forensic_timeline(
            dynamic_report,
            output_folder
        )
    )

    # ============================================================
    # 3. CANDIDATE EXTRACTION
    # ============================================================

    print()
    print(
        "[3/8] RECOVERY CANDIDATE EXTRACTION"
    )

    candidate_file = (
        output_folder
        /
        "recovery_candidate.bin"
    )

    candidate_created = False
    candidate_info = {}

    try:

        if (
            isinstance(signatures, list)
            and
            signatures
        ):

            normalized_signature = (
                normalize_signature(
                    signatures[0]
                )
            )

            print(
                "Candidate signature normalized."
            )

            if not isinstance(
                normalized_signature,
                dict
            ):

                raise TypeError(
                    "Video signature is not a dictionary."
                )

            start_position = (
                normalized_signature.get(
                    "position"
                )
            )

            if start_position is None:
                start_position = normalized_signature.get(
                    "offset"
                )

            if start_position is None:
                start_position = normalized_signature.get(
                    "start_position"
                )

            if start_position is None:
                start_position = normalized_signature.get(
                    "start_offset"
                )

            if start_position is None:

                raise ValueError(
                    "No byte position was found "
                    "in the video signature."
                )

            try:

                start_position = int(
                    start_position
                )

            except Exception:

                start_position = int(
                    float(start_position)
                )

            print(
                f"Candidate start position: "
                f"{start_position}"
            )

            bytes_extracted = (
                extract_fragment(
                    str(source_file),
                    str(candidate_file),
                    start_position
                )
            )

            candidate_info = {

                "source_file":
                    str(source_file),

                "output_file":
                    str(candidate_file),

                "start_position":
                    start_position,

                "end_position":
                    os.path.getsize(
                        source_file
                    ),

                "bytes_extracted":
                    int(bytes_extracted)

            }

            if (
                candidate_file.exists()
                and
                candidate_file.stat().st_size > 0
            ):

                candidate_created = True

                print(
                    "Candidate fragment extracted."
                )

                print(
                    f"Bytes extracted: "
                    f"{candidate_file.stat().st_size:,}"
                )

            else:

                print(
                    "Candidate extractor returned "
                    "but no usable candidate file was created."
                )

        else:

            print(
                "No usable signature candidate."
            )

    except Exception as exc:

        candidate_info = {
            "error": str(exc)
        }

        print(
            f"Candidate extraction skipped: "
            f"{exc}"
        )

    # ============================================================
    # 4. CANDIDATE VALIDATION
    # ============================================================

    print()
    print(
        "[4/8] CANDIDATE VALIDATION"
    )

    if candidate_created:

        try:

            candidate_validation = (
                validate_video(
                    candidate_file
                )
            )

        except Exception as exc:

            candidate_validation = {

                "status":
                    "VALIDATION_ERROR",

                "error":
                    str(exc)

            }

        print(
            f"Candidate status: "
            f"{candidate_validation.get('status')}"
        )

    else:

        candidate_validation = {
            "status": "NO_CANDIDATE"
        }

        print(
            "No candidate available."
        )

    # ============================================================
    # 5. CANDIDATE RECORD
    # ============================================================

    print()
    print(
        "[5/8] CANDIDATE RECORD"
    )

    if candidate_created:

        try:

            recovery_candidate = (
                create_recovery_candidate(
                    str(candidate_file),
                    evidence_id
                )
            )

        except Exception as exc:

            recovery_candidate = {
                "error": str(exc)
            }

    else:

        recovery_candidate = {
            "status": "NO_CANDIDATE"
        }

    candidate_record_file = (
        output_folder
        /
        "recovery_candidate.json"
    )

    with open(
        candidate_record_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            recovery_candidate,
            f,
            indent=4
        )

    # ============================================================
    # 6. SHA-256
    # ============================================================

    print()
    print(
        "[6/8] CANDIDATE SHA-256"
    )

    candidate_sha256 = None

    if candidate_created:

        try:

            candidate_sha256 = (
                calculate_sha256(
                    str(candidate_file)
                )
            )

            print(
                f"SHA-256: "
                f"{candidate_sha256}"
            )

        except Exception as exc:

            print(
                f"SHA-256 failed: "
                f"{exc}"
            )

    else:

        print(
            "No candidate to hash."
        )

    # ============================================================
    # 7. FFMPEG SALVAGE
    # ============================================================

    print()
    print(
        "[7/8] FFMPEG VIDEO SALVAGE"
    )

    salvaged_video = (
        output_folder
        /
        f"{evidence_id}_ffmpeg_salvaged.mp4"
    )

    salvage_result = (
        repair_video_with_ffmpeg(
            source_file,
            salvaged_video
        )
    )

    print(
        f"Salvage success: "
        f"{salvage_result['success']}"
    )

    if salvage_result.get("success"):

        salvage_validation = (
            validate_video(
                salvaged_video
            )
        )

        print(
            f"Salvaged decoded frames: "
            f"{salvage_validation['decoded_frames']}"
        )

    else:

        salvage_validation = {

            "status":
                "SALVAGE_FAILED",

            "decoded_frames":
                0,

            "reported_frames":
                0,

            "fps":
                0.0,

            "duration":
                0.0

        }

    # ============================================================
    # 8. LEGACY RECOVERED-ONLY VIDEO
    # ============================================================

    print()
    print(
        "[8/8] LEGACY RECOVERED-ONLY VIDEO"
    )

    recovered_only_video = (
        output_folder
        /
        f"{evidence_id}_final_recovered_video.mp4"
    )

    recovered_files = []

    if (
        salvage_result.get("success")
        and
        salvaged_video.exists()
    ):

        recovered_files.append(
            salvaged_video
        )

    legacy_assembly = (
        assemble_final_video(
            recovered_files,
            recovered_only_video
        )
    )

    print(
        f"Recovered-only video created: "
        f"{legacy_assembly.get('success')}"
    )

    # ============================================================
    # DECODER-OBSERVED ANALYSIS
    # ============================================================

    (
        decoder_region_analysis,
        decoder_region_file
    ) = run_decoder_region_analysis(
        source_file,
        output_folder
    )

    # ============================================================
    # REGION RECONSTRUCTION
    # ============================================================

    print()
    print("=" * 70)
    print(
        "REGION-BASED FORENSIC RECONSTRUCTION"
    )
    print("=" * 70)

    reconstructed_dir = (
        output_folder
        /
        "reconstructed_regions"
    )

    reconstructed_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    scanner_report_file = (
        output_folder
        /
        "mp4_sample_recovery_scan.json"
    )

    region_manifest = None
    region_reconstruction_error = None

    try:

        region_manifest = (
            reconstruct_recovered_regions(
                source_file,
                scanner_report_file,
                reconstructed_dir
            )
        )

        print()
        print(
            "Region reconstruction completed."
        )

    except Exception as exc:

        region_reconstruction_error = str(
            exc
        )

        print()
        print(
            "Region reconstruction failed:"
        )

        print(exc)

    # ============================================================
    # DECODER FALLBACK
    # ============================================================

    decoder_fallback_used = False

    reconstructed_count = 0

    if region_manifest is not None:

        try:

            reconstructed_count = int(
                region_manifest.get(
                    "successfully_reconstructed",
                    0
                )
                or
                0
            )

        except Exception:

            reconstructed_count = 0

    if (
        reconstructed_count <= 0
        and
        salvage_result.get("success")
        and
        salvaged_video.exists()
    ):

        print()
        print("=" * 70)
        print(
            "DECODER-OBSERVED RECOVERY FALLBACK"
        )
        print("=" * 70)

        decoder_fallback_manifest = (
            build_decoder_fallback_manifest(
                salvage_validation,
                salvaged_video,
                output_folder,
                evidence_id,
                source_validation,
                decoder_region_analysis
            )
        )

        if decoder_fallback_manifest is not None:

            region_manifest = (
                decoder_fallback_manifest
            )

            decoder_fallback_used = True

            manifest_file = (
                reconstructed_dir
                /
                "region_reconstruction_manifest.json"
            )

            with open(
                manifest_file,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    region_manifest,
                    f,
                    indent=4
                )

            print()
            print(
                "Decoder-observed recovered region created."
            )

            print(
                f"Decoded frames: "
                f"{salvage_validation.get('decoded_frames', 0)}"
            )

            print(
                "Recovery basis: DECODER_OBSERVED"
            )

            print(
                "Structural GOP reconstruction: False"
            )

            print()
            print(
                "Manifest saved:"
            )

            print(
                manifest_file
            )

        else:

            print()
            print(
                "Decoder fallback could not be created."
            )

    # ============================================================
    # FINAL TIMELINE VIDEO
    # ============================================================

    final_timeline_result = None
    final_timeline_error = None

    if region_manifest is not None:

        print()
        print("=" * 70)
        print(
            "FINAL TIMELINE PRESENTATION"
        )
        print("=" * 70)

        available_recovered_regions = 0

        for region in region_manifest.get(
            "regions",
            []
        ):

            if str(
                region.get(
                    "scanner_status",
                    ""
                )
            ).upper() != "RECOVERED":

                continue

            output_file = region.get(
                "output_file"
            )

            if not output_file:
                continue

            candidate = Path(
                output_file
            )

            if not candidate.is_absolute():

                candidate = (
                    BACKEND_DIR
                    /
                    candidate
                )

            if candidate.exists():

                available_recovered_regions += 1

        if available_recovered_regions <= 0:

            final_timeline_error = (
                "No recovered region video exists "
                "for final timeline assembly."
            )

            print()
            print(
                "Final timeline skipped:"
            )

            print(
                final_timeline_error
            )

        else:

            try:

                final_timeline_result = (
                    create_final_timeline_video(
                        region_manifest,
                        output_folder
                    )
                )

            except Exception as exc:

                final_timeline_error = str(
                    exc
                )

                print()
                print(
                    "Final timeline creation failed:"
                )

                print(exc)

    # ============================================================
    # FINAL STATISTICS
    # ============================================================

    samples = dynamic_result.get("samples", [])
    gops = dynamic_report.get("gop_analysis", [])
    dynamic_regions = dynamic_report.get("recovery_regions", [])

    # ------------------------------------------------------------
    # FIX:
    # Use authoritative scanner counters first.
    # Fallback to sample["physical_status"].
    # ------------------------------------------------------------

    physical_stats = (
        dynamic_report.get(
            "physical_sample_availability",
            {}
        )
    )

    if (
        isinstance(
            physical_stats,
            dict
        )
        and
        physical_stats
    ):

        total_samples = int(
            physical_stats.get(
                "mapped_sample_count",
                physical_stats.get(
                    "sample_count",
                    len(samples)
                )
            )
            or
            0
        )

        physically_present_samples = int(
            physical_stats.get(
                "fully_present",
                0
            )
            or
            0
        )

        zero_filled_samples = int(
            physical_stats.get(
                "zero_filled",
                0
            )
            or
            0
        )

        suspicious_samples = int(
            physical_stats.get(
                "suspicious",
                0
            )
            or
            0
        )

        outside_mdat_samples = int(
            physical_stats.get(
                "outside_mdat",
                0
            )
            or
            0
        )

    else:

        total_samples = len(
            samples
        )

        physically_present_samples = 0
        zero_filled_samples = 0
        suspicious_samples = 0
        outside_mdat_samples = 0

        for sample in samples:

            status = str(
                sample.get(
                    "physical_status",
                    sample.get(
                        "status",
                        ""
                    )
                )
            ).upper()

            if status in {

                "PHYSICALLY_PRESENT",
                "PRESENT",
                "USABLE"

            }:

                physically_present_samples += 1

            elif status in {

                "ZERO_FILLED",
                "ZERO"

            }:

                zero_filled_samples += 1

            elif status in {

                "LIKELY_CORRUPTED",
                "STRUCTURALLY_SUSPICIOUS",
                "SUSPICIOUS"

            }:

                suspicious_samples += 1

            elif status in {

                "OUTSIDE_MDAT",
                "OUTSIDE_FILE",
                "OUT_OF_FILE"

            }:

                outside_mdat_samples += 1

    physical_sample_percentage = (

        (
            physically_present_samples
            /
            total_samples
            *
            100
        )

        if total_samples > 0

        else 0.0

    )

    # ============================================================
    # STRUCTURAL GOP STATISTICS
    #
    # The dynamic MP4 scanner stores authoritative GOP
    # information under "gop_analysis".
    # ============================================================

    scanner_gops = []

    try:

        scanner_gops = dynamic_result.get(
            "gop_analysis",
            []
        )

    except Exception:

        scanner_gops = []

    if not isinstance(scanner_gops, list):

        scanner_gops = []

    # Fallback to the report object if required.
    if not scanner_gops:

        try:

            scanner_gops = dynamic_report.get(
                "gop_analysis",
                []
            )

        except Exception:

            scanner_gops = []

    if not isinstance(scanner_gops, list):

        scanner_gops = []

    total_gops = len(
        scanner_gops
    )

    recoverable_gops = 0

    for gop in scanner_gops:

        if not isinstance(gop, dict):

            continue

        status = str(
            gop.get(
                "status",
                gop.get(
                    "recovery_status",
                    ""
                )
            )
        ).upper()

        if status in {

            "RECOVERED",
            "RECOVERABLE",
            "FULLY_RECOVERED",
            "FULLY_RECOVERABLE"

        }:

            recoverable_gops += 1

    gop_percentage = (

        (
            recoverable_gops
            /
            total_gops
            *
            100
        )

        if total_gops > 0

        else 0.0

    )

    # ============================================================
    # DYNAMIC TIMELINE STATISTICS
    # ============================================================

    recovered_dynamic_regions = [

        region

        for region in dynamic_regions

        if str(
            region.get(
                "status",
                ""
            )
        ).upper()
        in {
            "RECOVERED",
            "RECOVERABLE"
        }

    ]

    missing_dynamic_regions = [

        region

        for region in dynamic_regions

        if str(
            region.get(
                "status",
                ""
            )
        ).upper()
        not in {
            "RECOVERED",
            "RECOVERABLE"
        }

    ]

    structural_recovered_duration = 0.0
    structural_missing_duration = 0.0

    for region in dynamic_regions:

        start_value = region.get(
            "time_start_seconds"
        )

        if start_value is None:

            start_value = region.get(
                "time_start",
                0
            )

        end_value = region.get(
            "time_end_seconds"
        )

        if end_value is None:

            end_value = region.get(
                "time_end",
                start_value
            )

        start = parse_time_value(
            start_value,
            0.0
        )

        end = parse_time_value(
            end_value,
            start
        )

        duration = max(
            end - start,
            0.0
        )

        status = str(
            region.get(
                "status",
                ""
            )
        ).upper()

        if status in {

            "RECOVERED",
            "RECOVERABLE"

        }:

            structural_recovered_duration += (
                duration
            )

        else:

            structural_missing_duration += (
                duration
            )

    # ============================================================
    # DECODER-OBSERVED RECOVERY
    # ============================================================

    try:

        salvage_decoded_frames = int(
            salvage_validation.get(
                "decoded_frames",
                0
            )
            or
            0
        )

    except Exception:

        salvage_decoded_frames = 0

    # ============================================================
    # FORENSIC DECODER STATISTICS
    #
    # FFmpeg salvage can sometimes report a frame count that is
    # larger than the original container frame count because the
    # damaged stream is being reinterpreted during salvage.
    #
    # Therefore:
    #   - physical_sample_availability remains authoritative
    #   - decoder frames are capped at the source frame count
    #   - this prevents impossible percentages above 100%
    # ============================================================

    try:

        reported_source_frames = int(
            source_validation.get(
                "reported_frames",
                0
            )
            or
            0
        )

    except Exception:

        reported_source_frames = 0

    if (
        reported_source_frames > 0
        and
        salvage_decoded_frames > reported_source_frames
    ):

        salvage_decoded_frames = (
            reported_source_frames
        )

    decoder_observed_recovery_percentage = 0.0

    if (
        source_validation["reported_frames"] > 0
        and
        salvage_decoded_frames > 0
    ):

        decoder_observed_recovery_percentage = (

            salvage_decoded_frames
            /
            source_validation["reported_frames"]
            *
            100

        )

    elif (
        source_validation["reported_frames"] > 0
        and
        source_validation["decoded_frames"] > 0
    ):

        decoder_observed_recovery_percentage = (

            source_validation["decoded_frames"]
            /
            source_validation["reported_frames"]
            *
            100

        )

    # ============================================================
    # FINAL TIMELINE STATISTICS
    #
    # Calculate timeline recovery directly from the dynamic
    # forensic regions produced by the MP4 sample scanner.
    # These regions preserve the original recording positions.
    # ============================================================

    timeline_recovered_duration = 0.0
    timeline_missing_duration = 0.0

    for region in dynamic_regions:

        start = parse_time_value(
            region.get(
                "time_start_seconds",
                0
            ),
            0.0
        )

        end = parse_time_value(
            region.get(
                "time_end_seconds",
                start
            ),
            start
        )

        duration = max(
            end - start,
            0.0
        )

        status = str(
            region.get(
                "status",
                ""
            )
        ).upper()

        if status in {
            "RECOVERED",
            "RECOVERABLE"
        }:

            timeline_recovered_duration += duration

        else:

            timeline_missing_duration += duration

    if decoder_fallback_used:

        fallback_regions = (
            region_manifest.get(
                "regions",
                []
            )
        )

        timeline_recovered_duration = 0.0
        timeline_missing_duration = 0.0

        for region in fallback_regions:

            start = parse_time_value(
                region.get(
                    "original_time_start_seconds",
                    0
                ),
                0.0
            )

            end = parse_time_value(
                region.get(
                    "original_time_end_seconds",
                    start
                ),
                start
            )

            duration = max(
                end - start,
                0.0
            )

            status = str(
                region.get(
                    "scanner_status",
                    ""
                )
            ).upper()

            if status == "RECOVERED":

                timeline_recovered_duration += (
                    duration
                )

            else:

                timeline_missing_duration += (
                    duration
                )

    total_timeline_duration = (

        timeline_recovered_duration
        +
        timeline_missing_duration

    )

    timeline_recovery_percentage = (

        (
            timeline_recovered_duration
            /
            total_timeline_duration
            *
            100
        )

        if total_timeline_duration > 0

        else 0.0

    )

    # ============================================================
    # REGION RECONSTRUCTION STATISTICS
    # ============================================================

    reconstructed_region_count = 0

    if region_manifest is not None:

        for region in region_manifest.get(
            "regions",
            []
        ):

            if str(
                region.get(
                    "scanner_status",
                    ""
                )
            ).upper() != "RECOVERED":

                continue

            output_file = region.get(
                "output_file"
            )

            if not output_file:
                continue

            candidate = Path(
                output_file
            )

            if not candidate.is_absolute():

                candidate = (
                    BACKEND_DIR
                    /
                    candidate
                )

            if candidate.exists():

                reconstructed_region_count += 1

    reconstruction_performed = (
        reconstructed_region_count > 0
    )

    final_timeline_created = (
        final_timeline_result is not None
    )

    # ============================================================
    # OVERALL STATUS
    # ============================================================

    # A video must NOT be classified as FULLY_RECOVERED merely
    # because FFmpeg can decode it.
    #
    # Physical sample availability and the forensic timeline
    # are authoritative for recovery completeness.
    #
    # If even one expected sample is physically unavailable,
    # or the original timeline contains a missing region,
    # the result cannot be FULLY_RECOVERED.

    physical_recovery_complete = (

        total_samples > 0

        and

        physically_present_samples >= total_samples

    )

    timeline_recovery_complete = (

        timeline_missing_duration <= 0.000001

        and

        len(missing_dynamic_regions) == 0

    )

    gop_recovery_complete = (

        total_gops > 0

        and

        recoverable_gops == total_gops

    )

    if (

        source_validation["status"] == "READABLE"

        and

        physical_recovery_complete

        and

        timeline_recovery_complete

        and

        gop_recovery_complete

    ):

        overall_status = (

            "FULLY_RECOVERED"

        )

    elif (

        len(recovered_dynamic_regions) > 0

        or

        salvage_decoded_frames > 0

        or

        source_validation["decoded_frames"] > 0

        or

        reconstructed_region_count > 0

    ):

        overall_status = (

            "PARTIALLY_RECOVERED"

        )

    else:

        overall_status = (

            "RECOVERY_FAILED"

        )

    # ============================================================
    # FINAL RECOVERY REPORT
    # ============================================================

    recovery_report = {

        "tool":
            "TraceX",

        "operation":
            "COMPLETE_FORENSIC_RECOVERY_WORKFLOW",

        "generated_at":
            datetime.now().isoformat(),

        "evidence_id":
            evidence_id,

        "source_file":
            str(source_file),

        "source_validation":
            source_validation,

        "overall_status":
            overall_status,

        # --------------------------------------------------------
        # PHYSICAL SAMPLE AVAILABILITY
        # --------------------------------------------------------

        "total_mp4_samples":
            total_samples,

        "physically_present_samples":
            physically_present_samples,

        "zero_filled_samples":
            zero_filled_samples,

        "suspicious_samples":
            suspicious_samples,

        "outside_mdat_samples":
            outside_mdat_samples,

        "physical_sample_availability_percentage":
            physical_sample_percentage,

        "structural_sample_recovery_percentage":
            physical_sample_percentage,

        # --------------------------------------------------------
        # DECODER-OBSERVED RECOVERY
        # --------------------------------------------------------

        "decoder_observed_recovered_frames":
            salvage_decoded_frames,

        "decoder_observed_reported_frames":
            source_validation[
                "reported_frames"
            ],

        "decoder_observed_recovery_percentage":
            decoder_observed_recovery_percentage,

        # --------------------------------------------------------
        # STRUCTURAL GOP RECOVERY
        # --------------------------------------------------------

        "total_gops":
            total_gops,

        "recoverable_gops":
            recoverable_gops,

        "unrecoverable_gops":
            max(
                total_gops
                -
                recoverable_gops,
                0
            ),

        "gop_recovery_percentage":
            gop_percentage,

        # --------------------------------------------------------
        # TIMELINE RECOVERY
        # --------------------------------------------------------

        "recovered_timeline_duration_seconds":
            timeline_recovered_duration,

        "missing_timeline_duration_seconds":
            timeline_missing_duration,

        "timeline_recovery_percentage":
            timeline_recovery_percentage,

        "timeline_preserved":
            True,

        # --------------------------------------------------------
        # DYNAMIC REGIONS
        # --------------------------------------------------------

        "dynamic_recovery_regions":
            dynamic_regions,

        "dynamic_recovered_regions":
            recovered_dynamic_regions,

        "dynamic_missing_regions":
            missing_dynamic_regions,

        # --------------------------------------------------------
        # DECODER REGION ANALYSIS
        # --------------------------------------------------------

        "decoder_recovery_regions":
            decoder_region_analysis,

        "decoder_fallback_used":
            decoder_fallback_used,

        # --------------------------------------------------------
        # CANDIDATE
        # --------------------------------------------------------

        "candidate_created":
            candidate_created,

        "candidate_info":
            candidate_info,

        "candidate_sha256":
            candidate_sha256,

        "candidate_validation":
            candidate_validation,

        # --------------------------------------------------------
        # FFMPEG SALVAGE
        # --------------------------------------------------------

        "ffmpeg_salvage":
            salvage_result,

        "ffmpeg_salvage_validation":
            salvage_validation,

        # --------------------------------------------------------
        # LEGACY RECOVERED-ONLY VIDEO
        # --------------------------------------------------------

        "recovered_only_video":
            (
                str(recovered_only_video)
                if recovered_only_video.exists()
                else None
            ),

        "recovered_only_video_is_timeline_compressed":
            True,

        # --------------------------------------------------------
        # REGION RECONSTRUCTION
        # --------------------------------------------------------

        "reconstruction_performed":
            reconstruction_performed,

        "reconstructed_region_count":
            reconstructed_region_count,

        "region_reconstruction_manifest":
            (
                str(
                    reconstructed_dir
                    /
                    "region_reconstruction_manifest.json"
                )
                if region_manifest is not None
                else None
            ),

        "region_reconstruction_error":
            region_reconstruction_error,

        # --------------------------------------------------------
        # FINAL TIMELINE
        # --------------------------------------------------------

        "final_timeline_video_created":
            final_timeline_created,

        "final_timeline_video":
            (
                str(
                    final_timeline_result["video"]
                )
                if final_timeline_result
                else None
            ),

        "final_timeline_video_report":
            (
                str(
                    final_timeline_result["report"]
                )
                if final_timeline_result
                else None
            ),

        "final_timeline_error":
            final_timeline_error,

        "synthetic_content_added":
            (
                final_timeline_created
                and
                any(
                    str(
                        region.get(
                            "scanner_status",
                            ""
                        )
                    ).upper() != "RECOVERED"

                    for region in (
                        region_manifest.get(
                            "regions",
                            []
                        )
                        if region_manifest
                        else []
                    )
                )
            ),

        "synthetic_content_note":
            (
                "Synthetic content refers only to "
                "black MISSING placeholders used in "
                "the final timeline presentation video. "
                "No synthetic footage is used in forensic "
                "recovered region files."
            ),

        # --------------------------------------------------------
        # FORENSIC NOTES
        # --------------------------------------------------------

        "forensic_notes": [

            (
                "Physical sample availability indicates "
                "that sample bytes exist inside the source "
                "container. It does not prove decoder-level "
                "recoverability."
            ),

            (
                "Decoder-observed recovery is kept separate "
                "from structural GOP recovery."
            ),

            (
                "A decoder-observed recovered region does "
                "not mean that the complete original GOP "
                "was recovered."
            ),

            (
                "Structural GOP recovery requires the "
                "necessary H.264 dependency chain to remain "
                "recoverable."
            ),

            (
                "Missing regions are not treated as recovered "
                "merely because later sample bytes exist "
                "physically in the source."
            ),

            (
                "FFmpeg salvage identifies video frames that "
                "the decoder can actually recover."
            ),

            (
                "The dynamic MP4 sample/GOP scanner determines "
                "structural recoverability."
            ),

            (
                "The original forensic timeline mapping "
                "preserves the source timeline positions."
            ),

            (
                "The final timeline video may contain "
                "synthetic black placeholders and is therefore "
                "a presentation/reconstruction artifact."
            ),

            (
                "Original recovered region files and their "
                "manifest remain the authoritative forensic "
                "recovery artifacts."
            ),

            (
                "The original evidence file is never modified "
                "by this workflow."
            ),

            (
                "Candidate extraction is an auxiliary recovery "
                "stage and does not override dynamic MP4 "
                "sample/GOP or decoder-observed analysis."
            )

        ],

        # --------------------------------------------------------
        # OUTPUT FILES
        # --------------------------------------------------------

        "output_files": {

            "scanner_report":
                str(
                    output_folder
                    /
                    "mp4_sample_recovery_scan.json"
                ),

            "timeline_mapping":
                str(
                    output_folder
                    /
                    "original_timeline_mapping.json"
                ),

            "candidate_record":
                str(
                    candidate_record_file
                ),

            "decoder_recovery_regions":
                str(
                    decoder_region_file
                ),

            "region_reconstruction_manifest":
                (
                    str(
                        reconstructed_dir
                        /
                        "region_reconstruction_manifest.json"
                    )
                    if region_manifest is not None
                    else None
                ),

            "final_timeline_video":
                (
                    str(
                        final_timeline_result["video"]
                    )
                    if final_timeline_result
                    else None
                ),

            "final_timeline_report":
                (
                    str(
                        final_timeline_result["report"]
                    )
                    if final_timeline_result
                    else None
                )

        }

    }

    recovery_report_file = (
        output_folder
        /
        f"{evidence_id}_recovery_report.json"
    )

    with open(
        recovery_report_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            recovery_report,
            f,
            indent=4
        )

    # ============================================================
    # FINAL CONSOLE SUMMARY
    # ============================================================

    print()
    print("=" * 70)
    print(
        "             TRACEX RECOVERY COMPLETE"
    )
    print("=" * 70)

    print()
    print(
        f"Evidence ID: "
        f"{evidence_id}"
    )

    print(
        f"Overall status: "
        f"{overall_status}"
    )

    print()
    print(
        "PHYSICAL SAMPLE AVAILABILITY"
    )

    print(
        f"Samples physically present: "
        f"{physically_present_samples}"
        f"/"
        f"{total_samples}"
    )

    print(
        f"Physical sample availability: "
        f"{physical_sample_percentage:.2f}%"
    )

    print()
    print(
        "DECODER-OBSERVED RECOVERY"
    )

    print(
        f"Decoded frames: "
        f"{salvage_decoded_frames}"
        f"/"
        f"{source_validation['reported_frames']}"
    )

    print(
        f"Decoder recovery: "
        f"{decoder_observed_recovery_percentage:.2f}%"
    )

    print()
    print(
        "STRUCTURAL GOP RECOVERY"
    )

    print(
        f"Recoverable GOPs: "
        f"{recoverable_gops}"
        f"/"
        f"{total_gops}"
    )

    print(
        f"GOP recovery: "
        f"{gop_percentage:.2f}%"
    )

    print()
    print(
        "TIMELINE RECOVERY"
    )

    print(
        f"Recovered duration: "
        f"{timeline_recovered_duration:.3f} seconds"
    )

    print(
        f"Missing duration: "
        f"{timeline_missing_duration:.3f} seconds"
    )

    print(
        f"Timeline recovery: "
        f"{timeline_recovery_percentage:.2f}%"
    )

    print()
    print(
        "REGION RECONSTRUCTION"
    )

    print(
        f"Recovered region files: "
        f"{reconstructed_region_count}"
    )

    print(
        f"Reconstruction performed: "
        f"{reconstruction_performed}"
    )

    print(
        f"Decoder fallback used: "
        f"{decoder_fallback_used}"
    )

    print()
    print(
        "FINAL TIMELINE"
    )

    print(
        f"Created: "
        f"{final_timeline_created}"
    )

    if final_timeline_result:

        print(
            f"Video: "
            f"{final_timeline_result['video']}"
        )

    elif final_timeline_error:

        print(
            f"Reason: "
            f"{final_timeline_error}"
        )

    print()
    print(
        "FINAL RECOVERY REPORT"
    )

    print(
        recovery_report_file
    )

    print()
    print(
        "TraceX complete recovery pipeline finished."
    )

    return recovery_report


# ================================================================
# DIRECT EXECUTION
# ================================================================

if __name__ == "__main__":

    backend_folder = (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )

    # ------------------------------------------------------------
    # CURRENT TEST EVIDENCE
    #
    # Change ONLY these three values when testing another file.
    # ------------------------------------------------------------

    source_file = (
        backend_folder
        /
        "recovery"
        /
        "test_data"
        /
        "damaged_test.mp4"
    )

    evidence_id = (
        "EVD-TEST-RECOVERY"
    )

    output_folder = (
        backend_folder
        /
        "output"
        /
        "recovery"
        /
        evidence_id
    )

    run_recovery_workflow(
        source_file=source_file,
        output_folder=output_folder,
        evidence_id=evidence_id
    )