import os
from datetime import datetime

from parser.vendor_fingerprints import (
    VENDOR_FINGERPRINTS,
    SUPPORTED_VENDORS
)

from parser.container_fingerprint import analyze


# ============================================================
# TRACE X - DYNAMIC MULTI-SIGNAL VENDOR DETECTOR
# ============================================================
#
# Signals used:
#
# 1. File content fingerprints
# 2. MP4 container structure
# 3. FFprobe technical metadata
#
# IMPORTANT:
# Structural and FFprobe signals are NOT vendor proof unless
# they have been validated against genuine vendor samples.
#
# ============================================================


# ============================================================
# FILE CONTENT ANALYSIS
# ============================================================

def inspect_file_contents(file_path):

    file_size = os.path.getsize(file_path)

    chunks = []

    with open(file_path, "rb") as file:

        beginning_size = min(
            10 * 1024 * 1024,
            file_size
        )

        chunks.append(
            file.read(beginning_size)
        )

        if file_size > beginning_size:

            end_size = min(
                10 * 1024 * 1024,
                file_size
            )

            file.seek(
                max(
                    0,
                    file_size - end_size
                )
            )

            chunks.append(
                file.read(end_size)
            )

    return b"\n".join(chunks)


# ============================================================
# TEXT FINGERPRINT SEARCH
# ============================================================

def find_vendor_signatures(data):

    data_upper = data.upper()

    vendor_scores = {}
    evidence = {}

    for vendor, fingerprint_groups in VENDOR_FINGERPRINTS.items():

        score = 0
        matches = []

        # ----------------------------------------------------
        # STRONG
        # ----------------------------------------------------

        for fingerprint in fingerprint_groups.get(
            "strong",
            []
        ):

            fingerprint_bytes = fingerprint.encode(
                errors="ignore"
            )

            if fingerprint_bytes.upper() in data_upper:

                score += 100

                matches.append({
                    "fingerprint": fingerprint,
                    "strength": "STRONG",
                    "score": 100,
                    "signal": "FILE_CONTENT"
                })

        # ----------------------------------------------------
        # MEDIUM
        # ----------------------------------------------------

        for fingerprint in fingerprint_groups.get(
            "medium",
            []
        ):

            fingerprint_bytes = fingerprint.encode(
                errors="ignore"
            )

            if fingerprint_bytes.upper() in data_upper:

                score += 50

                matches.append({
                    "fingerprint": fingerprint,
                    "strength": "MEDIUM",
                    "score": 50,
                    "signal": "FILE_CONTENT"
                })

        vendor_scores[vendor] = score

        if matches:

            evidence[vendor] = matches

    return vendor_scores, evidence


# ============================================================
# STRUCTURAL SIGNAL ANALYSIS
# ============================================================

def compare_structural_signals(
    container_result
):

    scores = {
        vendor: 0
        for vendor in SUPPORTED_VENDORS
    }

    evidence = {}

    if not container_result:

        return scores, evidence

    container = container_result.get(
        "container",
        {}
    )

    box_sequence = container.get(
        "box_sequence",
        []
    )

    metadata = container_result.get(
        "metadata",
        {}
    )

    # --------------------------------------------------------
    # We ONLY use signatures that have explicitly been
    # validated in vendor_fingerprints.py.
    # --------------------------------------------------------

    for vendor in SUPPORTED_VENDORS:

        fingerprint_data = VENDOR_FINGERPRINTS.get(
            vendor,
            {}
        )

        if not fingerprint_data.get(
            "validated",
            False
        ):

            continue

        structural_signatures = fingerprint_data.get(
            "structural",
            []
        )

        for signature in structural_signatures:

            matched = True

            # ------------------------------------------------
            # Box requirement
            # ------------------------------------------------

            required_boxes = signature.get(
                "required_boxes",
                []
            )

            for required_box in required_boxes:

                if required_box not in box_sequence:

                    matched = False
                    break

            if not matched:
                continue

            # ------------------------------------------------
            # FTYP requirement
            # ------------------------------------------------

            required_major_brand = signature.get(
                "major_brand"
            )

            if required_major_brand:

                ftyp = metadata.get(
                    "ftyp",
                    {}
                )

                if ftyp.get(
                    "major_brand"
                ) != required_major_brand:

                    matched = False

            if not matched:
                continue

            # ------------------------------------------------
            # Codec requirement
            # ------------------------------------------------

            required_codec = signature.get(
                "codec"
            )

            if required_codec:

                sample_descriptions = metadata.get(
                    "sample_descriptions",
                    []
                )

                codec_found = False

                for description in sample_descriptions:

                    entries = description.get(
                        "sample_entries",
                        []
                    )

                    for entry in entries:

                        if entry.get(
                            "type"
                        ) == required_codec:

                            codec_found = True

                if not codec_found:

                    matched = False

            if not matched:
                continue

            # ------------------------------------------------
            # MATCH
            # ------------------------------------------------

            score = signature.get(
                "score",
                25
            )

            scores[vendor] += score

            evidence.setdefault(
                vendor,
                []
            ).append({

                "signal": "CONTAINER_STRUCTURE",

                "signature": signature,

                "score": score

            })

    return scores, evidence


# ============================================================
# FFPROBE SIGNAL ANALYSIS
# ============================================================

def compare_ffprobe_signals(
    ffprobe_result
):

    scores = {
        vendor: 0
        for vendor in SUPPORTED_VENDORS
    }

    evidence = {}

    if not ffprobe_result:

        return scores, evidence

    # --------------------------------------------------------
    # Only validated vendor fingerprints can receive points.
    # --------------------------------------------------------

    for vendor in SUPPORTED_VENDORS:

        fingerprint_data = VENDOR_FINGERPRINTS.get(
            vendor,
            {}
        )

        if not fingerprint_data.get(
            "validated",
            False
        ):

            continue

        signatures = fingerprint_data.get(
            "ffprobe",
            []
        )

        for signature in signatures:

            matched = True

            for key, expected_value in signature.items():

                if key == "score":
                    continue

                actual_value = ffprobe_result.get(
                    key
                )

                if actual_value != expected_value:

                    matched = False
                    break

            if matched:

                score = signature.get(
                    "score",
                    25
                )

                scores[vendor] += score

                evidence.setdefault(
                    vendor,
                    []
                ).append({

                    "signal": "FFPROBE",

                    "signature": signature,

                    "score": score

                })

    return scores, evidence


# ============================================================
# COMBINE ALL SIGNALS
# ============================================================

def combine_scores(
    text_scores,
    structural_scores,
    ffprobe_scores
):

    final_scores = {}

    for vendor in SUPPORTED_VENDORS:

        final_scores[vendor] = (

            text_scores.get(
                vendor,
                0
            )

            +

            structural_scores.get(
                vendor,
                0
            )

            +

            ffprobe_scores.get(
                vendor,
                0
            )
        )

    return final_scores


# ============================================================
# COMBINE EVIDENCE
# ============================================================

def combine_evidence(
    text_evidence,
    structural_evidence,
    ffprobe_evidence
):

    combined = {}

    for source in [
        text_evidence,
        structural_evidence,
        ffprobe_evidence
    ]:

        for vendor, matches in source.items():

            combined.setdefault(
                vendor,
                []
            ).extend(matches)

    return combined


# ============================================================
# FINAL VENDOR DECISION
# ============================================================

def determine_vendor(
    vendor_scores,
    evidence
):

    if not vendor_scores:

        return "UNKNOWN", "LOW"

    sorted_vendors = sorted(
        vendor_scores.items(),
        key=lambda item: item[1],
        reverse=True
    )

    best_vendor, best_score = sorted_vendors[0]

    # --------------------------------------------------------
    # No evidence
    # --------------------------------------------------------

    if best_score == 0:

        return "UNKNOWN", "LOW"

    # --------------------------------------------------------
    # Competing vendors
    # --------------------------------------------------------

    if len(sorted_vendors) > 1:

        second_vendor, second_score = sorted_vendors[1]

        if (
            second_score > 0
            and second_score == best_score
        ):

            return "UNKNOWN", "AMBIGUOUS"

    vendor_evidence = evidence.get(
        best_vendor,
        []
    )

    strong_matches = [
        item
        for item in vendor_evidence
        if item.get("strength") == "STRONG"
    ]

    medium_matches = [
        item
        for item in vendor_evidence
        if item.get("strength") == "MEDIUM"
    ]

    structural_matches = [
        item
        for item in vendor_evidence
        if item.get("signal") == "CONTAINER_STRUCTURE"
    ]

    ffprobe_matches = [
        item
        for item in vendor_evidence
        if item.get("signal") == "FFPROBE"
    ]

    # --------------------------------------------------------
    # Strong textual evidence
    # --------------------------------------------------------

    if len(strong_matches) >= 1:

        return best_vendor, "HIGH"

    # --------------------------------------------------------
    # Multiple medium fingerprints
    # --------------------------------------------------------

    if len(medium_matches) >= 2:

        return best_vendor, "MEDIUM"

    # --------------------------------------------------------
    # Multiple independent validated signals
    # --------------------------------------------------------

    independent_signals = 0

    if structural_matches:
        independent_signals += 1

    if ffprobe_matches:
        independent_signals += 1

    if len(medium_matches) >= 1:
        independent_signals += 1

    if independent_signals >= 2:

        return best_vendor, "MEDIUM"

    return "UNKNOWN", "LOW"


# ============================================================
# MAIN DETECTOR
# ============================================================

def detect_vendor(file_path):

    if not os.path.exists(file_path):

        raise FileNotFoundError(
            f"Evidence file not found: {file_path}"
        )

    file_name = os.path.basename(
        file_path
    )

    file_extension = os.path.splitext(
        file_name
    )[1].lower()

    file_size = os.path.getsize(
        file_path
    )

    # ========================================================
    # DEFAULT VALUES
    # ========================================================

    text_scores = {
        vendor: 0
        for vendor in SUPPORTED_VENDORS
    }

    structural_scores = {
        vendor: 0
        for vendor in SUPPORTED_VENDORS
    }

    ffprobe_scores = {
        vendor: 0
        for vendor in SUPPORTED_VENDORS
    }

    text_evidence = {}
    structural_evidence = {}
    ffprobe_evidence = {}

    container_result = None
    ffprobe_result = None

    reasons = []

    # ========================================================
    # 1. FILE CONTENT
    # ========================================================

    try:

        data = inspect_file_contents(
            file_path
        )

        text_scores, text_evidence = (
            find_vendor_signatures(
                data
            )
        )

    except Exception as error:

        reasons.append(
            "File-content analysis unavailable: "
            + str(error)
        )

    # ========================================================
    # 2. CONTAINER
    # ========================================================

    try:

        container_result = analyze(
            file_path
        )

        structural_scores, structural_evidence = (
            compare_structural_signals(
                container_result
            )
        )

        container_data = container_result.get(
            "container",
            {}
        )

        box_sequence = container_data.get(
            "box_sequence",
            []
        )

        unknown_boxes = container_data.get(
            "unknown_box_types",
            []
        )

        reasons.append(
            "Container structure analyzed: "
            + " → ".join(box_sequence)
        )

        if unknown_boxes:

            reasons.append(
                "Unknown/custom container boxes observed: "
                + ", ".join(
                    f"'{box}'"
                    for box in unknown_boxes
                )
            )

        reasons.append(
            "Container characteristics are descriptive "
            "evidence and were not treated as vendor proof."
        )

    except Exception as error:

        reasons.append(
            "Container analysis unavailable: "
            + str(error)
        )

    # ========================================================
    # 3. FFPROBE
    # ========================================================

    try:

        from parser.ffprobe_vendor_detector import (
            analyze_ffprobe
        )

        ffprobe_result = analyze_ffprobe(
            file_path
        )

        ffprobe_scores, ffprobe_evidence = (
            compare_ffprobe_signals(
                ffprobe_result
            )
        )

        if ffprobe_result:

            if ffprobe_result.get(
                "format"
            ):

                reasons.append(
                    "FFprobe format: "
                    + str(
                        ffprobe_result["format"]
                    )
                )

            if ffprobe_result.get(
                "duration"
            ) is not None:

                reasons.append(
                    "FFprobe duration: "
                    + str(
                        ffprobe_result["duration"]
                    )
                )

            if ffprobe_result.get(
                "bit_rate"
            ) is not None:

                reasons.append(
                    "FFprobe bit rate: "
                    + str(
                        ffprobe_result["bit_rate"]
                    )
                )

            if ffprobe_result.get(
                "video_codec"
            ):

                reasons.append(
                    "FFprobe video codec: "
                    + str(
                        ffprobe_result["video_codec"]
                    )
                )

            if ffprobe_result.get(
                "codec_tag"
            ):

                reasons.append(
                    "FFprobe codec tag: "
                    + str(
                        ffprobe_result["codec_tag"]
                    )
                )

            if ffprobe_result.get(
                "resolution"
            ):

                reasons.append(
                    "FFprobe resolution: "
                    + str(
                        ffprobe_result["resolution"]
                    )
                )

            if ffprobe_result.get(
                "pixel_format"
            ):

                reasons.append(
                    "FFprobe pixel format: "
                    + str(
                        ffprobe_result["pixel_format"]
                    )
                )

            if ffprobe_result.get(
                "frame_rate"
            ):

                reasons.append(
                    "FFprobe frame rate: "
                    + str(
                        ffprobe_result["frame_rate"]
                    )
                )

            reasons.append(
                "FFprobe metadata was collected as a "
                "standardized technical signal and was not "
                "automatically treated as vendor proof."
            )

    except Exception as error:

        reasons.append(
            "FFprobe analysis unavailable: "
            + str(error)
        )

    # ========================================================
    # 4. FINAL SCORES
    # ========================================================

    final_scores = combine_scores(
        text_scores,
        structural_scores,
        ffprobe_scores
    )

    final_evidence = combine_evidence(
        text_evidence,
        structural_evidence,
        ffprobe_evidence
    )

    # ========================================================
    # 5. FINAL DECISION
    # ========================================================

    detected_vendor, confidence = determine_vendor(
        final_scores,
        final_evidence
    )

    # ========================================================
    # 6. REASONS FROM EVIDENCE
    # ========================================================

    if text_evidence:

        for vendor, matches in text_evidence.items():

            for match in matches:

                reasons.append(
                    f"{vendor}: "
                    f"{match['strength']} fingerprint "
                    f"'{match['fingerprint']}' "
                    f"(+{match['score']})"
                )

    else:

        reasons.append(
            "No textual vendor-specific evidence found."
        )

    for vendor, matches in structural_evidence.items():

        for match in matches:

            reasons.append(
                f"{vendor}: validated structural "
                f"signature matched "
                f"(+{match['score']})"
            )

    for vendor, matches in ffprobe_evidence.items():

        for match in matches:

            reasons.append(
                f"{vendor}: validated FFprobe "
                f"signature matched "
                f"(+{match['score']})"
            )

    # ========================================================
    # 7. UNKNOWN REASON
    # ========================================================

    if detected_vendor == "UNKNOWN":

        if confidence == "AMBIGUOUS":

            reasons.append(
                "Multiple vendors produced equal evidence "
                "scores. Vendor identification was rejected "
                "as ambiguous."
            )

        else:

            reasons.append(
                "No sufficiently reliable vendor-specific "
                "evidence was found."
            )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    result = {

        "detection": {

            "vendor":
                detected_vendor,

            "confidence":
                confidence,

            "method":
                "MULTI_SIGNAL_FILE_CONTENT_CONTAINER_FFPROBE",

            "filename_used_as_proof":
                False,

            "scores":
                final_scores
        },

        "file": {

            "name":
                file_name,

            "extension":
                file_extension,

            "size_bytes":
                file_size,

            "path":
                os.path.abspath(
                    file_path
                )
        },

        "evidence":
            final_evidence,

        "container_analysis":
            container_result,

        "ffprobe_analysis":
            ffprobe_result,

        "supported_vendors":
            SUPPORTED_VENDORS,

        "reasons":
            reasons,

        "detected_at":
            datetime.now().isoformat()
    }

    return result


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 65)
    print(
        "       TRACE X DYNAMIC VENDOR DETECTION TEST"
    )
    print("=" * 65)

    print()
    print(
        "Enter the path of ANY evidence/video file."
    )

    print()
    print(
        "Example: "
        "parser\\test_data\\your_video.mp4"
    )

    print()

    test_file = input(
        "File path: "
    ).strip().strip('"')

    if not test_file:

        print()
        print("No file path entered.")
        raise SystemExit

    try:

        result = detect_vendor(
            test_file
        )

        print()
        print("FILE")
        print("─────────────────────────────────")

        print(
            result["file"]["name"]
        )

        print(
            "Extension:",
            result["file"]["extension"]
        )

        print(
            "Size:",
            result["file"]["size_bytes"],
            "bytes"
        )

        print()
        print("VENDOR")
        print("─────────────────────────────────")

        print(
            result["detection"]["vendor"]
        )

        print()
        print("CONFIDENCE")
        print("─────────────────────────────────")

        print(
            result["detection"]["confidence"]
        )

        print()
        print("METHOD")
        print("─────────────────────────────────")

        print(
            result["detection"]["method"]
        )

        print()
        print("FILENAME USED AS PROOF")
        print("─────────────────────────────────")

        print(
            result["detection"][
                "filename_used_as_proof"
            ]
        )

        print()
        print("VENDOR SCORES")
        print("─────────────────────────────────")

        for vendor, score in (
            result["detection"]["scores"].items()
        ):

            print(
                f"{vendor:20} : {score}"
            )

        print()
        print("VENDOR EVIDENCE")
        print("─────────────────────────────────")

        if result["evidence"]:

            for vendor, matches in (
                result["evidence"].items()
            ):

                print()
                print(vendor + ":")

                for match in matches:

                    print(
                        "  -",
                        match
                    )

        else:

            print(
                "No vendor-specific evidence found."
            )

        print()
        print("CONTAINER ANALYSIS")
        print("─────────────────────────────────")

        container = result.get(
            "container_analysis"
        )

        if container:

            container_data = container.get(
                "container",
                {}
            )

            print(
                "Total boxes:",
                container_data.get(
                    "box_count",
                    0
                )
            )

            print(
                "Sequence:",
                " → ".join(
                    container_data.get(
                        "box_sequence",
                        []
                    )
                )
            )

            print(
                "Unknown boxes:",
                container_data.get(
                    "unknown_box_types",
                    []
                )
            )

        else:

            print(
                "Unavailable"
            )

        print()
        print("FFPROBE ANALYSIS")
        print("─────────────────────────────────")

        ffprobe = result.get(
            "ffprobe_analysis"
        )

        if ffprobe:

            for key in [
                "format",
                "duration",
                "bit_rate",
                "video_codec",
                "codec_tag",
                "resolution",
                "pixel_format",
                "frame_rate"
            ]:

                if key in ffprobe:

                    print(
                        f"{key}:",
                        ffprobe[key]
                    )

        else:

            print(
                "Unavailable"
            )

        print()
        print("REASONS")
        print("─────────────────────────────────")

        for reason in result["reasons"]:

            print(
                "-",
                reason
            )

        print()
        print("=" * 65)
        print(
            "                 COMPLETE"
        )
        print("=" * 65)

    except Exception as error:

        print()
        print("ERROR:")
        print(error)