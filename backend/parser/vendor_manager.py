"""
Vendor Manager
--------------
Connects vendor detection with the appropriate parser and
device capability information.

This module does NOT connect to real DVR/NVR devices yet.
It prepares the architecture for vendor-specific handling.
"""

from parser.vendor_detector import detect_vendor
from parser.generic_parser import parse_generic_evidence
from device.vendor_capabilities import VENDOR_CAPABILITIES


def get_vendor_capabilities(vendor):
    """Return device capabilities for a detected vendor."""

    if not vendor:
        return None

    return VENDOR_CAPABILITIES.get(vendor)


def analyze_file(file_path, evidence_id="EVD-UNKNOWN"):
    """
    Analyze a forensic evidence/video file.

    The vendor detector is the source of truth for vendor
    identification. If the vendor cannot be reliably
    identified, the generic evidence parser is used.
    """

    # Run vendor detection
    detection = detect_vendor(file_path)

    # The detector currently returns the actual vendor result
    # inside detection["detection"].
    detector_result = detection.get("detection", {})

    vendor = detector_result.get("vendor")
    confidence = detector_result.get("confidence")

    result = {
        "evidence_id": evidence_id,
        "file": file_path,
        "vendor": vendor,
        "confidence": confidence,
        "detection": detection
    }

    # =================================================
    # UNKNOWN VENDOR
    # =================================================

    if not vendor or vendor == "UNKNOWN":

        generic_result = parse_generic_evidence(
            evidence_id,
            file_path
        )

        result["parser"] = "generic_parser"
        result["status"] = "GENERIC_FALLBACK"

        result["reason"] = (
            "Vendor could not be reliably identified. "
            "Generic analysis will be used instead of guessing."
        )

        result["analysis"] = generic_result
        result["capabilities"] = None

        return result

    # =================================================
    # KNOWN VENDOR
    # =================================================

    capabilities = get_vendor_capabilities(vendor)

    result["capabilities"] = capabilities

    if capabilities:

        result["driver"] = capabilities.get("driver")

        result["primary_protocol"] = capabilities.get(
            "primary_protocol"
        )

        result["fallback_protocol"] = capabilities.get(
            "fallback_protocol"
        )

        result["live_stream"] = capabilities.get(
            "live_stream"
        )

        result["historical_playback"] = capabilities.get(
            "historical_playback"
        )

        result["event_ingest"] = capabilities.get(
            "event_ingest"
        )

        result["cloud_p2p"] = capabilities.get(
            "cloud_p2p"
        )

    result["status"] = "VENDOR_IDENTIFIED"

    return result


# =====================================================
# BASIC MODULE TEST
# =====================================================

if __name__ == "__main__":

    print("=" * 60)
    print("             VENDOR MANAGER TEST")
    print("=" * 60)
    print()

    print("Vendor manager module loaded successfully.")
    print()

    print("Supported vendors:")

    for vendor in VENDOR_CAPABILITIES:
        print(f"  - {vendor}")

    print()
    print("=" * 60)
    print("              TEST COMPLETE")
    print("=" * 60)