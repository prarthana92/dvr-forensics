import os
import json
import subprocess
from datetime import datetime

try:
    from .fragment_scanner import scan_for_video_signatures
    from .fragment_extractor import extract_fragment
    from .recovery_candidate import create_recovery_candidate
    from .candidate_hash import calculate_sha256
    from .video_integrity import get_video_info, run_ffprobe

except ImportError:
    from fragment_scanner import scan_for_video_signatures
    from fragment_extractor import extract_fragment
    from recovery_candidate import create_recovery_candidate
    from candidate_hash import calculate_sha256
    from video_integrity import get_video_info, run_ffprobe


# ============================================================
# FFMPEG CONFIGURATION
# ============================================================

FFMPEG_PATH = (
    r"C:\ffmpeg\ffmpeg-9.0.1-essentials_build"
    r"\bin\ffmpeg.exe"
)


# ============================================================
# FFMPEG VIDEO REPAIR
# ============================================================

def repair_video_with_ffmpeg(
    input_file,
    output_file
):
    """
    Attempt to create a new playable video from
    the frames that can still be decoded.
    """

    if not os.path.exists(input_file):
        return {
            "success": False,
            "error": "INPUT_FILE_NOT_FOUND"
        }

    if not os.path.exists(FFMPEG_PATH):
        return {
            "success": False,
            "error": "FFMPEG_NOT_FOUND"
        }

    output_folder = os.path.dirname(
        os.path.abspath(output_file)
    )

    os.makedirs(
        output_folder,
        exist_ok=True
    )

    command = [
        FFMPEG_PATH,
        "-y",
        "-err_detect",
        "ignore_err",
        "-i",
        input_file,
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        output_file
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True
        )

    except Exception as error:

        return {
            "success": False,
            "error": str(error)
        }

    if not os.path.exists(output_file):

        return {
            "success": False,
            "error": (
                result.stderr.strip()
                or "FFMPEG_OUTPUT_NOT_CREATED"
            )
        }

    return {
        "success": True,
        "return_code": result.returncode,
        "warnings": result.stderr.strip()
    }


# ============================================================
# VIDEO VALIDATION
# ============================================================

def validate_video(file_path):

    video_info = get_video_info(
        file_path
    )

    ffprobe_result = run_ffprobe(
        file_path
    )

    if video_info is None:

        return {
            "status": "DAMAGED_OR_UNREADABLE",
            "video_info": None,
            "ffprobe": ffprobe_result
        }

    if not ffprobe_result["success"]:

        return {
            "status": "DAMAGED_OR_UNREADABLE",
            "video_info": video_info,
            "ffprobe": ffprobe_result
        }

    return {
        "status": "READABLE",
        "video_info": video_info,
        "ffprobe": ffprobe_result
    }


# ============================================================
# MAIN RECOVERY WORKFLOW
# ============================================================

def run_recovery_workflow(
    source_file,
    output_folder,
    evidence_id
):

    if not os.path.exists(source_file):

        raise FileNotFoundError(
            f"Source file not found: {source_file}"
        )

    os.makedirs(
        output_folder,
        exist_ok=True
    )

    print("\n")
    print("=" * 60)
    print("              RECOVERY WORKFLOW")
    print("=" * 60)

    print("\nEvidence ID:")
    print(evidence_id)

    print("\nSource file:")
    print(source_file)


    # ========================================================
    # STEP 1 - SIGNATURE SCANNING
    # ========================================================

    print("\n[1/7] Scanning for video signatures...")

    signatures = scan_for_video_signatures(
        source_file
    )

    print(
        "Signatures found:",
        len(signatures)
    )

    if not signatures:

        print(
            "\nNo known video signatures were found."
        )

        return {
            "evidence_id": evidence_id,
            "source_file": source_file,
            "overall_status": "NO_RECOVERY_CANDIDATE",
            "signatures_found": 0,
            "candidates_found": 0,
            "recovered_candidates": 0,
            "candidates": [],
            "created_at": datetime.now().isoformat()
        }


    # ========================================================
    # CANDIDATE PROCESSING
    # ========================================================

    candidates = []


    for index, signature in enumerate(
        signatures,
        start=1
    ):

        print("\n")

        print(
            f"Processing candidate {index} "
            f"of {len(signatures)}"
        )

        print(
            "Type:",
            signature["file_type"]
        )

        print(
            "Position:",
            signature["position"]
        )


        # ====================================================
        # STEP 2 - EXTRACT FRAGMENT
        # ====================================================

        print("\n[2/7] Extracting fragment...")

        extension = ".mp4"

        if signature["file_type"] == "AVI":

            extension = ".avi"

        elif signature["file_type"] == "MKV/WebM":

            extension = ".mkv"


        candidate_file = os.path.join(
            output_folder,
            f"{evidence_id}_recovery_candidate_"
            f"{index}{extension}"
        )


        bytes_extracted = extract_fragment(
            source_file,
            candidate_file,
            signature["position"]
        )


        print(
            "Bytes extracted:",
            bytes_extracted
        )


        # ====================================================
        # STEP 3 - VALIDATE EXTRACTED FRAGMENT
        # ====================================================

        print(
            "\n[3/7] Validating extracted candidate..."
        )

        validation = validate_video(
            candidate_file
        )

        validation_status = validation[
            "status"
        ]


        print(
            "Validation:",
            validation_status
        )


        if validation["video_info"] is not None:

            print(
                "Reported frames:",
                validation["video_info"]["frame_count"]
            )


        # ====================================================
        # STEP 4 - CREATE RECOVERY CANDIDATE
        # ====================================================

        print(
            "\n[4/7] Creating recovery candidate..."
        )


        candidate = create_recovery_candidate(
            source_file,
            signature["file_type"],
            signature["signature"],
            signature["position"],
            candidate_file,
            validation_status,
            evidence_id
        )


        print(
            "Candidate ID:",
            candidate["candidate_id"]
        )


        # ====================================================
        # STEP 5 - SHA-256
        # ====================================================

        print(
            "\n[5/7] Calculating candidate SHA-256..."
        )


        candidate_sha256 = calculate_sha256(
            candidate_file
        )


        candidate["candidate_sha256"] = (
            candidate_sha256
        )


        print(
            "SHA-256:",
            candidate_sha256
        )


        # ====================================================
        # STEP 6 - FFMPEG REPAIR
        # ====================================================

        print(
            "\n[6/7] Attempting FFmpeg repair..."
        )


        repaired_file = os.path.join(
            output_folder,
            f"{candidate['candidate_id']}"
            f"_repaired.mp4"
        )


        # IMPORTANT:
        #
        # Repair the ORIGINAL DAMAGED FILE.
        #
        # Do NOT modify the original evidence.
        #
        # The original damaged MP4 still contains
        # enough container information for FFmpeg
        # to salvage the readable frames.

        repair_result = repair_video_with_ffmpeg(
            source_file,
            repaired_file
        )


        candidate["repair_attempted"] = True

        candidate["repair_input"] = source_file

        candidate["repair_output"] = repaired_file

        candidate["repair_success"] = (
            repair_result["success"]
        )


        if repair_result["success"]:

            print(
                "✓ FFmpeg repair output created."
            )

            print(
                "Repaired file:",
                repaired_file
            )


            repaired_validation = validate_video(
                repaired_file
            )


            candidate[
                "repaired_validation_status"
            ] = repaired_validation[
                "status"
            ]


            candidate[
                "repaired_video_info"
            ] = repaired_validation[
                "video_info"
            ]


            candidate[
                "repaired_ffprobe"
            ] = repaired_validation[
                "ffprobe"
            ]


            if (
                repaired_validation["status"]
                == "READABLE"
            ):

                candidate[
                    "final_recovery_status"
                ] = "RECOVERED"


                print(
                    "✓ Repaired video is readable."
                )


                if (
                    repaired_validation[
                        "video_info"
                    ] is not None
                ):

                    print(
                        "Recovered frames:",
                        repaired_validation[
                            "video_info"
                        ]["frame_count"]
                    )

            else:

                candidate[
                    "final_recovery_status"
                ] = "NOT_RECOVERED"


                print(
                    "✗ Repaired video could not be validated."
                )

        else:

            candidate[
                "final_recovery_status"
            ] = "NOT_RECOVERED"


            candidate[
                "repair_error"
            ] = repair_result["error"]


            print(
                "✗ FFmpeg repair failed."
            )

            print(
                "Reason:",
                repair_result["error"]
            )


        # ====================================================
        # STEP 7 - SAVE CANDIDATE REPORT
        # ====================================================

        print(
            "\n[7/7] Saving recovery candidate report..."
        )


        candidate_report_path = os.path.join(
            output_folder,
            f"{candidate['candidate_id']}.json"
        )


        candidate[
            "candidate_report"
        ] = candidate_report_path


        with open(
            candidate_report_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                candidate,
                file,
                indent=4
            )


        candidates.append(
            candidate
        )


        print(
            "Report:",
            candidate_report_path
        )


    # ========================================================
    # FINAL RECOVERY STATUS
    # ========================================================

    recovered_count = 0


    for candidate in candidates:

        if candidate.get(
            "final_recovery_status"
        ) == "RECOVERED":

            recovered_count += 1


    if recovered_count > 0:

        overall_status = (
            "RECOVERY_SUCCESSFUL"
        )

    else:

        overall_status = (
            "RECOVERY_ATTEMPTED"
        )


    # ========================================================
    # FINAL RECOVERY REPORT
    # ========================================================

    recovery_report = {

        "evidence_id": evidence_id,

        "source_file": source_file,

        "signatures_found": len(signatures),

        "candidates_found": len(candidates),

        "recovered_candidates": recovered_count,

        # IMPORTANT:
        # This is the standardized field consumed
        # by forensic_pipeline.py.
        "overall_status": overall_status,

        "candidates": candidates,

        "created_at": datetime.now().isoformat()
    }


    recovery_report_path = os.path.join(
        output_folder,
        f"{evidence_id}_recovery_report.json"
    )


    with open(
        recovery_report_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            recovery_report,
            file,
            indent=4
        )


    # ========================================================
    # FINAL CONSOLE OUTPUT
    # ========================================================

    print("\n")

    print("=" * 60)

    print(
        "           RECOVERY WORKFLOW COMPLETE"
    )

    print("=" * 60)


    print(
        "\nCandidates found:",
        len(candidates)
    )


    print(
        "Successfully recovered:",
        recovered_count
    )


    print(
        "Overall status:",
        overall_status
    )


    print(
        "Recovery report:",
        recovery_report_path
    )


    # IMPORTANT:
    # Return the SAME field name used by
    # forensic_pipeline.py.
    return recovery_report


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    backend_folder = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )


    source_file = os.path.join(
        backend_folder,
        "recovery",
        "test_data",
        "damaged_test.mp4"
    )


    output_folder = os.path.join(
        backend_folder,
        "output",
        "recovery"
    )


    evidence_id = "EVD-TEST-RECOVERY"


    try:

        run_recovery_workflow(
            source_file,
            output_folder,
            evidence_id
        )

    except Exception as error:

        print(
            "\nError:",
            error
        )