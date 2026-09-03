import os
import sys
import json
from datetime import datetime


# ============================================================
# FORENSIC ORIGINAL TIMELINE RECONSTRUCTOR
# ============================================================
#
# Purpose:
#
#   Reconstruct the ORIGINAL forensic timeline from:
#
#       1. MP4 sample metadata
#       2. Sample-level decoder validation
#
# The timeline preserves the ORIGINAL sample numbers,
# timestamps, byte ranges, and gaps.
#
# Possible forensic states:
#
#   RECOVERED
#   NOT_DECODE_VALIDATED
#   PARTIAL_NOT_RECOVERED
#   MISSING
#
# IMPORTANT:
#
#   This module does NOT create video frames.
#   This module does NOT fabricate missing footage.
#   This module does NOT compress the original timeline.
#
#   The timeline JSON is the authoritative forensic record.
# ============================================================


# ============================================================
# PATH CONFIGURATION
# ============================================================

BACKEND_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

RECOVERY_OUTPUT_DIR = os.path.join(
    BACKEND_DIR,
    "output",
    "recovery"
)


# ============================================================
# SAFE VIDEO DIRECTORY NAME
# ============================================================

def get_safe_video_name(video_path):

    video_name = os.path.splitext(
        os.path.basename(video_path)
    )[0]

    safe_name = ""

    for character in video_name:

        if character.isalnum() or character in (
            "-",
            "_"
        ):

            safe_name += character

        else:

            safe_name += "_"

    return safe_name


# ============================================================
# VIDEO RECOVERY DIRECTORY
# ============================================================

def get_video_recovery_directory(video_path):

    safe_video_name = get_safe_video_name(
        video_path
    )

    return os.path.join(
        RECOVERY_OUTPUT_DIR,
        safe_video_name
    )


# ============================================================
# COMMAND-LINE VIDEO INPUT
# ============================================================

def get_video_path_from_command_line():

    if len(sys.argv) < 2:

        raise ValueError(
            "No input video was provided.\n\n"
            "Usage:\n"
            'python -m recovery.timeline_reconstructor ".\\recovery\\test_data\\video.mp4"'
        )

    video_path = os.path.abspath(
        sys.argv[1]
    )

    if not os.path.exists(video_path):

        raise FileNotFoundError(
            f"Input video not found: {video_path}"
        )

    return video_path


# ============================================================
# REPORT PATHS
# ============================================================

def get_sample_report_path(video_path):

    video_directory = (
        get_video_recovery_directory(
            video_path
        )
    )

    return os.path.join(
        video_directory,
        "mp4_sample_recovery_scan.json"
    )


def get_validation_report_path(video_path):

    video_directory = (
        get_video_recovery_directory(
            video_path
        )
    )

    return os.path.join(
        video_directory,
        "sample_level_validation.json"
    )


def get_timeline_report_path(video_path):

    video_directory = (
        get_video_recovery_directory(
            video_path
        )
    )

    return os.path.join(
        video_directory,
        "original_timeline_mapping.json"
    )


# ============================================================
# TIMESTAMP FORMATTER
# ============================================================

def format_timestamp(seconds):

    if seconds is None:

        return None

    try:

        seconds = float(
            seconds
        )

    except (
        TypeError,
        ValueError
    ):

        return None

    hours = int(
        seconds // 3600
    )

    minutes = int(
        (seconds % 3600) // 60
    )

    remaining = (
        seconds % 60
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{remaining:06.3f}"
    )


# ============================================================
# LOAD JSON
# ============================================================

def load_json(file_path):

    if not os.path.exists(
        file_path
    ):

        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(
            file
        )


# ============================================================
# DETERMINE ORIGINAL DURATION
# ============================================================

def determine_original_duration(
    sample_report,
    samples
):

    # --------------------------------------------------------
    # Preferred source:
    #
    # End timestamp of the final MP4 sample.
    # --------------------------------------------------------

    if samples:

        last_sample = samples[-1]

        end_timestamp = (
            last_sample.get(
                "end_timestamp_seconds"
            )
        )

        if end_timestamp is not None:

            try:

                return float(
                    end_timestamp
                )

            except (
                TypeError,
                ValueError
            ):

                pass

    # --------------------------------------------------------
    # Fallback:
    #
    # duration_seconds from the sample report.
    # --------------------------------------------------------

    metadata_duration = (
        sample_report.get(
            "duration_seconds"
        )
    )

    if metadata_duration is not None:

        try:

            return float(
                metadata_duration
            )

        except (
            TypeError,
            ValueError
        ):

            pass

    return None


# ============================================================
# EXTRACT EXACT VALIDATED SAMPLE NUMBERS
# ============================================================

def extract_validated_sample_numbers(
    validation_report
):

    validated_samples = set()

    # --------------------------------------------------------
    # PRIMARY SOURCE
    #
    # New sample-level validator explicitly stores:
    #
    #   validated_sample_numbers
    #
    # This is the authoritative source.
    # --------------------------------------------------------

    numbers = validation_report.get(
        "validated_sample_numbers",
        []
    )

    for number in numbers:

        try:

            validated_samples.add(
                int(number)
            )

        except (
            TypeError,
            ValueError
        ):

            continue

    # --------------------------------------------------------
    # SECONDARY SOURCE
    #
    # Some versions may store:
    #
    #   decoded_sample_numbers
    #
    # Use it only to supplement the exact list.
    # --------------------------------------------------------

    numbers = validation_report.get(
        "decoded_sample_numbers",
        []
    )

    for number in numbers:

        try:

            validated_samples.add(
                int(number)
            )

        except (
            TypeError,
            ValueError
        ):

            continue

    return validated_samples


# ============================================================
# DETERMINE SAMPLE FORENSIC STATUS
# ============================================================

def determine_sample_status(
    sample,
    validated_samples
):

    availability = sample.get(
        "availability_status",
        "UNKNOWN"
    )

    sample_number = sample.get(
        "sample_number"
    )

    try:

        sample_number = int(
            sample_number
        )

    except (
        TypeError,
        ValueError
    ):

        return "UNKNOWN"

    # --------------------------------------------------------
    # FULLY PRESENT + DECODER VALIDATED
    #
    # This is the only condition for RECOVERED.
    # --------------------------------------------------------

    if availability == "FULLY_PRESENT":

        if sample_number in validated_samples:

            return "RECOVERED"

        return "NOT_DECODE_VALIDATED"

    # --------------------------------------------------------
    # PHYSICALLY PARTIAL
    # --------------------------------------------------------

    if availability == "PARTIALLY_PRESENT":

        return "PARTIAL_NOT_RECOVERED"

    # --------------------------------------------------------
    # PHYSICALLY MISSING
    # --------------------------------------------------------

    if availability == "MISSING":

        return "MISSING"

    return "UNKNOWN"


# ============================================================
# CREATE TIMELINE REGION
# ============================================================

def create_region(
    samples,
    status,
    region_number
):

    if not samples:

        return None

    first = samples[0]

    last = samples[-1]

    start_timestamp = (
        first.get(
            "start_timestamp_seconds"
        )
    )

    end_timestamp = (
        last.get(
            "end_timestamp_seconds"
        )
    )

    start_sample = (
        first.get(
            "sample_number"
        )
    )

    end_sample = (
        last.get(
            "sample_number"
        )
    )

    available_bytes = 0
    expected_bytes = 0

    for sample in samples:

        try:

            available_bytes += int(
                sample.get(
                    "available_bytes",
                    0
                )
            )

        except (
            TypeError,
            ValueError
        ):

            pass

        try:

            expected_bytes += int(
                sample.get(
                    "sample_size",
                    0
                )
            )

        except (
            TypeError,
            ValueError
        ):

            pass

    return {

        "region_id":
            f"TIMELINE-REGION-{region_number:03d}",

        "status":
            status,

        "start_sample":
            start_sample,

        "end_sample":
            end_sample,

        "sample_count":
            len(samples),

        "start_timestamp_seconds":
            start_timestamp,

        "end_timestamp_seconds":
            end_timestamp,

        "start_timestamp":
            format_timestamp(
                start_timestamp
            ),

        "end_timestamp":
            format_timestamp(
                end_timestamp
            ),

        "byte_start":
            first.get(
                "byte_start"
            ),

        "byte_end":
            last.get(
                "byte_end"
            ),

        "available_bytes":
            available_bytes,

        "expected_bytes":
            expected_bytes,

        "synthetic_frames_created":
            0,

        "synthetic_content_added":
            False
    }


# ============================================================
# BUILD ORIGINAL FORENSIC TIMELINE
# ============================================================

def build_original_timeline(
    sample_report_file,
    validation_report_file
):

    sample_report = load_json(
        sample_report_file
    )

    validation_report = load_json(
        validation_report_file
    )

    samples = sample_report.get(
        "samples",
        []
    )

    if not samples:

        raise RuntimeError(
            "Sample report does not contain "
            "individual MP4 sample information."
        )

    # --------------------------------------------------------
    # Sort samples by original sample number.
    #
    # This guarantees that the timeline follows the original
    # MP4 order.
    # --------------------------------------------------------

    samples = sorted(
        samples,
        key=lambda sample: int(
            sample.get(
                "sample_number",
                0
            )
        )
    )

    # --------------------------------------------------------
    # Extract EXACT decoder-validated samples.
    #
    # No sequential reconstruction from a count.
    # No assumption that samples 1..N are recovered.
    # --------------------------------------------------------

    validated_samples = (
        extract_validated_sample_numbers(
            validation_report
        )
    )

    # --------------------------------------------------------
    # Physical sample statistics.
    #
    # Prefer the actual individual sample statuses because
    # they are the source of truth for classification.
    # --------------------------------------------------------

    fully_present = 0
    partially_present = 0
    missing = 0
    unknown = 0

    for sample in samples:

        availability = sample.get(
            "availability_status",
            "UNKNOWN"
        )

        if availability == "FULLY_PRESENT":

            fully_present += 1

        elif availability == "PARTIALLY_PRESENT":

            partially_present += 1

        elif availability == "MISSING":

            missing += 1

        else:

            unknown += 1

    # --------------------------------------------------------
    # Build per-sample forensic classification.
    # --------------------------------------------------------

    classified_samples = []

    for sample in samples:

        classified_sample = dict(
            sample
        )

        status = determine_sample_status(
            sample,
            validated_samples
        )

        classified_sample[
            "forensic_status"
        ] = status

        classified_samples.append(
            classified_sample
        )

    # --------------------------------------------------------
    # Group consecutive samples with identical status.
    #
    # This preserves gaps in the original timeline.
    # --------------------------------------------------------

    regions = []

    current_samples = []

    current_status = None

    for sample in classified_samples:

        status = sample.get(
            "forensic_status",
            "UNKNOWN"
        )

        if current_status is None:

            current_status = status

            current_samples = [
                sample
            ]

            continue

        if status == current_status:

            current_samples.append(
                sample
            )

            continue

        # ----------------------------------------------------
        # Status changed.
        # Close the previous region.
        # ----------------------------------------------------

        region = create_region(
            current_samples,
            current_status,
            len(regions) + 1
        )

        if region is not None:

            regions.append(
                region
            )

        current_status = status

        current_samples = [
            sample
        ]

    # --------------------------------------------------------
    # Close final region.
    # --------------------------------------------------------

    if current_samples:

        region = create_region(
            current_samples,
            current_status,
            len(regions) + 1
        )

        if region is not None:

            regions.append(
                region
            )

    # --------------------------------------------------------
    # Original duration.
    # --------------------------------------------------------

    original_duration = (
        determine_original_duration(
            sample_report,
            samples
        )
    )

    # --------------------------------------------------------
    # Statistics based on actual classification.
    # --------------------------------------------------------

    recovered_samples = sum(
        1
        for sample in classified_samples
        if sample.get(
            "forensic_status"
        ) == "RECOVERED"
    )

    not_validated_samples = sum(
        1
        for sample in classified_samples
        if sample.get(
            "forensic_status"
        ) == "NOT_DECODE_VALIDATED"
    )

    partial_samples = sum(
        1
        for sample in classified_samples
        if sample.get(
            "forensic_status"
        ) == "PARTIAL_NOT_RECOVERED"
    )

    missing_samples = sum(
        1
        for sample in classified_samples
        if sample.get(
            "forensic_status"
        ) == "MISSING"
    )

    unknown_samples = sum(
        1
        for sample in classified_samples
        if sample.get(
            "forensic_status"
        ) == "UNKNOWN"
    )

    # --------------------------------------------------------
    # Validate consistency.
    #
    # A timeline can never claim more recovered samples than
    # the validator actually supplied.
    # --------------------------------------------------------

    recovered_count_matches_validation = (
        recovered_samples
        == len(validated_samples)
    )

    # --------------------------------------------------------
    # Build final forensic report.
    # --------------------------------------------------------

    result = {

        "status":
            "TIMELINE_RECONSTRUCTED",

        "analysis_timestamp":
            datetime.now().isoformat(),

        "sample_report":
            os.path.abspath(
                sample_report_file
            ),

        "validation_report":
            os.path.abspath(
                validation_report_file
            ),

        "original_sample_count":
            len(samples),

        "original_duration_seconds":
            original_duration,

        "original_duration":
            format_timestamp(
                original_duration
            ),

        "physical_sample_statistics": {

            "metadata_sample_count":
                len(samples),

            "fully_present_samples":
                fully_present,

            "partially_present_samples":
                partially_present,

            "missing_samples":
                missing,

            "unknown_samples":
                unknown
        },

        "decoder_validation_statistics": {

            "validated_sample_count":
                len(validated_samples),

            "recovered_sample_count":
                recovered_samples,

            "not_decode_validated_samples":
                not_validated_samples,

            "partial_not_recovered_samples":
                partial_samples,

            "missing_samples":
                missing_samples,

            "unknown_samples":
                unknown_samples,

            "recovered_count_matches_validation":
                recovered_count_matches_validation
        },

        "regions":
            regions,

        "classified_samples":
            classified_samples,

        "timeline_preserved":
            True,

        "synthetic_frames_created":
            0,

        "synthetic_content_added":
            False,

        "forensic_note":
            (
                "The original MP4 forensic timeline is "
                "preserved using the original sample numbers "
                "and timestamps stored in the MP4 metadata. "
                "A sample is classified as RECOVERED only "
                "when it is physically fully present and its "
                "sample number is explicitly supported by "
                "decoder validation. Physically present "
                "samples that were not decoder validated are "
                "classified as NOT_DECODE_VALIDATED and are "
                "not treated as recovered. Partial and "
                "missing samples are not treated as recovered. "
                "No synthetic frames, fabricated footage, or "
                "invented timestamps were created."
            )
    }

    return result


# ============================================================
# SAVE TIMELINE
# ============================================================

def save_timeline(
    timeline,
    output_file
):

    folder = os.path.dirname(
        os.path.abspath(
            output_file
        )
    )

    os.makedirs(
        folder,
        exist_ok=True
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            timeline,
            file,
            indent=4
        )


# ============================================================
# PRINT TIMELINE
# ============================================================

def print_timeline(
    timeline
):

    print()
    print("=" * 70)
    print(
        "             ORIGINAL FORENSIC TIMELINE"
    )
    print("=" * 70)

    print()

    print(
        "Original samples:",
        timeline.get(
            "original_sample_count",
            0
        )
    )

    print(
        "Original duration:",
        timeline.get(
            "original_duration",
            "UNKNOWN"
        )
    )

    print()

    physical_stats = (
        timeline.get(
            "physical_sample_statistics",
            {}
        )
    )

    decoder_stats = (
        timeline.get(
            "decoder_validation_statistics",
            {}
        )
    )

    print(
        "Physically complete samples:",
        physical_stats.get(
            "fully_present_samples",
            0
        )
    )

    print(
        "Partially present samples:",
        physical_stats.get(
            "partially_present_samples",
            0
        )
    )

    print(
        "Missing samples:",
        physical_stats.get(
            "missing_samples",
            0
        )
    )

    print(
        "Decoder-validated samples:",
        decoder_stats.get(
            "validated_sample_count",
            0
        )
    )

    print()

    print(
        "TIMELINE REGIONS"
    )

    print("-" * 70)

    for region in timeline.get(
        "regions",
        []
    ):

        print(
            region.get(
                "region_id"
            ),
            "|",
            region.get(
                "status"
            )
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
            "Time:",
            region.get(
                "start_timestamp"
            ),
            "→",
            region.get(
                "end_timestamp"
            )
        )

        print(
            "Samples in region:",
            region.get(
                "sample_count"
            )
        )

        print()

    print(
        "Recovered samples:",
        decoder_stats.get(
            "recovered_sample_count",
            0
        )
    )

    print(
        "Not decoder validated:",
        decoder_stats.get(
            "not_decode_validated_samples",
            0
        )
    )

    print(
        "Partial samples:",
        decoder_stats.get(
            "partial_not_recovered_samples",
            0
        )
    )

    print(
        "Missing samples:",
        decoder_stats.get(
            "missing_samples",
            0
        )
    )

    print(
        "Timeline preserved:",
        timeline.get(
            "timeline_preserved",
            False
        )
    )

    print(
        "Synthetic content added:",
        timeline.get(
            "synthetic_content_added",
            False
        )
    )

    print("=" * 70)


# ============================================================
# STANDALONE TEST
# ============================================================

def main():

    try:

        # ----------------------------------------------------
        # Get dynamic input video.
        # ----------------------------------------------------

        video_path = (
            get_video_path_from_command_line()
        )

        # ----------------------------------------------------
        # Determine all report paths dynamically.
        # ----------------------------------------------------

        sample_report = (
            get_sample_report_path(
                video_path
            )
        )

        validation_report = (
            get_validation_report_path(
                video_path
            )
        )

        timeline_report = (
            get_timeline_report_path(
                video_path
            )
        )

        # ----------------------------------------------------
        # Display input information.
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print(
            "FORENSIC TIMELINE RECONSTRUCTOR"
        )
        print("=" * 70)

        print()

        print(
            "Input video:"
        )

        print(
            video_path
        )

        print()

        print(
            "Sample report:"
        )

        print(
            sample_report
        )

        print()

        print(
            "Validation report:"
        )

        print(
            validation_report
        )

        print()

        print(
            "Timeline output:"
        )

        print(
            timeline_report
        )

        # ----------------------------------------------------
        # Verify reports exist.
        # ----------------------------------------------------

        if not os.path.exists(
            sample_report
        ):

            raise FileNotFoundError(
                "Sample recovery report not found:\n"
                f"{sample_report}\n\n"
                "Run the MP4 sample recovery scanner first."
            )

        if not os.path.exists(
            validation_report
        ):

            raise FileNotFoundError(
                "Sample validation report not found:\n"
                f"{validation_report}\n\n"
                "Run the sample-level validator first."
            )

        print()

        print(
            "Reports loaded successfully."
        )

        # ----------------------------------------------------
        # Build timeline.
        # ----------------------------------------------------

        timeline = (
            build_original_timeline(
                sample_report,
                validation_report
            )
        )

        # ----------------------------------------------------
        # Save timeline.
        # ----------------------------------------------------

        save_timeline(
            timeline,
            timeline_report
        )

        # ----------------------------------------------------
        # Print result.
        # ----------------------------------------------------

        print_timeline(
            timeline
        )

        print()

        print(
            "Timeline report:"
        )

        print(
            timeline_report
        )

        print()

        print("=" * 70)

        print(
            "        TIMELINE RECONSTRUCTION COMPLETE"
        )

        print("=" * 70)

    except Exception as error:

        print()

        print(
            "ERROR:"
        )

        print(
            str(error)
        )

        print()

        print("=" * 70)


if __name__ == "__main__":

    main()