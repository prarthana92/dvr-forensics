import os
import json
import hashlib
from datetime import datetime

from parser.vendor_manager import analyze_file

from metadata.metadata import extract_metadata

from custody.custody_engine import (
    ChainOfCustodyEngine,
    save_chain_of_custody
)

from integrity.integrity_engine import run_integrity_assessment
from fingerprint.fingerprint_engine import run_fingerprint
from correlation.correlation_engine import run_correlation
from confidence.confidence_engine import run_confidence_assessment
from decision.decision_engine import run_decision
from recovery.recovery_workflow import run_recovery_workflow


# ============================================================
# PATH CONFIGURATION
# ============================================================

BACKEND_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

OUTPUT_DIR = os.path.join(
    BACKEND_DIR,
    "output"
)


# ============================================================
# HASHING
# ============================================================

def calculate_hashes(file_path):

    md5 = hashlib.md5()
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        while True:

            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            md5.update(chunk)
            sha256.update(chunk)

    return {
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest()
    }


# ============================================================
# AI RESULT ASSOCIATION
# ============================================================

def load_ai_results(
    evidence_id,
    video_file
):

    ai_path = os.path.join(
        OUTPUT_DIR,
        "ai_results.json"
    )

    if not os.path.exists(ai_path):

        return {
            "found": False,
            "evidence_match": False,
            "video_match": False,
            "associated": False,
            "data": None,
            "path": ai_path
        }

    with open(
        ai_path,
        "r",
        encoding="utf-8"
    ) as file:

        ai_data = json.load(file)

    evidence_match = (
        str(
            ai_data.get("evidence_id", "")
        ).strip()
        == str(evidence_id).strip()
    )

    ai_video_file = os.path.basename(
        str(
            ai_data.get("video_file", "")
        )
    )

    requested_video_file = os.path.basename(
        str(video_file)
    )

    video_match = (
        ai_video_file.lower()
        == requested_video_file.lower()
    )

    associated = (
        evidence_match
        or video_match
    )

    return {
        "found": True,
        "evidence_match": evidence_match,
        "video_match": video_match,
        "associated": associated,
        "data": ai_data,
        "path": ai_path
    }


# ============================================================
# MAIN FORENSIC PIPELINE
# ============================================================

def run_forensic_pipeline(
    file_path,
    evidence_id
):

    print()
    print("=" * 70)
    print("                 TRACEX FORENSIC PIPELINE")
    print("=" * 70)

    # --------------------------------------------------------
    # PATHS
    # --------------------------------------------------------

    file_path = os.path.abspath(
        file_path
    )

    if not os.path.exists(file_path):

        raise FileNotFoundError(
            f"Evidence file not found: {file_path}"
        )

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    file_name = os.path.basename(
        file_path
    )

    file_size = os.path.getsize(
        file_path
    )

    # --------------------------------------------------------
    # STAGE 1 - VALIDATION
    # --------------------------------------------------------

    print()
    print("[1/12] Validating evidence...")
    print(
        f"File: {file_name}"
    )
    print(
        f"Size: {file_size} bytes"
    )

    custody = ChainOfCustodyEngine(
        evidence_id
    )

    custody.add_event(
        "Evidence Acquired",
        "COMPLETED",
        {
            "file_name": file_name,
            "file_path": file_path,
            "size_bytes": file_size
        }
    )

    # --------------------------------------------------------
    # STAGE 2 - HASHING
    # --------------------------------------------------------

    print()
    print("[2/12] Calculating evidence hashes...")

    hashes = calculate_hashes(
        file_path
    )

    print(
        f"MD5: {hashes['md5']}"
    )

    print(
        f"SHA-256: {hashes['sha256']}"
    )

    custody.add_event(
        "SHA256 Calculated",
        "COMPLETED",
        {
            "sha256": hashes["sha256"],
            "md5": hashes["md5"]
        }
    )

    # --------------------------------------------------------
    # STAGE 3 - METADATA
    # --------------------------------------------------------

    print()
    print("[3/12] Extracting metadata...")

    try:

        metadata = extract_metadata(
            file_path
        )

        metadata_status = "CONNECTED"

        print(
            "Metadata extraction: CONNECTED"
        )

        for key, value in metadata.items():

            print(
                f"{key}: {value}"
            )

    except Exception as error:

        metadata = {
            "status": "ERROR",
            "error": str(error)
        }

        metadata_status = "ERROR"

        print(
            "Metadata extraction: ERROR"
        )

        print(
            f"Reason: {error}"
        )

    custody.add_event(
        "Metadata Extraction Performed",
        metadata_status,
        metadata
    )

    # --------------------------------------------------------
    # STAGE 4 - INTEGRITY
    # --------------------------------------------------------

    print()
    print("[4/12] Assessing evidence integrity...")

    integrity_path = os.path.join(
        OUTPUT_DIR,
        "integrity_assessment.json"
    )

    integrity_result = run_integrity_assessment(
        file_path,
        integrity_path
    )

    integrity_status = integrity_result.get(
        "overall_assessment",
        "UNKNOWN"
    )

    decode_integrity = integrity_result.get(
        "decode_integrity",
        {}
    )

    print(
        f"Integrity: {integrity_status}"
    )

    print(
        "Container status:",
        integrity_result.get(
            "container_integrity",
            {}
        ).get(
            "status",
            "UNKNOWN"
        )
    )

    print(
        "Decode status:",
        decode_integrity.get(
            "status",
            "UNKNOWN"
        )
    )

    print(
        "Decoded frames:",
        decode_integrity.get(
            "decoded_frames",
            "UNKNOWN"
        )
    )

    print(
        "Expected frames:",
        decode_integrity.get(
            "expected_frames",
            "UNKNOWN"
        )
    )

    print(
        "Completeness:",
        decode_integrity.get(
            "completeness_percent",
            "UNKNOWN"
        ),
        "%"
    )

    custody.add_event(
        "Integrity Assessment Performed",
        "COMPLETED",
        {
            "overall_assessment": integrity_status
        }
    )

    # --------------------------------------------------------
    # STAGE 5 - VENDOR DETECTION
    # --------------------------------------------------------

    print()
    print("[5/12] Detecting vendor...")

    vendor_result = analyze_file(
        file_path,
        evidence_id
    )

    vendor_output_path = os.path.join(
        OUTPUT_DIR,
        "vendor_detection.json"
    )

    with open(
        vendor_output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            vendor_result,
            file,
            indent=2
        )

    detection = vendor_result.get(
        "detection",
        {}
    )

    # Handle the nested structure produced by vendor_manager.
    if isinstance(detection, dict):

        nested_detection = detection.get(
            "detection",
            {}
        )

        if isinstance(nested_detection, dict):

            vendor = nested_detection.get(
                "vendor",
                vendor_result.get(
                    "vendor",
                    "UNKNOWN"
                )
            )

        else:

            vendor = detection.get(
                "vendor",
                vendor_result.get(
                    "vendor",
                    "UNKNOWN"
                )
            )

    else:

        vendor = vendor_result.get(
            "vendor",
            "UNKNOWN"
        )

    vendor_status = vendor_result.get(
        "status",
        "UNKNOWN"
    )

    print(
        f"Vendor: {vendor}"
    )

    print(
        f"Status: {vendor_status}"
    )

    custody.add_event(
        "Vendor Detection Performed",
        "COMPLETED",
        {
            "vendor": vendor,
            "status": vendor_status
        }
    )

    # --------------------------------------------------------
    # STAGE 6 - EVIDENCE FINGERPRINT
    # --------------------------------------------------------

    print()
    print("[6/12] Generating evidence fingerprint...")

    fingerprint_path = os.path.join(
        OUTPUT_DIR,
        "evidence_fingerprint.json"
    )

    fingerprint_result = run_fingerprint(
        file_path,
        evidence_id,
        fingerprint_path
    )

    fingerprint_value = fingerprint_result.get(
        "fingerprint"
    )

    print(
        f"Fingerprint: {fingerprint_value}"
    )

    custody.add_event(
        "Evidence Fingerprint Generated",
        "COMPLETED",
        {
            "fingerprint": fingerprint_value
        }
    )

    # --------------------------------------------------------
    # STAGE 7 - AI ASSOCIATION
    # --------------------------------------------------------

    print()
    print("[7/12] Checking AI results...")

    ai_info = load_ai_results(
        evidence_id,
        file_path
    )

    if ai_info["found"]:

        print(
            "AI results: FOUND"
        )

    else:

        print(
            "AI results: NOT FOUND"
        )

    print(
        "Evidence match:",
        ai_info["evidence_match"]
    )

    print(
        "Video match:",
        ai_info["video_match"]
    )

    print(
        "Associated:",
        ai_info["associated"]
    )

    custody.add_event(
        "AI Analysis Received",
        "COMPLETED" if ai_info["found"] else "NOT_FOUND",
        {
            "found": ai_info["found"],
            "evidence_match": ai_info["evidence_match"],
            "video_match": ai_info["video_match"],
            "associated": ai_info["associated"]
        }
    )

    # --------------------------------------------------------
    # STAGE 8 - CORRELATION
    # --------------------------------------------------------

    print()
    print("[8/12] Correlating AI detections...")

    correlation_path = os.path.join(
        OUTPUT_DIR,
        "correlation_result.json"
    )

    if ai_info["associated"]:

        correlation_result = run_correlation(
            evidence_id,
            ai_info["path"],
            correlation_path
        )

        correlation_status = "COMPLETED"

        print(
            "Correlation: COMPLETED"
        )

        print(
            "Total events:",
            correlation_result.get(
                "summary",
                {}
            ).get(
                "total_events",
                0
            )
        )

    else:

        correlation_result = {
            "status": "NOT_ASSOCIATED",
            "evidence_id": evidence_id,
            "reason": (
                "AI results are not associated "
                "with this evidence."
            )
        }

        correlation_status = "NOT_ASSOCIATED"

        print(
            "Correlation: SKIPPED"
        )

        print(
            "Reason: AI results are not associated."
        )

    custody.add_event(
        "AI Correlation Performed",
        correlation_status,
        {
            "status": correlation_status
        }
    )

    # --------------------------------------------------------
    # STAGE 9 - CONFIDENCE / RELIABILITY
    # --------------------------------------------------------

    print()
    print(
        "[9/12] Assessing confidence and reliability..."
    )

    confidence_path = os.path.join(
        OUTPUT_DIR,
        "confidence_assessment.json"
    )

    if ai_info["associated"]:

        confidence_result = run_confidence_assessment(
            evidence_id,
            ai_info["path"],
            integrity_path,
            confidence_path
        )

        confidence_status = (
            confidence_result
            .get(
                "overall_reliability",
                {}
            )
            .get(
                "level",
                "UNKNOWN"
            )
        )

        print(
            "Confidence assessment: COMPLETED"
        )

        print(
            "Reliability score:",
            confidence_result
            .get(
                "overall_reliability",
                {}
            )
            .get(
                "score"
            )
        )

        print(
            "Reliability level:",
            confidence_status
        )

    else:

        confidence_result = {
            "status": "NOT_ASSOCIATED",
            "evidence_id": evidence_id,
            "reason": (
                "AI results are not associated "
                "with this evidence."
            )
        }

        confidence_status = "NOT_ASSOCIATED"

        print(
            "Confidence assessment: SKIPPED"
        )

        print(
            "Reason: AI results are not associated."
        )

    custody.add_event(
        "Confidence and Reliability Assessment Performed",
        "COMPLETED"
        if ai_info["associated"]
        else "NOT_ASSOCIATED",
        {
            "status": confidence_status
        }
    )

    # --------------------------------------------------------
    # STAGE 10 - FORENSIC DECISION
    # --------------------------------------------------------

    print()
    print(
        "[10/12] Building forensic decision..."
    )

    decision_path = os.path.join(
        OUTPUT_DIR,
        "forensic_decision.json"
    )

    decision_result = run_decision(
        evidence_id,
        vendor_output_path,
        integrity_path,
        decision_path
    )

    # IMPORTANT:
    # decision_engine.py returns the decision fields
    # directly. There is NO "decision" wrapper.
    decision = decision_result

    primary_decision = decision.get(
        "primary_decision",
        "MANUAL_REVIEW"
    )

    priority = decision.get(
        "priority",
        "MEDIUM"
    )

    print(
        f"Primary decision: {primary_decision}"
    )

    print(
        f"Priority: {priority}"
    )

    print(
        f"Vendor: {decision.get('vendor', vendor)}"
    )

    print(
        f"Integrity: "
        f"{decision.get('integrity', {}).get('overall', integrity_status)}"
    )

    print(
        "Recommended actions:"
    )

    for action in decision.get(
        "recommended_actions",
        []
    ):

        print(
            f" - {action}"
        )

    custody.add_event(
        "Forensic Decision Generated",
        "COMPLETED",
        {
            "primary_decision": primary_decision,
            "priority": priority
        }
    )

    # --------------------------------------------------------
    # STAGE 11 - RECOVERY
    # --------------------------------------------------------

    print()
    print(
        "[11/12] Evaluating recovery requirement..."
    )

    recovery_required_decisions = {
        "RECOVERY_REQUIRED",
        "RECOVERY_RECOMMENDED",
        "RECOVERY_WORKFLOW"
    }

    if primary_decision in recovery_required_decisions:

        print(
            f"Recovery decision: {primary_decision}"
        )

        print(
            "Original evidence will NOT be modified."
        )

        recovery_output_folder = os.path.join(
            OUTPUT_DIR,
            "recovery",
            evidence_id
        )

        os.makedirs(
            recovery_output_folder,
            exist_ok=True
        )

        try:

            recovery_result = run_recovery_workflow(
                source_file=file_path,
                output_folder=recovery_output_folder,
                evidence_id=evidence_id
            )

            recovery_status = recovery_result.get(
                "overall_status",
                "RECOVERY_ATTEMPTED"
            )

            print(
                f"Recovery status: {recovery_status}"
            )

            custody.add_event(
                "Recovery Attempt Performed",
                "COMPLETED",
                {
                    "status": recovery_status
                }
            )

            custody.add_event(
                "Recovery Validation Performed",
                "COMPLETED",
                {
                    "status": recovery_status
                }
            )

        except Exception as error:

            recovery_result = {
                "overall_status": "RECOVERY_ERROR",
                "evidence_id": evidence_id,
                "error": str(error)
            }

            recovery_status = "RECOVERY_ERROR"

            print(
                "Recovery error:",
                error
            )

            custody.add_event(
                "Recovery Attempt Performed",
                "FAILED",
                {
                    "error": str(error)
                }
            )

    else:

        recovery_result = {
            "overall_status": "NOT_REQUIRED",
            "evidence_id": evidence_id,
            "reason": (
                "Evidence does not require recovery "
                "based on forensic decision."
            )
        }

        recovery_status = "NOT_REQUIRED"

        print(
            "Recovery: SKIPPED"
        )

        print(
            "Reason: Evidence does not require recovery "
            "based on forensic decision."
        )

    # --------------------------------------------------------
    # STAGE 12 - FINAL FORENSIC RESULT
    # --------------------------------------------------------

    print()
    print(
        "[12/12] Building final forensic result..."
    )

    final_result = {

        "pipeline_version": "1.8",

        "forensic_status": "COMPLETED",

        "generated_at": datetime.now().isoformat(),

        "evidence": {

            "evidence_id": evidence_id,

            "file_name": file_name,

            "file_path": file_path,

            "size_bytes": file_size,

            "md5": hashes["md5"],

            "sha256": hashes["sha256"]

        },

        "metadata": metadata,

        "integrity_assessment": integrity_result,

        "vendor_analysis": vendor_result,

        "fingerprint": fingerprint_result,

        "ai_analysis": ai_info,

        "correlation": correlation_result,

        "confidence_reliability": confidence_result,

        "forensic_decision": decision_result,

        "recovery": recovery_result

    }

    final_output_path = os.path.join(
        OUTPUT_DIR,
        "forensic_result.json"
    )

    with open(
        final_output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            final_result,
            file,
            indent=2
        )

    custody.add_event(
        "Forensic Result Generated",
        "COMPLETED",
        {
            "output_file": final_output_path
        }
    )

    # --------------------------------------------------------
    # SAVE CHAIN OF CUSTODY
    # --------------------------------------------------------

    custody_result = custody.build_result()

    custody_path = os.path.join(
        OUTPUT_DIR,
        "chain_of_custody.json"
    )

    save_chain_of_custody(
        custody_result,
        custody_path
    )

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "                    PIPELINE COMPLETED"
    )
    print("=" * 70)

    print(
        f"FINAL STATUS: "
        f"{final_result['forensic_status']}"
    )

    print(
        f"INTEGRITY STATUS: "
        f"{integrity_status}"
    )

    print(
        f"METADATA STATUS: "
        f"{metadata_status}"
    )

    print(
        f"FINGERPRINT STATUS: "
        f"{fingerprint_value}"
    )

    print(
        f"CORRELATION STATUS: "
        f"{correlation_status}"
    )

    print(
        f"RELIABILITY STATUS: "
        f"{confidence_status}"
    )

    print(
        f"FORENSIC DECISION: "
        f"{primary_decision}"
    )

    print(
        f"DECISION PRIORITY: "
        f"{priority}"
    )

    print(
        f"RECOVERY STATUS: "
        f"{recovery_status}"
    )

    print(
        f"FINAL RESULT: "
        f"{final_output_path}"
    )

    print(
        f"CHAIN OF CUSTODY: "
        f"{custody_path}"
    )

    print(
        "=" * 70
    )

    return final_result


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    test_file = os.path.join(
        BACKEND_DIR,
        "device",
        "hikvision_test.mp4"
    )

    test_evidence_id = (
        "EVD-PIPELINE-TEST-001"
    )

    run_forensic_pipeline(
        test_file,
        test_evidence_id
    )