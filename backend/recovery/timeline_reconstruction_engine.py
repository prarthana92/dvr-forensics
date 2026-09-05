import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime


# ============================================================
# TRACE-X TIMELINE RECONSTRUCTION ENGINE
# ============================================================
#
# Purpose:
#
#   Extract independently recovered regions from the ORIGINAL
#   damaged video using the authoritative forensic timeline.
#
# Workflow:
#
#   Original damaged video
#           ↓
#   Original timeline mapping
#           ↓
#   RECOVERED regions only
#           ↓
#   Extract each region independently
#           ↓
#   Validate extracted region
#           ↓
#   Create recovered-region files
#           ↓
#   Create forensic manifest
#           ↓
#   Create timeline-compressed preview
#
# IMPORTANT:
#
#   Missing footage is NEVER fabricated.
#   NOT_DECODE_VALIDATED regions are NEVER included.
#   PARTIAL regions are NEVER included.
#
#   The timeline manifest remains authoritative for the
#   original timestamps and gaps.
#
#   timeline_preview.mp4 is a recovered-only,
#   timeline-compressed preview.
#
#   It is NOT the original continuous recording.
# ============================================================


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = (
    Path(__file__).resolve().parent.parent
)

RECOVERY_OUTPUT_DIR = (
    BASE_DIR
    / "output"
    / "recovery"
)

FFMPEG = Path(
    r"C:\ffmpeg\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe"
)

FFPROBE = Path(
    r"C:\ffmpeg\ffmpeg-9.0.1-essentials_build\bin\ffprobe.exe"
)


# ============================================================
# VIDEO NAME
# ============================================================

def get_safe_video_name(
    video_path
):

    video_name = (
        Path(video_path).stem
    )

    safe_name = ""

    for character in video_name:

        if (
            character.isalnum()
            or character in (
                "-",
                "_"
            )
        ):

            safe_name += character

        else:

            safe_name += "_"

    return safe_name


# ============================================================
# VIDEO RECOVERY DIRECTORY
# ============================================================

def get_video_recovery_directory(
    video_path
):

    safe_name = (
        get_safe_video_name(
            video_path
        )
    )

    return (
        RECOVERY_OUTPUT_DIR
        / safe_name
    )


# ============================================================
# REPORT PATHS
# ============================================================

def get_timeline_file(
    video_path
):

    return (
        get_video_recovery_directory(
            video_path
        )
        / "original_timeline_mapping.json"
    )


def get_validation_file(
    video_path
):

    return (
        get_video_recovery_directory(
            video_path
        )
        / "sample_level_validation.json"
    )


# ============================================================
# OUTPUT PATHS
# ============================================================

def get_output_directory(
    video_path
):

    return (
        get_video_recovery_directory(
            video_path
        )
        / "timeline_reconstruction"
    )


def get_region_directory(
    video_path
):

    return (
        get_output_directory(
            video_path
        )
        / "recovered_regions"
    )


def get_manifest_file(
    video_path
):

    return (
        get_output_directory(
            video_path
        )
        / "timeline_reconstruction.json"
    )


def get_preview_file(
    video_path
):

    return (
        get_output_directory(
            video_path
        )
        / "timeline_preview.mp4"
    )


# ============================================================
# TIMESTAMP FORMATTER
# ============================================================

def format_timestamp(
    seconds
):

    if seconds is None:

        return "UNKNOWN"

    try:

        seconds = float(
            seconds
        )

    except (
        TypeError,
        ValueError
    ):

        return "UNKNOWN"

    milliseconds = int(
        round(
            seconds * 1000
        )
    )

    hours = (
        milliseconds
        // 3_600_000
    )

    milliseconds %= 3_600_000

    minutes = (
        milliseconds
        // 60_000
    )

    milliseconds %= 60_000

    secs = (
        milliseconds
        // 1000
    )

    milliseconds %= 1000

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{secs:02d}."
        f"{milliseconds:03d}"
    )


# ============================================================
# LOAD JSON
# ============================================================

def load_json(
    path
):

    if not path.exists():

        raise FileNotFoundError(
            f"File not found: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(
            file
        )


# ============================================================
# SAVE JSON
# ============================================================

def save_json(
    path,
    data
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )


# ============================================================
# GET INPUT VIDEO
# ============================================================

def get_input_video():

    if len(sys.argv) < 2:

        raise ValueError(
            "No input video was provided.\n\n"
            "Usage:\n"
            'python -m recovery.timeline_reconstruction_engine '
            '".\\recovery\\test_data\\video.mp4"'
        )

    video_path = Path(
        sys.argv[1]
    ).resolve()

    if not video_path.exists():

        raise FileNotFoundError(
            f"Input video not found: {video_path}"
        )

    return video_path


# ============================================================
# RUN PROCESS
# ============================================================

def run_process(
    command
):

    print()
    print(
        "Running:"
    )

    print(
        " ".join(
            f'"{item}"'
            if " " in str(item)
            else str(item)
            for item in command
        )
    )

    print()

    result = subprocess.run(
        [
            str(item)
            for item in command
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    return result


# ============================================================
# PROBE VIDEO
# ============================================================

def probe_video(
    video_path
):

    command = [

        str(FFPROBE),

        "-v",
        "error",

        "-select_streams",
        "v:0",

        "-show_entries",
        "stream=codec_name,width,height,avg_frame_rate,nb_frames",

        "-show_entries",
        "format=duration",

        "-of",
        "json",

        str(video_path)
    ]

    result = run_process(
        command
    )

    if result.returncode != 0:

        return {
            "success": False,
            "error": result.stderr
        }

    try:

        data = json.loads(
            result.stdout
        )

    except json.JSONDecodeError:

        return {
            "success": False,
            "error":
                "FFprobe returned invalid JSON."
        }

    streams = data.get(
        "streams",
        []
    )

    stream = (
        streams[0]
        if streams
        else {}
    )

    format_data = data.get(
        "format",
        {}
    )

    return {

        "success": True,

        "codec_name":
            stream.get(
                "codec_name"
            ),

        "width":
            stream.get(
                "width"
            ),

        "height":
            stream.get(
                "height"
            ),

        "avg_frame_rate":
            stream.get(
                "avg_frame_rate"
            ),

        "nb_frames":
            stream.get(
                "nb_frames"
            ),

        "duration":
            format_data.get(
                "duration"
            )
    }


# ============================================================
# EXTRACT ONE RECOVERED REGION
# ============================================================

def extract_recovered_region(
    region,
    source_video,
    destination
):

    start_time = region.get(
        "start_timestamp_seconds"
    )

    end_time = region.get(
        "end_timestamp_seconds"
    )

    if start_time is None:

        raise ValueError(
            f"{region['region_id']} has no "
            "start timestamp."
        )

    if end_time is None:

        raise ValueError(
            f"{region['region_id']} has no "
            "end timestamp."
        )

    start_time = float(
        start_time
    )

    end_time = float(
        end_time
    )

    if end_time <= start_time:

        raise ValueError(
            f"{region['region_id']} has an "
            "invalid time range."
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # We decode and re-encode the selected interval.
    #
    # This creates a derivative recovered-region file.
    # It does NOT fabricate footage.
    #
    # The source material remains the original damaged video.
    # --------------------------------------------------------

    command = [

        FFMPEG,

        "-y",

        "-hide_banner",

        "-loglevel",
        "warning",

        "-ss",
        f"{start_time:.6f}",

        "-to",
        f"{end_time:.6f}",

        "-i",
        source_video,

        "-map",
        "0:v:0",

        "-an",

        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-crf",
        "18",

        "-pix_fmt",
        "yuv420p",

        "-movflags",
        "+faststart",

        destination
    ]

    result = run_process(
        command
    )

    if result.returncode != 0:

        print(
            "FFmpeg extraction failed."
        )

        print(
            result.stderr
        )

        return False

    if not destination.exists():

        return False

    if destination.stat().st_size <= 0:

        return False

    return True


# ============================================================
# VALIDATE EXTRACTED REGION
# ============================================================

def validate_extracted_region(
    video_path
):

    command = [

        FFPROBE,

        "-v",
        "error",

        "-select_streams",
        "v:0",

        "-count_frames",

        "-show_entries",
        "stream=nb_read_frames,duration",

        "-of",
        "json",

        video_path
    ]

    result = run_process(
        command
    )

    if result.returncode != 0:

        return {

            "valid": False,

            "error":
                result.stderr.strip()
        }

    try:

        data = json.loads(
            result.stdout
        )

    except json.JSONDecodeError:

        return {

            "valid": False,

            "error":
                "Invalid FFprobe response."
        }

    streams = data.get(
        "streams",
        []
    )

    if not streams:

        return {

            "valid": False,

            "error":
                "No video stream found."
        }

    stream = streams[0]

    frame_count = (
        stream.get(
            "nb_read_frames"
        )
    )

    duration = (
        stream.get(
            "duration"
        )
    )

    try:

        frame_count = int(
            frame_count
        )

    except (
        TypeError,
        ValueError
    ):

        frame_count = 0

    try:

        duration = float(
            duration
        )

    except (
        TypeError,
        ValueError
    ):

        duration = None

    return {

        "valid":
            frame_count > 0,

        "decoded_frames":
            frame_count,

        "duration_seconds":
            duration
    }


# ============================================================
# CREATE RECOVERED REGION RECORD
# ============================================================

def create_region_record(
    region,
    destination,
    validation
):

    return {

        "region_id":
            region["region_id"],

        "forensic_status":
            "RECOVERED",

        "start_sample":
            region.get(
                "start_sample"
            ),

        "end_sample":
            region.get(
                "end_sample"
            ),

        "sample_count":
            region.get(
                "sample_count",
                0
            ),

        "original_start_timestamp_seconds":
            region.get(
                "start_timestamp_seconds"
            ),

        "original_end_timestamp_seconds":
            region.get(
                "end_timestamp_seconds"
            ),

        "original_start_timestamp":
            region.get(
                "start_timestamp"
            ),

        "original_end_timestamp":
            region.get(
                "end_timestamp"
            ),

        "recovered_file":
            str(
                destination
            ),

        "recovered_file_name":
            destination.name,

        "decoded_frames_in_extracted_file":
            validation.get(
                "decoded_frames",
                0
            ),

        "extracted_duration_seconds":
            validation.get(
                "duration_seconds"
            ),

        "extracted_file_valid":
            validation.get(
                "valid",
                False
            ),

        "synthetic_content":
            False,

        "synthetic_frames_created":
            0,

        "reconstruction_method":
            "TIMESTAMP_BOUNDED_DECODER_VALIDATED_REGION_EXTRACTION"
    }


# ============================================================
# BUILD FORENSIC MANIFEST
# ============================================================

def build_manifest(
    video_path,
    timeline_data,
    region_records
):

    recovered_lookup = {

        item["region_id"]:
            item

        for item in region_records
    }

    manifest_regions = []

    for region in timeline_data.get(
        "regions",
        []
    ):

        region_id = (
            region["region_id"]
        )

        status = (
            region["status"]
        )

        entry = {

            "region_id":
                region_id,

            "forensic_status":
                status,

            "start_sample":
                region.get(
                    "start_sample"
                ),

            "end_sample":
                region.get(
                    "end_sample"
                ),

            "sample_count":
                region.get(
                    "sample_count",
                    0
                ),

            "start_timestamp_seconds":
                region.get(
                    "start_timestamp_seconds"
                ),

            "end_timestamp_seconds":
                region.get(
                    "end_timestamp_seconds"
                ),

            "start_timestamp":
                region.get(
                    "start_timestamp"
                ),

            "end_timestamp":
                region.get(
                    "end_timestamp"
                ),

            "synthetic_content":
                False,

            "content_available":
                False,

            "recovered_file":
                None,

            "recovered_file_name":
                None,

            "reconstruction_method":
                None
        }

        # ----------------------------------------------------
        # Only independently extracted and validated regions
        # are marked as having a recovered file.
        # ----------------------------------------------------

        if (
            region_id
            in recovered_lookup
        ):

            recovered = (
                recovered_lookup[
                    region_id
                ]
            )

            entry[
                "content_available"
            ] = True

            entry[
                "recovered_file"
            ] = recovered[
                "recovered_file"
            ]

            entry[
                "recovered_file_name"
            ] = recovered[
                "recovered_file_name"
            ]

            entry[
                "extracted_file_valid"
            ] = recovered[
                "extracted_file_valid"
            ]

            entry[
                "decoded_frames_in_extracted_file"
            ] = recovered[
                "decoded_frames_in_extracted_file"
            ]

            entry[
                "reconstruction_method"
            ] = recovered[
                "reconstruction_method"
            ]

        else:

            if status == "NOT_DECODE_VALIDATED":

                entry[
                    "reconstruction_method"
                ] = (
                    "NO_DECODER_VALIDATED_CONTENT"
                )

            elif status == "PARTIAL_NOT_RECOVERED":

                entry[
                    "reconstruction_method"
                ] = (
                    "PARTIAL_DATA_NOT_USED"
                )

            elif status == "MISSING":

                entry[
                    "reconstruction_method"
                ] = (
                    "NO_RECOVERABLE_DATA"
                )

            elif status == "UNKNOWN":

                entry[
                    "reconstruction_method"
                ] = (
                    "UNKNOWN_FORENSIC_STATUS"
                )

            else:

                entry[
                    "reconstruction_method"
                ] = (
                    "NO_RECOVERED_REGION_FILE"
                )

        manifest_regions.append(
            entry
        )

    recovered_count = sum(
        1
        for region in manifest_regions
        if (
            region[
                "forensic_status"
            ]
            == "RECOVERED"
        )
    )

    manifest = {

        "reconstruction_type":
            "ORIGINAL_TIMELINE_FORENSIC_RECONSTRUCTION",

        "created_at":
            datetime.now().isoformat(),

        "source_video":
            str(
                video_path
            ),

        "source_timeline":
            str(
                get_timeline_file(
                    video_path
                )
            ),

        "source_validation":
            str(
                get_validation_file(
                    video_path
                )
            ),

        "original_sample_count":
            timeline_data.get(
                "original_sample_count"
            ),

        "original_duration_seconds":
            timeline_data.get(
                "original_duration_seconds"
            ),

        "original_duration":
            timeline_data.get(
                "original_duration"
            ),

        "timeline_preserved":
            True,

        "recovered_region_count":
            len(region_records),

        "timeline_recovered_region_count":
            recovered_count,

        "synthetic_frames_created":
            0,

        "synthetic_content_added":
            False,

        "forensic_integrity_rule":
            (
                "Only regions explicitly classified as "
                "RECOVERED by the sample-level decoder "
                "validation are extracted. "
                "NOT_DECODE_VALIDATED, partial, missing, "
                "and unknown regions are never fabricated."
            ),

        "preview_warning":
            (
                "timeline_preview.mp4 is a "
                "timeline-compressed preview containing "
                "recovered regions only. Missing timeline "
                "intervals are omitted from the preview. "
                "The preview must not be interpreted as a "
                "continuous representation of the original "
                "recording. The original timeline positions "
                "are preserved in this manifest."
            ),

        "regions":
            manifest_regions
    }

    return manifest


# ============================================================
# CREATE TIMELINE-COMPRESSED PREVIEW
# ============================================================

def create_preview(
    region_records,
    preview_file
):

    if not region_records:

        print()
        print(
            "No independently recovered regions exist."
        )

        print(
            "Timeline preview will not be created."
        )

        return False

    valid_regions = [

        region

        for region in region_records

        if (
            region.get(
                "extracted_file_valid",
                False
            )
            and Path(
                region[
                    "recovered_file"
                ]
            ).exists()
        )
    ]

    if not valid_regions:

        print()
        print(
            "No valid extracted region files "
            "are available for preview."
        )

        return False

    output_dir = (
        preview_file.parent
    )

    concat_file = (
        output_dir
        / "preview_concat.txt"
    )

    with open(
        concat_file,
        "w",
        encoding="utf-8"
    ) as file:

        for region in valid_regions:

            video_path = (
                Path(
                    region[
                        "recovered_file"
                    ]
                )
                .resolve()
            )

            escaped_path = (
                str(video_path)
                .replace(
                    "\\",
                    "/"
                )
                .replace(
                    "'",
                    "'\\''"
                )
            )

            file.write(
                f"file '{escaped_path}'\n"
            )

    command = [

        FFMPEG,

        "-y",

        "-hide_banner",

        "-loglevel",
        "warning",

        "-f",
        "concat",

        "-safe",
        "0",

        "-i",
        concat_file,

        "-c",
        "copy",

        preview_file
    ]

    result = run_process(
        command
    )

    try:

        concat_file.unlink()

    except OSError:

        pass

    if result.returncode != 0:

        print(
            "Preview creation failed."
        )

        print(
            result.stderr
        )

        return False

    return (
        preview_file.exists()
        and preview_file.stat().st_size > 0
    )


# ============================================================
# MAIN
# ============================================================

def reconstruct_timeline():

    print()
    print("=" * 70)
    print(
        "       TRACE-X FORENSIC TIMELINE RECONSTRUCTION"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # Input
    # --------------------------------------------------------

    video_path = (
        get_input_video()
    )

    timeline_file = (
        get_timeline_file(
            video_path
        )
    )

    validation_file = (
        get_validation_file(
            video_path
        )
    )

    output_dir = (
        get_output_directory(
            video_path
        )
    )

    region_dir = (
        get_region_directory(
            video_path
        )
    )

    manifest_file = (
        get_manifest_file(
            video_path
        )
    )

    preview_file = (
        get_preview_file(
            video_path
        )
    )

    # --------------------------------------------------------
    # Display paths
    # --------------------------------------------------------

    print()
    print(
        "Input video:"
    )

    print(
        video_path
    )

    print()
    print(
        "Timeline mapping:"
    )

    print(
        timeline_file
    )

    print()
    print(
        "Validation report:"
    )

    print(
        validation_file
    )

    print()
    print(
        "Output directory:"
    )

    print(
        output_dir
    )

    # --------------------------------------------------------
    # Verify dependencies
    # --------------------------------------------------------

    if not FFMPEG.exists():

        raise FileNotFoundError(
            f"FFmpeg not found: {FFMPEG}"
        )

    if not FFPROBE.exists():

        raise FileNotFoundError(
            f"FFprobe not found: {FFPROBE}"
        )

    # --------------------------------------------------------
    # Verify reports
    # --------------------------------------------------------

    if not timeline_file.exists():

        raise FileNotFoundError(
            "Timeline mapping does not exist.\n"
            "Run timeline_reconstructor.py first."
        )

    if not validation_file.exists():

        raise FileNotFoundError(
            "Sample-level validation report does not exist.\n"
            "Run sample_level_validator.py first."
        )

    # --------------------------------------------------------
    # Prepare directories
    # --------------------------------------------------------

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    region_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Load reports
    # --------------------------------------------------------

    timeline_data = load_json(
        timeline_file
    )

    validation_data = load_json(
        validation_file
    )

    # --------------------------------------------------------
    # Display validation summary
    # --------------------------------------------------------

    validation_stats = (
        validation_data.get(
            "decoder_validation",
            {}
        )
    )

    validated_count = (
        validation_stats.get(
            "validated_recovered_samples"
        )
    )

    if validated_count is None:

        validated_count = len(
            validation_data.get(
                "validated_sample_numbers",
                []
            )
        )

    print()
    print(
        "Decoder-validated samples:"
    )

    print(
        validated_count
    )

    # --------------------------------------------------------
    # Find RECOVERED timeline regions.
    #
    # These are the ONLY regions eligible for extraction.
    # --------------------------------------------------------

    all_regions = timeline_data.get(
        "regions",
        []
    )

    recovered_regions = [

        region

        for region in all_regions

        if region.get(
            "status"
        ) == "RECOVERED"
    ]

    print()
    print(
        "Original timeline regions:"
    )

    print(
        len(
            all_regions
        )
    )

    print()
    print(
        "RECOVERED regions eligible for extraction:"
    )

    print(
        len(
            recovered_regions
        )
    )

    # --------------------------------------------------------
    # Probe original source
    # --------------------------------------------------------

    source_probe = probe_video(
        video_path
    )

    print()
    print(
        "SOURCE VIDEO CHECK"
    )

    print("-" * 70)

    print(
        "FFprobe success:",
        source_probe.get(
            "success"
        )
    )

    print(
        "Codec:",
        source_probe.get(
            "codec_name"
        )
    )

    print(
        "Duration:",
        source_probe.get(
            "duration"
        )
    )

    # --------------------------------------------------------
    # Extract each recovered region independently.
    # --------------------------------------------------------

    region_records = []

    for index, region in enumerate(
        recovered_regions
    ):

        region_id = (
            region[
                "region_id"
            ]
        )

        destination = (
            region_dir
            / f"{region_id}_recovered.mp4"
        )

        print()
        print("=" * 70)

        print(
            f"RECOVERED REGION "
            f"{index + 1}/"
            f"{len(recovered_regions)}"
        )

        print("=" * 70)

        print()
        print(
            "Region:",
            region_id
        )

        print(
            "Samples:",
            region.get(
                "start_sample"
            ),
            "→",
            region.get(
                "end_sample"
            )
        )

        print(
            "Original time:",
            region.get(
                "start_timestamp"
            ),
            "→",
            region.get(
                "end_timestamp"
            )
        )

        print()

        success = (
            extract_recovered_region(
                region,
                video_path,
                destination
            )
        )

        if not success:

            print()
            print(
                "WARNING:"
            )

            print(
                f"{region_id} could not be "
                "independently extracted."
            )

            print(
                "It will NOT be marked as a "
                "successfully reconstructed region."
            )

            continue

        # ----------------------------------------------------
        # Validate extracted file.
        # ----------------------------------------------------

        extraction_validation = (
            validate_extracted_region(
                destination
            )
        )

        print()
        print(
            "Extracted file validation:"
        )

        print(
            "Valid:",
            extraction_validation.get(
                "valid"
            )
        )

        print(
            "Decoded frames:",
            extraction_validation.get(
                "decoded_frames"
            )
        )

        print(
            "Extracted duration:",
            extraction_validation.get(
                "duration_seconds"
            )
        )

        if not extraction_validation.get(
            "valid",
            False
        ):

            print()
            print(
                "WARNING:"
            )

            print(
                f"{region_id} produced an "
                "invalid extracted file."
            )

            print(
                "The file will NOT be included "
                "as a recovered region."
            )

            try:

                destination.unlink()

            except OSError:

                pass

            continue

        record = (
            create_region_record(
                region,
                destination,
                extraction_validation
            )
        )

        region_records.append(
            record
        )

        print()
        print(
            "Recovered region created:"
        )

        print(
            destination
        )

    # --------------------------------------------------------
    # Build manifest.
    # --------------------------------------------------------

    manifest = build_manifest(
        video_path,
        timeline_data,
        region_records
    )

    save_json(
        manifest_file,
        manifest
    )

    # --------------------------------------------------------
    # Create preview.
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "CREATING TIMELINE-COMPRESSED PREVIEW"
    )
    print("=" * 70)

    preview_created = (
        create_preview(
            region_records,
            preview_file
        )
    )

    # --------------------------------------------------------
    # Final summary.
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "       TIMELINE RECONSTRUCTION COMPLETE"
    )
    print("=" * 70)

    print()

    print(
        "Original timeline duration:",
        timeline_data.get(
            "original_duration"
        )
    )

    print(
        "Original timeline regions:",
        len(
            all_regions
        )
    )

    print(
        "Recovered regions identified:",
        len(
            recovered_regions
        )
    )

    print(
        "Recovered region files created:",
        len(
            region_records
        )
    )

    print(
        "Synthetic content created:",
        "NO"
    )

    print(
        "Original timeline preserved:",
        "YES"
    )

    print()

    print(
        "Recovered region files:"
    )

    for record in region_records:

        print(
            f"  {record['region_id']} | "
            f"samples "
            f"{record['start_sample']} → "
            f"{record['end_sample']} | "
            f"{record['original_start_timestamp']} → "
            f"{record['original_end_timestamp']}"
        )

        print(
            f"      {record['recovered_file_name']}"
        )

    print()

    print(
        "Forensic timeline manifest:"
    )

    print(
        manifest_file
    )

    if preview_created:

        print()

        print(
            "Timeline-compressed preview:"
        )

        print(
            preview_file
        )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "The recovered region files contain only "
        "independently extracted recovered intervals."
    )

    print(
        "NOT_DECODE_VALIDATED, partial, and missing "
        "timeline intervals were not fabricated."
    )

    print(
        "The preview omits unrecovered time and therefore "
        "must NOT be interpreted as a continuous original "
        "recording."
    )

    print(
        "The forensic manifest preserves the original "
        "timeline positions and gaps."
    )

    print()
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        reconstruct_timeline()

    except Exception as error:

        print()
        print("=" * 70)
        print(
            "TIMELINE RECONSTRUCTION ERROR"
        )
        print("=" * 70)

        print()
        print(
            str(error)
        )

        print()
        print("=" * 70)