import json
import os


VENDOR_SIGNATURE_FILE = (
    "vendor_signatures/vendor_signatures.json"
)


def load_vendor_signatures():

    if not os.path.exists(
        VENDOR_SIGNATURE_FILE
    ):
        raise FileNotFoundError(
            "Vendor signature database not found."
        )

    with open(
        VENDOR_SIGNATURE_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def compare_features(
    fingerprint,
    vendor_features
):

    score = 0
    reasons = []

    # --------------------------------------------------------
    # Container features
    # --------------------------------------------------------

    container = fingerprint.get(
        "container",
        {}
    )

    box_sequence = container.get(
        "box_sequence",
        []
    )

    box_counts = container.get(
        "box_counts",
        {}
    )

    metadata = fingerprint.get(
        "metadata",
        {}
    )

    # --------------------------------------------------------
    # FTYP
    # --------------------------------------------------------

    ftyp = metadata.get(
        "ftyp",
        {}
    )

    major_brand = ftyp.get(
        "major_brand"
    )

    expected_brand = vendor_features.get(
        "major_brand"
    )

    if (
        expected_brand
        and major_brand == expected_brand
    ):

        score += 10

        reasons.append(
            f"Major brand matched: {major_brand}"
        )

    # --------------------------------------------------------
    # Codec / sample entry
    # --------------------------------------------------------

    sample_descriptions = metadata.get(
        "sample_descriptions",
        []
    )

    expected_codec = vendor_features.get(
        "sample_entry"
    )

    if expected_codec:

        for description in sample_descriptions:

            for entry in description.get(
                "sample_entries",
                []
            ):

                if entry.get(
                    "type"
                ) == expected_codec:

                    score += 10

                    reasons.append(
                        f"Sample entry matched: {expected_codec}"
                    )

    # --------------------------------------------------------
    # Handler type
    # --------------------------------------------------------

    handlers = metadata.get(
        "handlers",
        []
    )

    expected_handler = vendor_features.get(
        "handler_type"
    )

    if expected_handler:

        for handler in handlers:

            if handler.get(
                "handler_type"
            ) == expected_handler:

                score += 5

                reasons.append(
                    f"Handler matched: {expected_handler}"
                )

    # --------------------------------------------------------
    # Required boxes
    # --------------------------------------------------------

    required_boxes = vendor_features.get(
        "required_boxes",
        []
    )

    for required_box in required_boxes:

        if required_box in box_sequence:

            score += 5

            reasons.append(
                f"Container box present: {required_box}"
            )

    # --------------------------------------------------------
    # Unknown/custom boxes
    # --------------------------------------------------------

    expected_custom_boxes = vendor_features.get(
        "custom_boxes",
        []
    )

    unknown_boxes = container.get(
        "unknown_box_types",
        []
    )

    for custom_box in expected_custom_boxes:

        if custom_box in unknown_boxes:

            score += 10

            reasons.append(
                f"Custom box matched: {custom_box}"
            )

    return score, reasons


def calculate_vendor_scores(
    fingerprint
):

    signatures = load_vendor_signatures()

    results = []

    for vendor, information in signatures.items():

        # ----------------------------------------------------
        # Never score an unvalidated vendor signature
        # ----------------------------------------------------

        if not information.get(
            "validated",
            False
        ):

            results.append({
                "vendor": vendor,
                "score": 0,
                "confidence": "UNVALIDATED",
                "reasons": [
                    "No validated reference signature available."
                ]
            })

            continue

        score, reasons = compare_features(
            fingerprint,
            information.get(
                "features",
                {}
            )
        )

        if score >= 30:

            confidence = "HIGH"

        elif score >= 15:

            confidence = "MEDIUM"

        elif score > 0:

            confidence = "LOW"

        else:

            confidence = "NONE"

        results.append({
            "vendor": vendor,
            "score": score,
            "confidence": confidence,
            "reasons": reasons
        })

    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return results


def determine_best_vendor(
    results
):

    if not results:

        return {
            "vendor": "UNKNOWN",
            "confidence": "NONE",
            "score": 0,
            "reasons": [
                "No vendor results available."
            ]
        }

    best = results[0]

    if (
        best["confidence"]
        in ["NONE", "UNVALIDATED"]
    ):

        return {
            "vendor": "UNKNOWN",
            "confidence": "LOW",
            "score": best["score"],
            "reasons": [
                "Insufficient validated vendor-specific evidence."
            ]
        }

    return {
        "vendor": best["vendor"],
        "confidence": best["confidence"],
        "score": best["score"],
        "reasons": best["reasons"]
    }


if __name__ == "__main__":

    print()
    print("=" * 65)
    print(
        "             TRACE X VENDOR SCORING"
    )
    print("=" * 65)

    fingerprint_file = (
        "output/container_fingerprint.json"
    )

    if not os.path.exists(
        fingerprint_file
    ):

        print()
        print(
            "ERROR: Fingerprint file not found."
        )

        print(
            "Run container_fingerprint.py first."
        )

        raise SystemExit

    with open(
        fingerprint_file,
        "r",
        encoding="utf-8"
    ) as file:

        fingerprint = json.load(file)

    results = calculate_vendor_scores(
        fingerprint
    )

    print()

    print("VENDOR RESULTS")
    print("─────────────────────────────────")

    for result in results:

        print(
            f"{result['vendor']:20} "
            f"Score: {result['score']:3} "
            f"Confidence: {result['confidence']}"
        )

    best = determine_best_vendor(
        results
    )

    print()
    print("FINAL RESULT")
    print("─────────────────────────────────")

    print(
        "Vendor:",
        best["vendor"]
    )

    print(
        "Confidence:",
        best["confidence"]
    )

    print(
        "Score:",
        best["score"]
    )

    print()
    print(
        "Important: vendor identification requires "
        "validated reference signatures."
    )

    print()
    print("=" * 65)