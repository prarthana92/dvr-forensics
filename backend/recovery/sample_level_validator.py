import os
import sys
import json
import subprocess
import re
from datetime import datetime

import cv2


# ============================================================
# FFMPEG / FFPROBE PATHS
# ============================================================

FFPROBE = r"C:\ffmpeg\ffmpeg-9.0.1-essentials_build\bin\ffprobe.exe"
FFMPEG = r"C:\ffmpeg\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe"


# ============================================================
# DIRECTORIES
# ============================================================

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RECOVERY_OUTPUT_DIR = os.path.join(
    BACKEND_DIR,
    "output",
    "recovery"
)


# ============================================================
# PATH HELPERS
# ============================================================

def get_safe_video_name(video_path):
    """
    Creates a safe folder name from the input video filename.
    """

    filename = os.path.basename(video_path)
    stem = os.path.splitext(filename)[0]

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)

    return safe_name


def get_video_recovery_directory(video_path):
    """
    Returns the recovery output directory for this specific video.
    """

    safe_name = get_safe_video_name(video_path)

    output_directory = os.path.join(
        RECOVERY_OUTPUT_DIR,
        safe_name
    )

    os.makedirs(output_directory, exist_ok=True)

    return output_directory


def get_video_path_from_command_line():
    """
    Reads the input video from the command line.
    """

    if len(sys.argv) < 2:
        print()
        print("ERROR: No input video was provided.")
        print()
        print("Usage:")
        print(
            'python -m recovery.sample_level_validator ".\\recovery\\test_data\\video.mp4"'
        )
        print()
        sys.exit(1)

    video_path = sys.argv[1]

    if not os.path.isfile(video_path):
        print()
        print("ERROR: Input video does not exist:")
        print(video_path)
        print()
        sys.exit(1)

    return os.path.abspath(video_path)


def get_sample_report_path(video_path):
    """
    Returns the sample recovery report belonging to this video.
    """

    video_directory = get_video_recovery_directory(video_path)

    return os.path.join(
        video_directory,
        "mp4_sample_recovery_scan.json"
    )


def get_validation_report_path(video_path):
    """
    Returns the validation report belonging to this video.
    """

    video_directory = get_video_recovery_directory(video_path)

    return os.path.join(
        video_directory,
        "sample_level_validation.json"
    )


# ============================================================
# TIME FORMATTING
# ============================================================

def format_timestamp(seconds):
    """
    Converts seconds into HH:MM:SS.mmm.
    """

    if seconds is None:
        return "UNKNOWN"

    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return "UNKNOWN"

    total_milliseconds = int(round(seconds * 1000))

    hours = total_milliseconds // 3600000

    remaining = total_milliseconds % 3600000

    minutes = remaining // 60000

    remaining %= 60000

    whole_seconds = remaining // 1000

    milliseconds = remaining % 1000

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{whole_seconds:02d}."
        f"{milliseconds:03d}"
    )


# ============================================================
# FFPROBE
# ============================================================

def run_ffprobe(video_path):
    """
    Runs FFprobe and returns basic video information.
    """

    if not os.path.isfile(FFPROBE):
        return {
            "available": False,
            "success": False,
            "error": "FFprobe executable not found."
        }

    command = [
        FFPROBE,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,r_frame_rate,nb_frames,duration",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        video_path
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if result.returncode != 0:

            return {
                "available": True,
                "success": False,
                "error": result.stderr.strip()
            }

        data = json.loads(result.stdout)

        return {
            "available": True,
            "success": True,
            "data": data
        }

    except Exception as error:

        return {
            "available": True,
            "success": False,
            "error": str(error)
        }


# ============================================================
# OPENCV DECODER
# ============================================================

def decode_source(video_path):
    """
    Decodes the source video using OpenCV.

    This is used as an independent decoder check.
    """

    capture = cv2.VideoCapture(video_path)

    if not capture.isOpened():

        return {
            "opened": False,
            "decoded_frames": 0,
            "fps": 0.0,
            "reported_frames": 0,
            "decoded_timestamps": [],
            "termination_events": 1
        }

    fps = capture.get(cv2.CAP_PROP_FPS)

    reported_frames = int(
        capture.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    if fps <= 0:
        fps = 0.0

    decoded_frames = 0

    decoded_timestamps = []

    termination_events = 0

    while True:

        success, frame = capture.read()

        if not success:

            termination_events += 1

            break

        decoded_frames += 1

        if fps > 0:

            timestamp = (
                (decoded_frames - 1)
                / fps
            )

            decoded_timestamps.append(timestamp)

    capture.release()

    return {
        "opened": True,
        "decoded_frames": decoded_frames,
        "fps": fps,
        "reported_frames": reported_frames,
        "decoded_timestamps": decoded_timestamps,
        "termination_events": termination_events
    }


# ============================================================
# FFMPEG RECOVERY-AWARE DECODER
# ============================================================

def decode_with_ffmpeg(video_path):
    """
    Uses FFmpeg with corruption-tolerant flags and showinfo
    to obtain timestamps for successfully decoded frames.
    """

    if not os.path.isfile(FFMPEG):

        return {
            "available": False,
            "decoded_frames": 0,
            "timestamps": [],
            "error": "FFmpeg executable not found."
        }

    command = [
        FFMPEG,
        "-hide_banner",
        "-loglevel",
        "info",
        "-err_detect",
        "ignore_err",
        "-fflags",
        "+discardcorrupt",
        "-i",
        video_path,
        "-map",
        "0:v:0",
        "-vf",
        "showinfo",
        "-an",
        "-f",
        "null",
        "-"
    ]

    try:

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        combined_output = (
            result.stdout +
            "\n" +
            result.stderr
        )

        timestamps = []

        pattern = re.compile(
            r"pts_time:([+-]?\d+(?:\.\d+)?)"
        )

        for match in pattern.finditer(combined_output):

            try:

                timestamp = float(
                    match.group(1)
                )

                timestamps.append(timestamp)

            except ValueError:

                continue

        return {
            "available": True,
            "decoded_frames": len(timestamps),
            "timestamps": timestamps,
            "return_code": result.returncode
        }

    except Exception as error:

        return {
            "available": True,
            "decoded_frames": 0,
            "timestamps": [],
            "error": str(error)
        }


# ============================================================
# SAMPLE REPORT
# ============================================================

def load_sample_report(report_path):
    """
    Loads the MP4 sample recovery scanner report.
    """

    if not os.path.isfile(report_path):

        print()
        print("ERROR: Sample recovery report not found:")
        print(report_path)
        print()

        sys.exit(1)

    try:

        with open(
            report_path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as error:

        print()
        print("ERROR: Could not read sample recovery report.")
        print(error)
        print()

        sys.exit(1)


# ============================================================
# PHYSICAL SAMPLE STATISTICS
# ============================================================

def extract_physical_sample_statistics(sample_report):
    """
    Determines physical sample availability directly from
    each sample's availability_status.

    The report also contains top-level counters. We compare
    both sources so that an incorrect field name cannot make
    the validator report zero physical samples.
    """

    samples = sample_report.get(
        "samples",
        []
    )

    fully_present_samples = []

    partially_present_samples = []

    missing_samples = []

    for sample in samples:

        status = str(
            sample.get(
                "availability_status",
                ""
            )
        ).upper()

        if status == "FULLY_PRESENT":

            fully_present_samples.append(sample)

        elif status == "PARTIALLY_PRESENT":

            partially_present_samples.append(sample)

        elif status == "MISSING":

            missing_samples.append(sample)

    calculated_fully_present = len(
        fully_present_samples
    )

    calculated_partially_present = len(
        partially_present_samples
    )

    calculated_missing = len(
        missing_samples
    )

    metadata_sample_count = sample_report.get(
        "metadata_sample_count",
        len(samples)
    )

    report_fully_present = sample_report.get(
        "fully_present_samples"
    )

    report_partially_present = sample_report.get(
        "partially_present_samples"
    )

    report_missing = sample_report.get(
        "missing_samples"
    )

    return {
        "metadata_sample_count": metadata_sample_count,

        "fully_present_samples": calculated_fully_present,

        "partially_present_samples": calculated_partially_present,

        "missing_samples": calculated_missing,

        "reported_fully_present_samples": report_fully_present,

        "reported_partially_present_samples": report_partially_present,

        "reported_missing_samples": report_missing,

        "fully_present_sample_objects": fully_present_samples,

        "partially_present_sample_objects": partially_present_samples,

        "missing_sample_objects": missing_samples
    }


# ============================================================
# TIMESTAMP → SAMPLE MATCHING
# ============================================================

def match_decoded_timestamps_to_samples(
    samples,
    decoded_timestamps
):
    """
    Matches successfully decoded frame timestamps to MP4
    samples.

    Rules:

    1. Only FULLY_PRESENT samples may be validated.
    2. Every decoded timestamp may validate at most one sample.
    3. Every sample may be validated at most once.
    4. Matching is based primarily on the sample timestamp.
    5. A strict tolerance prevents one decoded frame from
       accidentally validating multiple nearby samples.
    """

    usable_samples = []

    for sample in samples:

        status = str(
            sample.get(
                "availability_status",
                ""
            )
        ).upper()

        if status != "FULLY_PRESENT":
            continue

        try:

            sample_number = int(
                sample["sample_number"]
            )

            start_time = float(
                sample["start_timestamp_seconds"]
            )

            end_time = float(
                sample["end_timestamp_seconds"]
            )

        except (
            KeyError,
            TypeError,
            ValueError
        ):

            continue

        usable_samples.append(
            {
                "sample_number": sample_number,
                "start": start_time,
                "end": end_time
            }
        )

    usable_samples.sort(
        key=lambda item: item["sample_number"]
    )

    if not usable_samples:
        return []

    # Determine the normal sample duration.
    durations = []

    for sample in usable_samples:

        duration = (
            sample["end"]
            -
            sample["start"]
        )

        if duration > 0:

            durations.append(duration)

    if durations:

        durations.sort()

        middle = len(durations) // 2

        if len(durations) % 2 == 0:

            median_duration = (
                durations[middle - 1]
                +
                durations[middle]
            ) / 2.0

        else:

            median_duration = durations[middle]

    else:

        median_duration = 1.0 / 30.0

    # Strict timestamp tolerance.
    #
    # For this video the normal sample duration is about
    # 0.0333 seconds. A tolerance around 0.012 seconds is
    # enough for timestamp rounding without causing broad
    # overmatching.
    tolerance = min(
        0.012,
        median_duration * 0.40
    )

    if tolerance <= 0:

        tolerance = 0.005

    validated_sample_numbers = []

    used_samples = set()

    sample_index = 0

    for timestamp in decoded_timestamps:

        try:

            timestamp = float(timestamp)

        except (
            TypeError,
            ValueError
        ):

            continue

        # Move forward until the current sample is the one
        # containing or immediately preceding the timestamp.
        while (
            sample_index + 1
            <
            len(usable_samples)
            and
            usable_samples[
                sample_index + 1
            ]["start"]
            <= timestamp
        ):

            sample_index += 1

        candidate_indexes = [
            sample_index
        ]

        if (
            sample_index + 1
            <
            len(usable_samples)
        ):

            candidate_indexes.append(
                sample_index + 1
            )

        best_sample = None

        best_difference = None

        for candidate_index in candidate_indexes:

            candidate = usable_samples[
                candidate_index
            ]

            sample_number = candidate[
                "sample_number"
            ]

            if sample_number in used_samples:
                continue

            difference = abs(
                timestamp
                -
                candidate["start"]
            )

            # Normal case: timestamp falls inside the
            # sample interval.
            inside_interval = (
                candidate["start"]
                <= timestamp
                <
                candidate["end"]
            )

            # At a timestamp boundary, allow a very small
            # rounding difference.
            close_to_start = (
                difference
                <= tolerance
            )

            if not inside_interval and not close_to_start:
                continue

            if (
                best_sample is None
                or
                difference < best_difference
            ):

                best_sample = candidate

                best_difference = difference

        if best_sample is not None:

            sample_number = best_sample[
                "sample_number"
            ]

            used_samples.add(
                sample_number
            )

            validated_sample_numbers.append(
                sample_number
            )

    # Safety guarantee:
    #
    # We can never validate more samples than FFmpeg
    # successfully decoded timestamps.
    validated_sample_numbers = (
        validated_sample_numbers[
            :len(decoded_timestamps)
        ]
    )

    return validated_sample_numbers


# ============================================================
# GROUP CONSECUTIVE SAMPLE NUMBERS
# ============================================================

def group_consecutive_numbers(numbers):
    """
    Converts sample numbers into consecutive ranges.
    """

    if not numbers:
        return []

    sorted_numbers = sorted(
        set(numbers)
    )

    groups = []

    start = sorted_numbers[0]

    previous = sorted_numbers[0]

    for number in sorted_numbers[1:]:

        if number == previous + 1:

            previous = number

        else:

            groups.append(
                (
                    start,
                    previous
                )
            )

            start = number

            previous = number

    groups.append(
        (
            start,
            previous
        )
    )

    return groups


# ============================================================
# VALIDATED REGION CREATION
# ============================================================

def build_validated_regions(
    validated_sample_numbers,
    samples
):
    """
    Builds decoder-validated recovered regions while
    preserving gaps between regions.
    """

    sample_map = {}

    for sample in samples:

        try:

            sample_number = int(
                sample["sample_number"]
            )

            sample_map[
                sample_number
            ] = sample

        except (
            KeyError,
            TypeError,
            ValueError
        ):

            continue

    groups = group_consecutive_numbers(
        validated_sample_numbers
    )

    regions = []

    for index, (
        start_sample,
        end_sample
    ) in enumerate(
        groups,
        start=1
    ):

        first_sample = sample_map.get(
            start_sample
        )

        last_sample = sample_map.get(
            end_sample
        )

        if (
            first_sample is None
            or
            last_sample is None
        ):

            continue

        start_timestamp = float(
            first_sample[
                "start_timestamp_seconds"
            ]
        )

        end_timestamp = float(
            last_sample[
                "end_timestamp_seconds"
            ]
        )

        region = {
            "region_id": (
                f"VALIDATED-REGION-{index:03d}"
            ),

            "status": "RECOVERED",

            "start_sample": start_sample,

            "end_sample": end_sample,

            "sample_count": (
                end_sample
                -
                start_sample
                +
                1
            ),

            "start_timestamp": start_timestamp,

            "end_timestamp": end_timestamp,

            "start_timestamp_formatted": (
                format_timestamp(
                    start_timestamp
                )
            ),

            "end_timestamp_formatted": (
                format_timestamp(
                    end_timestamp
                )
            ),

            "synthetic_content_added": False
        }

        regions.append(region)

    return regions


# ============================================================
# MAIN VALIDATION
# ============================================================

def validate_video(video_path):
    """
    Complete sample-level forensic validation.
    """

    video_directory = (
        get_video_recovery_directory(
            video_path
        )
    )

    sample_report_path = (
        get_sample_report_path(
            video_path
        )
    )

    validation_report_path = (
        get_validation_report_path(
            video_path
        )
    )

    print()
    print("=" * 70)
    print("SAMPLE-LEVEL VIDEO VALIDATION")
    print("=" * 70)

    print()
    print("Video:")
    print(video_path)

    print()
    print("Video recovery directory:")
    print(video_directory)

    print()
    print("Sample report:")
    print(sample_report_path)

    # --------------------------------------------------------
    # LOAD SAMPLE REPORT
    # --------------------------------------------------------

    sample_report = load_sample_report(
        sample_report_path
    )

    samples = sample_report.get(
        "samples",
        []
    )

    if not samples:

        print()
        print(
            "ERROR: No sample records were found "
            "in the sample report."
        )

        sys.exit(1)

    print()
    print("Sample report loaded.")

    # --------------------------------------------------------
    # PHYSICAL SAMPLE STATISTICS
    # --------------------------------------------------------

    physical_stats = (
        extract_physical_sample_statistics(
            sample_report
        )
    )

    print()
    print("PHYSICAL SAMPLE AVAILABILITY")
    print("-" * 70)

    print(
        "Metadata samples:",
        physical_stats[
            "metadata_sample_count"
        ]
    )

    print(
        "Physically complete samples:",
        physical_stats[
            "fully_present_samples"
        ]
    )

    print(
        "Partially present samples:",
        physical_stats[
            "partially_present_samples"
        ]
    )

    print(
        "Missing samples:",
        physical_stats[
            "missing_samples"
        ]
    )

    # --------------------------------------------------------
    # OPENCV
    # --------------------------------------------------------

    print()
    print("OPENCV DECODER VALIDATION")
    print("-" * 70)

    opencv_result = decode_source(
        video_path
    )

    print(
        "Reported frames:",
        opencv_result[
            "reported_frames"
        ]
    )

    print(
        "Successfully decoded:",
        opencv_result[
            "decoded_frames"
        ]
    )

    print(
        "Decode termination events:",
        opencv_result[
            "termination_events"
        ]
    )

    print(
        "FPS:",
        opencv_result[
            "fps"
        ]
    )

    # --------------------------------------------------------
    # FFMPEG
    # --------------------------------------------------------

    print()
    print("FFMPEG RECOVERY-AWARE DECODER")
    print("-" * 70)

    print(
        "Attempting decoder continuation after damaged data..."
    )

    ffmpeg_result = decode_with_ffmpeg(
        video_path
    )

    ffmpeg_timestamps = (
        ffmpeg_result.get(
            "timestamps",
            []
        )
    )

    ffmpeg_decoded_frames = (
        ffmpeg_result.get(
            "decoded_frames",
            0
        )
    )

    print(
        "FFmpeg decoded frames:",
        ffmpeg_decoded_frames
    )

    print(
        "FFmpeg timestamp records:",
        len(ffmpeg_timestamps)
    )

    # --------------------------------------------------------
    # SELECT DECODER TIMESTAMPS
    # --------------------------------------------------------

    if ffmpeg_timestamps:

        decoded_timestamps = (
            ffmpeg_timestamps
        )

        decoder_method = (
            "FFMPEG_SHOWINFO"
        )

    elif opencv_result[
        "decoded_timestamps"
    ]:

        decoded_timestamps = (
            opencv_result[
                "decoded_timestamps"
            ]
        )

        decoder_method = (
            "OPENCV_FRAME_INDEX"
        )

    else:

        decoded_timestamps = []

        decoder_method = "NONE"

    # --------------------------------------------------------
    # MATCH DECODER TIMESTAMPS TO SAMPLES
    # --------------------------------------------------------

    validated_sample_numbers = (
        match_decoded_timestamps_to_samples(
            samples,
            decoded_timestamps
        )
    )

    # --------------------------------------------------------
    # SAFETY CHECK
    # --------------------------------------------------------

    if (
        len(validated_sample_numbers)
        >
        len(decoded_timestamps)
    ):

        print()
        print(
            "WARNING: Validator attempted to exceed "
            "decoder frame count."
        )

        validated_sample_numbers = (
            validated_sample_numbers[
                :len(decoded_timestamps)
            ]
        )

    # --------------------------------------------------------
    # BUILD REGIONS
    # --------------------------------------------------------

    validated_regions = (
        build_validated_regions(
            validated_sample_numbers,
            samples
        )
    )

    # --------------------------------------------------------
    # COMPARISON
    # --------------------------------------------------------

    print()
    print("SAMPLE VS DECODER COMPARISON")
    print("-" * 70)

    print(
        "Physically complete samples:",
        physical_stats[
            "fully_present_samples"
        ]
    )

    print(
        "OpenCV decoded frames:",
        opencv_result[
            "decoded_frames"
        ]
    )

    print(
        "FFmpeg decoded frames:",
        ffmpeg_decoded_frames
    )

    print(
        "Validated recovered samples:",
        len(validated_sample_numbers)
    )

    print(
        "Partially present samples:",
        physical_stats[
            "partially_present_samples"
        ]
    )

    print(
        "Missing samples:",
        physical_stats[
            "missing_samples"
        ]
    )

    # --------------------------------------------------------
    # VALIDATED SAMPLE NUMBERS
    # --------------------------------------------------------

    print()
    print("VALIDATED SAMPLE NUMBERS")
    print("-" * 70)

    print(
        "Count:",
        len(validated_sample_numbers)
    )

    if validated_sample_numbers:

        print(
            "First:",
            validated_sample_numbers[0]
        )

        print(
            "Last:",
            validated_sample_numbers[-1]
        )

        if len(validated_sample_numbers) > 20:

            print(
                "Sample range:",
                validated_sample_numbers[:10],
                "...",
                validated_sample_numbers[-10:]
            )

        else:

            print(
                "Sample numbers:",
                validated_sample_numbers
            )

    else:

        print("No samples were decoder validated.")

    # --------------------------------------------------------
    # VALIDATED REGIONS
    # --------------------------------------------------------

    print()
    print("VALIDATED RECOVERED REGIONS")
    print("-" * 70)

    if validated_regions:

        for region in validated_regions:

            print(
                region["region_id"],
                "|",
                region["start_timestamp_formatted"],
                "→",
                region["end_timestamp_formatted"]
            )

            print(
                "Samples",
                region["start_sample"],
                "→",
                region["end_sample"],
                "count",
                region["sample_count"]
            )

    else:

        print("No decoder-validated regions found.")

    # --------------------------------------------------------
    # FFPROBE CROSS CHECK
    # --------------------------------------------------------

    print()
    print("FFPROBE CROSS-CHECK")
    print("-" * 70)

    ffprobe_result = run_ffprobe(
        video_path
    )

    if ffprobe_result.get(
        "success",
        False
    ):

        print(
            "FFprobe validation: SUCCESS"
        )

    else:

        print(
            "FFprobe validation: FAILED"
        )

    # --------------------------------------------------------
    # RECOVERY STATUS
    # --------------------------------------------------------

    physically_present_count = (
        physical_stats[
            "fully_present_samples"
        ]
    )

    validated_count = (
        len(validated_sample_numbers)
    )

    metadata_count = (
        physical_stats[
            "metadata_sample_count"
        ]
    )

    if (
        validated_count > 0
        and
        validated_count >= metadata_count
    ):

        recovery_status = (
            "FULLY_RECOVERED"
        )

    elif validated_count > 0:

        recovery_status = (
            "PARTIALLY_RECOVERED"
        )

    else:

        recovery_status = (
            "NOT_RECOVERED"
        )

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    report = {

        "video_file": video_path,

        "video_filename": os.path.basename(
            video_path
        ),

        "video_name": get_safe_video_name(
            video_path
        ),

        "analysis_timestamp": (
            datetime.now().isoformat()
        ),

        "physical_sample_statistics": {

            "metadata_sample_count":
                metadata_count,

            "fully_present_samples":
                physically_present_count,

            "partially_present_samples":
                physical_stats[
                    "partially_present_samples"
                ],

            "missing_samples":
                physical_stats[
                    "missing_samples"
                ],

            "reported_fully_present_samples":
                physical_stats[
                    "reported_fully_present_samples"
                ],

            "reported_partially_present_samples":
                physical_stats[
                    "reported_partially_present_samples"
                ],

            "reported_missing_samples":
                physical_stats[
                    "reported_missing_samples"
                ]
        },

        "decoder_validation": {

            "opencv_decoded_frames":
                opencv_result[
                    "decoded_frames"
                ],

            "opencv_reported_frames":
                opencv_result[
                    "reported_frames"
                ],

            "opencv_fps":
                opencv_result[
                    "fps"
                ],

            "ffmpeg_decoded_frames":
                ffmpeg_decoded_frames,

            "ffmpeg_timestamp_records":
                len(ffmpeg_timestamps),

            "decoder_method_used":
                decoder_method,

            "validated_recovered_samples":
                validated_count,

            "validated_sample_count":
                validated_count
        },

        "validated_sample_numbers":
            validated_sample_numbers,

        "decoded_sample_numbers":
            validated_sample_numbers,

        "validated_recovered_samples": [
            {
                "sample_number": sample_number
            }
            for sample_number
            in validated_sample_numbers
        ],

        "validated_regions":
            validated_regions,

        "ffprobe_cross_check":
            ffprobe_result,

        "synthetic_frames_created": 0,

        "synthetic_content_added": False,

        "recovery_status":
            recovery_status,

        "forensic_note": (
            "Physical sample presence is determined "
            "from MP4 sample metadata and file boundaries. "
            "Physical presence does not prove successful "
            "decoding. A sample is considered decoder "
            "validated only when a successfully decoded "
            "frame timestamp can be matched to that sample. "
            "No synthetic frames or synthetic video content "
            "were created."
        )
    }

    # --------------------------------------------------------
    # SINGLE REGION COMPATIBILITY
    # --------------------------------------------------------

    if len(validated_regions) == 1:

        report[
            "validated_region"
        ] = validated_regions[0]

    # --------------------------------------------------------
    # SAVE REPORT
    # --------------------------------------------------------

    with open(
        validation_report_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=4
        )

    # --------------------------------------------------------
    # FINAL OUTPUT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SAMPLE-LEVEL VALIDATION COMPLETE")
    print("=" * 70)

    print()
    print("Report:")
    print(validation_report_path)

    print()
    print(
        "Synthetic frames created:",
        0
    )

    print(
        "Synthetic content added:",
        False
    )

    print()
    print(
        "Recovery status:",
        recovery_status
    )

    print()


# ============================================================
# MAIN
# ============================================================

def main():

    video_path = (
        get_video_path_from_command_line()
    )

    validate_video(
        video_path
    )


if __name__ == "__main__":

    main()