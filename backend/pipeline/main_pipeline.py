```python
from pathlib import Path
import sys
import json
import subprocess


# ============================================================
# BACKEND FOLDER
# ============================================================

BACKEND_FOLDER = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(BACKEND_FOLDER))


# ============================================================
# IMPORT BACKEND MODULES
# ============================================================

from evidence.import_evidence2 import import_evidence
from recovery.recovery import process_forensic_copy
from metadata.metadata import extract_metadata
from video.video_processor import extract_frames
from custody.chain_of_custody import add_custody_event


# ============================================================
# LOAD AI RESULTS
# ============================================================

def load_ai_results(evidence_id, forensic_copy_path):

    ai_file = (
        BACKEND_FOLDER
        / "output"
        / "ai_results.json"
    )

    if not ai_file.exists():

        print("\nAI results file not found.")
        print("Continuing without AI analysis.")

        return {
            "evidence_id": evidence_id,
            "video_file": Path(
                forensic_copy_path
            ).name,
            "events": []
        }

    try:

        with open(
            ai_file,
            "r",
            encoding="utf-8"
        ) as file:

            ai_results = json.load(file)

        if not isinstance(
            ai_results,
            dict
        ):

            raise ValueError(
                "AI results must be a JSON object."
            )

        if "events" not in ai_results:

            raise ValueError(
                "AI results do not contain 'events'."
            )

        if not isinstance(
            ai_results["events"],
            list
        ):

            raise ValueError(
                "'events' must be a list."
            )

        # ----------------------------------------------------
        # CONNECT AI TO CURRENT EVIDENCE
        # ----------------------------------------------------

        connected_ai_results = {

            "evidence_id":
                evidence_id,

            "video_file":
                Path(
                    forensic_copy_path
                ).name,

            "events":
                ai_results["events"]

        }

        print(
            "\nAI results loaded successfully."
        )

        print(
            "AI Evidence ID:",
            evidence_id
        )

        print(
            "AI Video:",
            Path(
                forensic_copy_path
            ).name
        )

        print(
            "AI Events:",
            len(
                ai_results["events"]
            )
        )

        return connected_ai_results

    except Exception as error:

        print(
            "\nAI results could not be loaded:"
        )

        print(error)

        print(
            "Continuing without AI analysis."
        )

        return {
            "evidence_id": evidence_id,
            "video_file": Path(
                forensic_copy_path
            ).name,
            "events": []
        }


# ============================================================
# GENERATE TXT FORENSIC REPORT
# ============================================================

def generate_text_report(evidence_id):

    report_script = (
        BACKEND_FOLDER
        / "reports"
        / "report_generator.py"
    )

    if not report_script.exists():

        print(
            "\nWarning: report_generator.py not found."
        )

        return None

    print(
        "\nStarting forensic TXT report generation..."
    )

    try:

        result = subprocess.run(
            [
                sys.executable,
                str(report_script),
                evidence_id
            ],
            cwd=str(BACKEND_FOLDER),
            capture_output=True,
            text=True
        )

        if result.stdout:
            print(result.stdout)

        if result.returncode != 0:

            print(
                "TXT report generation failed."
            )

            if result.stderr:
                print(result.stderr)

            return None

        report_file = (
            BACKEND_FOLDER
            / "reports"
            / f"{evidence_id}_forensic_report.txt"
        )

        if report_file.exists():

            print(
                "✓ TXT forensic report generated."
            )

            print(
                "Saved as:",
                report_file
            )

            return report_file

        print(
            "Warning: TXT report was not found after generation."
        )

        return None

    except Exception as error:

        print(
            "\nTXT report generation error:"
        )

        print(error)

        return None


# ============================================================
# GENERATE PDF FORENSIC REPORT
# ============================================================

def generate_pdf_report():

    pdf_script = (
        BACKEND_FOLDER
        / "reports"
        / "pdf_report_generator.py"
    )

    if not pdf_script.exists():

        print(
            "\nWarning: pdf_report_generator.py not found."
        )

        return None

    print(
        "\nStarting forensic PDF report generation..."
    )

    try:

        result = subprocess.run(
            [
                sys.executable,
                str(pdf_script)
            ],
            cwd=str(BACKEND_FOLDER),
            capture_output=True,
            text=True
        )

        if result.stdout:
            print(result.stdout)

        if result.returncode != 0:

            print(
                "PDF report generation failed."
            )

            if result.stderr:
                print(result.stderr)

            return None

        # The PDF generator uses the latest TXT report.

        reports = sorted(
            (
                BACKEND_FOLDER
                / "reports"
            ).glob(
                "*_forensic_report.pdf"
            ),
            key=lambda file:
                file.stat().st_mtime,
            reverse=True
        )

        if reports:

            pdf_file = reports[0]

            print(
                "✓ PDF forensic report generated."
            )

            print(
                "Saved as:",
                pdf_file
            )

            return pdf_file

        print(
            "Warning: PDF report was not found."
        )

        return None

    except Exception as error:

        print(
            "\nPDF report generation error:"
        )

        print(error)

        return None


# ============================================================
# MAIN PIPELINE
# ============================================================

def start_pipeline(file_path):

    print("\n" + "=" * 70)

    print(
        "             DVR FORENSIC ANALYSIS PIPELINE"
    )

    print("=" * 70)


    # ========================================================
    # RESOLVE INPUT FILE
    # ========================================================

    file_path = Path(file_path)

    if not file_path.is_absolute():

        file_path = (
            BACKEND_FOLDER
            / file_path
        )

    file_path = file_path.resolve()

    print(
        "\nInput evidence:"
    )

    print(file_path)


    # ========================================================
    # CHECK FILE
    # ========================================================

    if not file_path.exists():

        print(
            "\nERROR: Evidence file not found."
        )

        return

    print(
        "\nEvidence file found."
    )


    # ========================================================
    # STAGE 1 — EVIDENCE INTAKE
    # ========================================================

    print(
        "\nStarting evidence intake..."
    )

    try:

        evidence_record = import_evidence(
            str(file_path)
        )

    except Exception as error:

        print(
            "\nEvidence intake failed:"
        )

        print(error)

        return


    # ========================================================
    # GET EVIDENCE ID
    # ========================================================

    evidence_id = (
        evidence_record["evidence_id"]
    )

    print(
        "\nEvidence successfully registered."
    )

    print(
        "Evidence ID:",
        evidence_id
    )

    print(
        "File:",
        evidence_record["file_name"]
    )

    print(
        "Type:",
        evidence_record["evidence_type"]
    )


    # ========================================================
    # CHAIN OF CUSTODY — EVIDENCE REGISTERED
    # ========================================================

    try:

        add_custody_event(

            evidence_id,

            "EVIDENCE_REGISTERED",

            "Evidence successfully registered in the forensic system."

        )

        print(
            "✓ Chain of custody updated."
        )

    except Exception as error:

        print(
            "Warning: Could not update chain of custody:"
        )

        print(error)


    # ========================================================
    # STAGE 2 — FORENSIC COPY
    # ========================================================

    print(
        "\nStarting forensic copy process..."
    )

    output_folder = (
        BACKEND_FOLDER
        / "output"
    )

    try:

        recovery_result = process_forensic_copy(

            str(file_path),

            str(output_folder),

            evidence_id

        )

    except Exception as error:

        print(
            "\nForensic copy failed:"
        )

        print(error)

        return


    print(
        "\nForensic copy process completed."
    )


    # ========================================================
    # CHAIN OF CUSTODY — FORENSIC COPY
    # ========================================================

    try:

        add_custody_event(

            evidence_id,

            "FORENSIC_COPY_CREATED",

            "Forensic copy created and SHA-256 verification process completed."

        )

        print(
            "✓ Chain of custody updated."
        )

    except Exception as error:

        print(
            "Warning: Could not update chain of custody:"
        )

        print(error)


    # ========================================================
    # CHAIN OF CUSTODY — INTEGRITY
    # ========================================================

    if recovery_result["status"] == "VERIFIED":

        try:

            add_custody_event(

                evidence_id,

                "INTEGRITY_VERIFIED",

                "Forensic copy SHA-256 hash matches the original evidence."

            )

            print(
                "✓ Integrity verification recorded in chain of custody."
            )

        except Exception as error:

            print(
                "Warning: Could not record integrity verification:"
            )

            print(error)


    # ========================================================
    # FORENSIC COPY PATH
    # ========================================================

    forensic_copy_path = Path(
        recovery_result["forensic_copy"]
    )


    # ========================================================
    # STAGE 3 — METADATA
    # ========================================================

    print(
        "\nStarting metadata extraction..."
    )

    try:

        metadata = extract_metadata(
            str(file_path)
        )

        print(
            "\nMetadata extracted successfully."
        )

        print(
            "\nVIDEO METADATA"
        )

        print(
            "-" * 40
        )

        for key, value in metadata.items():

            print(
                f"{key:<18}: {value}"
            )

        add_custody_event(

            evidence_id,

            "METADATA_EXTRACTED",

            "Video metadata was extracted from the evidence."

        )

        print(
            "✓ Metadata extraction recorded in chain of custody."
        )

    except Exception as error:

        print(
            "\nMetadata extraction failed:"
        )

        print(error)

        metadata = {}


    # ========================================================
    # STAGE 4 — FRAME EXTRACTION
    # ========================================================

    print(
        "\nStarting frame extraction..."
    )

    frames_folder = (

        BACKEND_FOLDER
        / "output"
        / "frames"
        / evidence_id

    )

    try:

        frame_count = extract_frames(

            str(forensic_copy_path),

            str(frames_folder),

            1

        )

        print(
            "\nFrames extracted successfully."
        )

        print(
            "Total frames saved:",
            frame_count
        )

        add_custody_event(

            evidence_id,

            "FRAMES_EXTRACTED",

            f"{frame_count} forensic video frames were extracted from the verified forensic copy."

        )

        print(
            "✓ Frame extraction recorded in chain of custody."
        )

    except Exception as error:

        print(
            "\nFrame extraction failed:"
        )

        print(error)

        frame_count = 0


    frame_index_path = (

        frames_folder
        / "frame_index.json"

    )


    # ========================================================
    # STAGE 5 — AI ANALYSIS
    # ========================================================

    print(
        "\nStarting AI integration..."
    )

    ai_results = load_ai_results(

        evidence_id,

        forensic_copy_path

    )


    # ========================================================
    # CHAIN OF CUSTODY — AI
    # ========================================================

    if len(
        ai_results["events"]
    ) > 0:

        try:

            add_custody_event(

                evidence_id,

                "AI_ANALYSIS_COMPLETED",

                f"AI analysis results were connected to the evidence. {len(ai_results['events'])} events detected."

            )

            print(
                "✓ AI analysis recorded in chain of custody."
            )

        except Exception as error:

            print(
                "Warning: Could not record AI analysis:"
            )

            print(error)


    # ========================================================
    # STAGE 6 — FINAL PIPELINE RESULT
    # ========================================================

    print(
        "\nCreating final pipeline result..."
    )

    pipeline_results_folder = (

        BACKEND_FOLDER
        / "output"
        / "pipeline_results"

    )

    pipeline_results_folder.mkdir(

        parents=True,

        exist_ok=True

    )


    pipeline_result = {

        "evidence":
            evidence_record,

        "forensic_copy": {

            "path":
                str(
                    forensic_copy_path
                ),

            "verification_report":
                recovery_result[
                    "verification_report"
                ],

            "original_sha256":
                recovery_result[
                    "original_sha256"
                ],

            "copy_sha256":
                recovery_result[
                    "copy_sha256"
                ],

            "hash_match":
                recovery_result[
                    "hash_match"
                ],

            "integrity_verified":
                recovery_result[
                    "integrity_verified"
                ],

            "status":
                recovery_result[
                    "status"
                ],

            "verified_at":
                recovery_result[
                    "verified_at"
                ]

        },

        "metadata":
            metadata,

        "frames": {

            "count":
                frame_count,

            "folder":
                str(
                    frames_folder
                ),

            "frame_index":
                str(
                    frame_index_path
                )

        },

        "ai_analysis":
            ai_results

    }


    # ========================================================
    # SAVE PIPELINE RESULT
    # ========================================================

    result_file = (

        pipeline_results_folder
        / f"{evidence_id}_pipeline.json"

    )


    with open(

        result_file,

        "w",

        encoding="utf-8"

    ) as file:

        json.dump(

            pipeline_result,

            file,

            indent=4

        )


    print(
        "\nFinal pipeline result saved."
    )

    print(
        "Saved as:",
        result_file
    )


    # ========================================================
    # CHAIN OF CUSTODY — PIPELINE COMPLETED
    # ========================================================

    try:

        add_custody_event(

            evidence_id,

            "FORENSIC_PIPELINE_COMPLETED",

            "Evidence intake, forensic copy verification, metadata extraction, frame extraction, AI integration, and pipeline processing completed successfully."

        )

        print(
            "✓ Final pipeline completion recorded in chain of custody."
        )

    except Exception as error:

        print(
            "Warning: Could not record pipeline completion:"
        )

        print(error)


    # ========================================================
    # STAGE 7 — TXT FORENSIC REPORT
    # ========================================================

    print(
        "\nStarting forensic report generation..."
    )

    text_report = generate_text_report(
        evidence_id
    )


    if text_report:

        try:

            add_custody_event(

                evidence_id,

                "FORENSIC_REPORT_GENERATED",

                "Final forensic TXT report was generated from the completed pipeline result."

            )

            print(
                "✓ TXT report generation recorded in chain of custody."
            )

        except Exception as error:

            print(
                "Warning: Could not record TXT report generation:"
            )

            print(error)


    # ========================================================
    # STAGE 8 — PDF FORENSIC REPORT
    # ========================================================

    pdf_report = None

    if text_report:

        print(
            "\nStarting PDF forensic report generation..."
        )

        pdf_report = generate_pdf_report()


    if pdf_report:

        try:

            add_custody_event(

                evidence_id,

                "PDF_REPORT_GENERATED",

                "Final forensic PDF report was generated from the forensic TXT report."

            )

            print(
                "✓ PDF report generation recorded in chain of custody."
            )

        except Exception as error:

            print(
                "Warning: Could not record PDF report generation:"
            )

            print(error)


    # ========================================================
    # FINAL STATUS
    # ========================================================

    custody_file = (

        BACKEND_FOLDER
        / "output"
        / "custody"
        / f"{evidence_id}_custody.json"

    )


    print(
        "\n" + "=" * 70
    )

    print(
        "        DVR FORENSIC ANALYSIS PIPELINE COMPLETED"
    )

    print("=" * 70)

    print(
        "\nEvidence ID:",
        evidence_id
    )

    print(
        "Forensic Copy:",
        forensic_copy_path.name
    )

    print(
        "Frames:",
        frame_count
    )

    print(
        "AI Events:",
        len(
            ai_results["events"]
        )
    )

    print(
        "Pipeline Result:",
        result_file
    )

    if text_report:

        print(
            "TXT Report:",
            text_report
        )

    else:

        print(
            "TXT Report: NOT GENERATED"
        )

    if pdf_report:

        print(
            "PDF Report:",
            pdf_report
        )

    else:

        print(
            "PDF Report: NOT GENERATED"
        )

    print(
        "Chain of Custody:",
        custody_file
    )

    print(
        "=" * 70
    )


# ============================================================
# PROGRAM START
# ============================================================

if __name__ == "__main__":

    file_path = input(
        "Enter the evidence file path: "
    ).strip()

    if not file_path:

        print(
            "\nEvidence file path cannot be empty."
        )

    else:

        start_pipeline(
            file_path
        )
```
