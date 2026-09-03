import json
import os
from datetime import datetime


class ForensicDecisionEngine:
    """
    Automatically decides the recommended forensic workflow
    based on evidence integrity and vendor detection.

    This engine does NOT perform detection or recovery itself.
    It decides what should happen next.
    """

    def __init__(self, evidence_id):
        self.evidence_id = evidence_id

    # ---------------------------------------------------------
    # NORMALIZE VENDOR
    # ---------------------------------------------------------

    def get_vendor(self, vendor_result):

        if not isinstance(vendor_result, dict):
            return "UNKNOWN"

        detection = vendor_result.get(
            "detection",
            {}
        )

        if isinstance(detection, dict):

            vendor = detection.get(
                "vendor"
            )

            if vendor:
                return str(vendor).upper()

        vendor = vendor_result.get(
            "vendor"
        )

        if vendor:
            return str(vendor).upper()

        return "UNKNOWN"

    # ---------------------------------------------------------
    # GET INTEGRITY
    # ---------------------------------------------------------

    def get_integrity(
        self,
        integrity_result
    ):

        if not isinstance(
            integrity_result,
            dict
        ):
            return {
                "overall": "INCONCLUSIVE",
                "decode_status": "UNKNOWN",
                "completeness": None
            }

        overall = integrity_result.get(
            "overall_assessment",
            "INCONCLUSIVE"
        )

        decode = integrity_result.get(
            "decode_integrity",
            {}
        )

        if not isinstance(decode, dict):
            decode = {}

        return {
            "overall": overall,
            "decode_status":
                decode.get(
                    "status",
                    "UNKNOWN"
                ),
            "completeness":
                decode.get(
                    "completeness_percent"
                )
        }

    # ---------------------------------------------------------
    # DECISION
    # ---------------------------------------------------------

    def decide(
        self,
        vendor_result,
        integrity_result
    ):

        vendor = self.get_vendor(
            vendor_result
        )

        integrity = self.get_integrity(
            integrity_result
        )

        overall = integrity["overall"]
        decode_status = integrity[
            "decode_status"
        ]
        completeness = integrity[
            "completeness"
        ]

        actions = []
        reasons = []

        # -----------------------------------------------------
        # INVALID EVIDENCE
        # -----------------------------------------------------

        if overall == "INVALID_EVIDENCE":

            actions.append(
                "REJECT_INVALID_EVIDENCE"
            )

            reasons.append(
                "Evidence file does not exist "
                "or is invalid."
            )

            priority = "CRITICAL"

        # -----------------------------------------------------
        # SEVERELY DAMAGED
        # -----------------------------------------------------

        elif overall in {
            "DAMAGED_OR_UNREADABLE",
            "SEVERELY_DAMAGED"
        }:

            actions.append(
                "RECOVERY_REQUIRED"
            )

            reasons.append(
                "Evidence cannot be reliably "
                "decoded."
            )

            priority = "HIGH"

        # -----------------------------------------------------
        # PARTIALLY INTACT
        # -----------------------------------------------------

        elif overall == "PARTIALLY_INTACT":

            actions.append(
                "RECOVERY_RECOMMENDED"
            )

            reasons.append(
                "Evidence is only partially "
                "decodable."
            )

            if completeness is not None:

                reasons.append(
                    f"Video completeness is "
                    f"{completeness}%."
                )

            priority = "HIGH"

        # -----------------------------------------------------
        # INTACT
        # -----------------------------------------------------

        elif overall == "INTACT":

            actions.append(
                "NORMAL_FORENSIC_ANALYSIS"
            )

            reasons.append(
                "Evidence passed integrity "
                "and decode checks."
            )

            priority = "NORMAL"

        # -----------------------------------------------------
        # UNKNOWN
        # -----------------------------------------------------

        else:

            actions.append(
                "MANUAL_REVIEW"
            )

            reasons.append(
                "Evidence integrity could not "
                "be conclusively determined."
            )

            priority = "MEDIUM"

        # -----------------------------------------------------
        # VENDOR DECISION
        # -----------------------------------------------------

        if vendor == "UNKNOWN":

            actions.append(
                "USE_GENERIC_PARSER"
            )

            reasons.append(
                "Vendor could not be reliably "
                "identified. Do not guess the vendor."
            )

        else:

            actions.append(
                "USE_VENDOR_SPECIFIC_ANALYSIS"
            )

            reasons.append(
                f"Detected vendor: {vendor}."
            )

        # -----------------------------------------------------
        # RECOVERY OVERRIDE
        # -----------------------------------------------------

        recovery_required = any(
            action in {
                "RECOVERY_REQUIRED",
                "RECOVERY_RECOMMENDED"
            }
            for action in actions
        )

        if recovery_required:

            actions.append(
                "PRESERVE_ORIGINAL_EVIDENCE"
            )

            reasons.append(
                "Original evidence should be "
                "preserved before recovery operations."
            )

        # -----------------------------------------------------
        # FINAL DECISION
        # -----------------------------------------------------

        if recovery_required:

            primary_decision = (
                "RECOVERY_WORKFLOW"
            )

        elif (
            "NORMAL_FORENSIC_ANALYSIS"
            in actions
        ):

            primary_decision = (
                "STANDARD_FORENSIC_WORKFLOW"
            )

        elif (
            "REJECT_INVALID_EVIDENCE"
            in actions
        ):

            primary_decision = (
                "INVALID_EVIDENCE"
            )

        else:

            primary_decision = (
                "MANUAL_REVIEW"
            )

        return {
            "evidence_id":
                self.evidence_id,

            "decision_generated_at":
                datetime.now().isoformat(),

            "primary_decision":
                primary_decision,

            "priority":
                priority,

            "vendor":
                vendor,

            "integrity":
                integrity,

            "recommended_actions":
                actions,

            "reasons":
                reasons
        }


# -------------------------------------------------------------
# LOAD JSON
# -------------------------------------------------------------

def load_json(file_path):

    if not os.path.exists(file_path):

        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# -------------------------------------------------------------
# SAVE JSON
# -------------------------------------------------------------

def save_decision(
    result,
    output_path
):

    directory = os.path.dirname(
        output_path
    )

    if directory:

        os.makedirs(
            directory,
            exist_ok=True
        )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            indent=2
        )


# -------------------------------------------------------------
# RUN
# -------------------------------------------------------------

def run_decision(
    evidence_id,
    vendor_path="output/vendor_detection.json",
    integrity_path=
        "output/integrity_assessment.json",
    output_path=
        "output/forensic_decision.json"
):

    vendor_result = load_json(
        vendor_path
    )

    integrity_result = load_json(
        integrity_path
    )

    engine = ForensicDecisionEngine(
        evidence_id
    )

    result = engine.decide(
        vendor_result,
        integrity_result
    )

    save_decision(
        result,
        output_path
    )

    return result


# -------------------------------------------------------------
# TEST
# -------------------------------------------------------------

if __name__ == "__main__":

    print("=" * 65)
    print("              FORENSIC DECISION ENGINE")
    print("=" * 65)

    evidence_id = "EVD-DECISION-TEST"

    vendor_file = (
        "output/vendor_detection.json"
    )

    integrity_file = (
        "output/integrity_assessment.json"
    )

    if not os.path.exists(vendor_file):

        print("\nERROR:")
        print(
            "Vendor detection file not found:"
        )
        print(vendor_file)

    elif not os.path.exists(
        integrity_file
    ):

        print("\nERROR:")
        print(
            "Integrity assessment file "
            "not found:"
        )
        print(integrity_file)

    else:

        try:

            result = run_decision(
                evidence_id=evidence_id,
                vendor_path=vendor_file,
                integrity_path=integrity_file,
                output_path=
                    "output/forensic_decision.json"
            )

            print("\nRESULT")
            print("-" * 45)

            print(
                "Primary decision :",
                result[
                    "primary_decision"
                ]
            )

            print(
                "Priority         :",
                result["priority"]
            )

            print(
                "Vendor           :",
                result["vendor"]
            )

            print(
                "Integrity        :",
                result[
                    "integrity"
                ]["overall"]
            )

            print("\nRecommended actions:")

            for action in result[
                "recommended_actions"
            ]:

                print(
                    f"  - {action}"
                )

            print("\nReasons:")

            for reason in result[
                "reasons"
            ]:

                print(
                    f"  - {reason}"
                )

            print(
                "\nSaved to:"
                "\noutput/forensic_decision.json"
            )

        except Exception as error:

            print("\nERROR:")
            print(error)