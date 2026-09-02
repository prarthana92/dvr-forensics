from pathlib import Path
import json
from datetime import datetime


# ============================================================
# PATHS
# ============================================================

BACKEND_FOLDER = Path(__file__).resolve().parent.parent

PIPELINE_FOLDER = (
    BACKEND_FOLDER
    / "output"
    / "pipeline_results"
)

CUSTODY_FOLDER = (
    BACKEND_FOLDER
    / "output"
    / "custody"
)

REPORT_FOLDER = (
    BACKEND_FOLDER
    / "reports"
)


# ============================================================
# CREATE REPORT FOLDER
# ============================================================

REPORT_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# FIND LATEST PIPELINE RESULT
# ============================================================

def find_latest_pipeline():

    pipeline_files = sorted(
        PIPELINE_FOLDER.glob(
            "*_pipeline.json"
        ),
        key=lambda file: file.stat().st_mtime,
        reverse=True
    )

    if not pipeline_files:

        raise FileNotFoundError(
            "No pipeline result found."
        )

    return pipeline_files[0]


# ============================================================
# LOAD JSON
# ============================================================

def load_json(file_path):

    if not file_path.exists():

        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ============================================================
# LOAD CHAIN OF CUSTODY
# ============================================================

def load_custody(evidence_id):

    custody_file = (
        CUSTODY_FOLDER
        / f"{evidence_id}_custody.json"
    )

    if not custody_file.exists():

        return None

    try:

        return load_json(
            custody_file
        )

    except Exception:

        return None


# ============================================================
# GENERATE TEXT REPORT
# ============================================================

def generate_report(
    pipeline_data,
    pipeline_file
):

    evidence = pipeline_data.get(
        "evidence",
        {}
    )

    forensic_copy = pipeline_data.get(
        "forensic_copy",
        {}
    )

    metadata = pipeline_data.get(
        "metadata",
        {}
    )

    frames = pipeline_data.get(
        "frames",
        {}
    )

    ai_analysis = pipeline_data.get(
        "ai_analysis",
        {}
    )

    evidence_id = evidence.get(
        "evidence_id",
        "UNKNOWN"
    )

    # --------------------------------------------------------
    # LOAD CUSTODY
    # --------------------------------------------------------

    custody_data = load_custody(
        evidence_id
    )

    # --------------------------------------------------------
    # REPORT FILE
    # --------------------------------------------------------

    report_file = (
        REPORT_FOLDER
        / f"{evidence_id}_forensic_report.txt"
    )

    # --------------------------------------------------------
    # BUILD REPORT
    # --------------------------------------------------------

    lines = []

    lines.append(
        "=" * 70
    )

    lines.append(
        "                 DVR FORENSIC ANALYSIS REPORT"
    )

    lines.append(
        "=" * 70
    )

    lines.append("")

    # ========================================================
    # CASE / EVIDENCE INFORMATION
    # ========================================================

    lines.append(
        "CASE / EVIDENCE INFORMATION"
    )

    lines.append(
        "-" * 70
    )

    lines.append(
        f"Evidence ID       : {evidence.get('evidence_id', 'N/A')}"
    )

    lines.append(
        f"File Name         : {evidence.get('file_name', 'N/A')}"
    )

    lines.append(
        f"File Size         : {evidence.get('file_size_bytes', 'N/A')} bytes"
    )

    lines.append(
        f"File Type         : {evidence.get('file_extension', 'N/A')}"
    )

    lines.append(
        f"Evidence Category : {evidence.get('evidence_type', 'N/A')}"
    )

    lines.append(
        f"Acquisition Time  : {evidence.get('acquisition_time', 'N/A')}"
    )

    lines.append(
        f"Modified Time     : {evidence.get('modification_time', 'N/A')}"
    )

    lines.append("")

    # ========================================================
    # HASH INFORMATION
    # ========================================================

    lines.append(
        "EVIDENCE HASHES"
    )

    lines.append(
        "-" * 70
    )

    lines.append(
        f"MD5               : {evidence.get('md5', 'N/A')}"
    )

    lines.append(
        f"SHA-256           : {evidence.get('sha256', 'N/A')}"
    )

    lines.append("")

    # ========================================================
    # INTEGRITY VERIFICATION
    # ========================================================

    lines.append(
        "INTEGRITY VERIFICATION"
    )

    lines.append(
        "-" * 70
    )

    lines.append(
        f"Original SHA-256  : {forensic_copy.get('original_sha256', 'N/A')}"
    )

    lines.append(
        f"Copy SHA-256      : {forensic_copy.get('copy_sha256', 'N/A')}"
    )

    lines.append(
        f"Hash Match        : {forensic_copy.get('hash_match', 'N/A')}"
    )

    lines.append(
        f"Integrity Status  : {forensic_copy.get('status', 'N/A')}"
    )

    lines.append(
        f"Verified At       : {forensic_copy.get('verified_at', 'N/A')}"
    )

    lines.append("")

    # ========================================================
    # FORENSIC COPY
    # ========================================================

    lines.append(
        "FORENSIC COPY"
    )

    lines.append(
        "-" * 70
    )

    lines.append(
        f"Copy Path         : {forensic_copy.get('path', 'N/A')}"
    )

    lines.append(
        f"Verification File : {forensic_copy.get('verification_report', 'N/A')}"
    )

    lines.append("")

    # ========================================================
    # VIDEO METADATA
    # ========================================================

    lines.append(
        "VIDEO METADATA"
    )

    lines.append(
        "-" * 70
    )

    lines.append(
        f"File              : {metadata.get('file', 'N/A')}"
    )

    lines.append(
        f"Format            : {metadata.get('format', 'N/A')}"
    )

    lines.append(
        f"Size              : {metadata.get('size_bytes', 'N/A')} bytes"
    )

    lines.append(
        f"Duration          : {metadata.get('duration_seconds', 'N/A')} seconds"
    )

    lines.append(
        f"Resolution        : {metadata.get('width', 'N/A')} x {metadata.get('height', 'N/A')}"
    )

    lines.append(
        f"Video Codec       : {metadata.get('video_codec', 'N/A')}"
    )

    lines.append(
        f"Frame Rate        : {metadata.get('frame_rate', 'N/A')}"
    )

    lines.append("")

    # ========================================================
    # FRAME EXTRACTION
    # ========================================================

    lines.append(
        "FRAME EXTRACTION"
    )

    lines.append(
        "-" * 70
    )

    lines.append(
        f"Frames Extracted  : {frames.get('count', 0)}"
    )

    lines.append(
        f"Frames Folder     : {frames.get('folder', 'N/A')}"
    )

    lines.append(
        f"Frame Index       : {frames.get('frame_index', 'N/A')}"
    )

    lines.append("")

    # ========================================================
    # AI ANALYSIS
    # ========================================================

    lines.append(
        "AI ANALYSIS"
    )

    lines.append(
        "-" * 70
    )

    lines.append(
        f"AI Evidence ID    : {ai_analysis.get('evidence_id', 'N/A')}"
    )

    lines.append(
        f"AI Video File     : {ai_analysis.get('video_file', 'N/A')}"
    )

    events = ai_analysis.get(
        "events",
        []
    )

    lines.append(
        f"Analysis Events   : {len(events)}"
    )

    lines.append("")

    # ========================================================
    # DETECTED EVENTS
    # ========================================================

    lines.append(
        "DETECTED EVENTS"
    )

    lines.append(
        "-" * 70
    )

    if events:

        for number, event in enumerate(
            events,
            start=1
        ):

            lines.append(
                f"Event {number}"
            )

            lines.append(
                f"  Frame       : {event.get('frame', 'N/A')}"
            )

            lines.append(
                f"  Timestamp   : {event.get('timestamp_seconds', 'N/A')} seconds"
            )

            detections = event.get(
                "detections",
                []
            )

            if detections:

                for detection in detections:

                    detection_type = detection.get(
                        "type",
                        "N/A"
                    )

                    label = detection.get(
                        "label",
                        "N/A"
                    )

                    confidence = detection.get(
                        "confidence"
                    )

                    if confidence is not None:

                        lines.append(
                            f"  Detection   : {detection_type} - {label} "
                            f"(confidence: {confidence})"
                        )

                    else:

                        lines.append(
                            f"  Detection   : {detection_type} - {label}"
                        )

            lines.append("")

    else:

        lines.append(
            "No AI events detected."
        )

        lines.append("")

    # ========================================================
    # CHAIN OF CUSTODY
    # ========================================================

    lines.append(
        "CHAIN OF CUSTODY"
    )

    lines.append(
        "-" * 70
    )

    if custody_data:

        custody_events = custody_data.get(
            "chain_of_custody",
            []
        )

        lines.append(
            f"Custody Events   : {len(custody_events)}"
        )

        lines.append("")

        for number, event in enumerate(
            custody_events,
            start=1
        ):

            lines.append(
                f"Event {number}"
            )

            lines.append(
                f"  Timestamp   : {event.get('timestamp', 'N/A')}"
            )

            lines.append(
                f"  Action      : {event.get('action', 'N/A')}"
            )

            lines.append(
                f"  Description : {event.get('description', 'N/A')}"
            )

            lines.append("")

    else:

        lines.append(
            "No chain-of-custody record found."
        )

        lines.append("")

    # ========================================================
    # PIPELINE INFORMATION
    # ========================================================

    lines.append(
        "PIPELINE INFORMATION"
    )

    lines.append(
        "-" * 70
    )

    lines.append(
        f"Pipeline Result  : {pipeline_file}"
    )

    lines.append(
        f"Report Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    lines.append(
        "Status           : FORENSIC ANALYSIS COMPLETED"
    )

    lines.append("")

    lines.append(
        "=" * 70
    )

    lines.append(
        "                 END OF FORENSIC REPORT"
    )

    lines.append(
        "=" * 70
    )

    # ========================================================
    # SAVE REPORT
    # ========================================================

    with open(
        report_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            "\n".join(lines)
        )

    return report_file


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("\n" + "=" * 70)

    print(
        "             FORENSIC REPORT GENERATOR"
    )

    print("=" * 70)

    try:

        pipeline_file = find_latest_pipeline()

        print(
            "\nUsing pipeline result:"
        )

        print(
            pipeline_file
        )

        pipeline_data = load_json(
            pipeline_file
        )

        report_file = generate_report(
            pipeline_data,
            pipeline_file
        )

        print(
            "\n✓ Forensic report generated."
        )

        print(
            "Saved as:"
        )

        print(
            report_file
        )

        print(
            "\n" + "=" * 70
        )

    except Exception as error:

        print(
            "\nERROR:"
        )

        print(
            error
        )