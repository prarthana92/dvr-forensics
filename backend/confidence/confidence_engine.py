import json
import os
from datetime import datetime


class ConfidenceReliabilityEngine:
    """
    Calculates a transparent reliability assessment for forensic
    evidence and AI detections.

    The engine does NOT perform AI detection.

    It evaluates:
    - AI confidence
    - Evidence integrity
    - Video completeness
    - Detection quality
    """

    def __init__(self, evidence_id):
        self.evidence_id = evidence_id

    # ---------------------------------------------------------
    # AI CONFIDENCE
    # ---------------------------------------------------------

    def calculate_ai_confidence(self, ai_results):
        """
        Extract confidence values from AI detections.

        Returns the average confidence as a percentage.
        """

        confidence_values = []

        if isinstance(ai_results, list):
            events = ai_results

        elif isinstance(ai_results, dict):
            events = (
                ai_results.get("events")
                or ai_results.get("results")
                or ai_results.get("detections")
                or []
            )

        else:
            events = []

        for event in events:

            if not isinstance(event, dict):
                continue

            detections = event.get("detections", [])

            if not isinstance(detections, list):
                detections = [detections] if detections else []

            # Check event-level confidence
            event_confidence = event.get("confidence")

            if event_confidence is not None:
                try:
                    value = float(event_confidence)

                    if 0 <= value <= 1:
                        confidence_values.append(value)

                    elif 1 < value <= 100:
                        confidence_values.append(value / 100)

                except (ValueError, TypeError):
                    pass

            # Check nested detections
            for detection in detections:

                if not isinstance(detection, dict):
                    continue

                confidence = detection.get("confidence")

                if confidence is None:
                    continue

                try:
                    value = float(confidence)

                    if 0 <= value <= 1:
                        confidence_values.append(value)

                    elif 1 < value <= 100:
                        confidence_values.append(value / 100)

                except (ValueError, TypeError):
                    continue

        if not confidence_values:
            return {
                "status": "UNKNOWN",
                "average_confidence_percent": None,
                "detections_with_confidence": 0
            }

        average = (
            sum(confidence_values)
            / len(confidence_values)
        ) * 100

        return {
            "status": "AVAILABLE",
            "average_confidence_percent": round(
                average,
                2
            ),
            "detections_with_confidence":
                len(confidence_values)
        }

    # ---------------------------------------------------------
    # EVIDENCE INTEGRITY
    # ---------------------------------------------------------

    def evaluate_integrity(self, integrity_result):

        if not isinstance(integrity_result, dict):
            return {
                "status": "UNKNOWN",
                "score": None
            }

        overall = integrity_result.get(
            "overall_assessment"
        )

        decode = integrity_result.get(
            "decode_integrity",
            {}
        )

        completeness = decode.get(
            "completeness_percent"
        )

        if overall == "INTACT":
            return {
                "status": "PASS",
                "score": 100.0
            }

        if overall == "PARTIALLY_INTACT":

            if completeness is not None:
                return {
                    "status": "PARTIAL",
                    "score": round(
                        float(completeness),
                        2
                    )
                }

            return {
                "status": "PARTIAL",
                "score": 50.0
            }

        if overall in {
            "DAMAGED_OR_UNREADABLE",
            "SEVERELY_DAMAGED"
        }:
            return {
                "status": "FAIL",
                "score": 0.0
            }

        return {
            "status": "UNKNOWN",
            "score": None
        }

    # ---------------------------------------------------------
    # RELIABILITY CALCULATION
    # ---------------------------------------------------------

    def calculate_reliability(
        self,
        ai_confidence,
        integrity
    ):

        ai_score = ai_confidence.get(
            "average_confidence_percent"
        )

        integrity_score = integrity.get(
            "score"
        )

        if ai_score is None:
            return {
                "score": None,
                "level": "INCONCLUSIVE",
                "reason":
                    "AI confidence information is unavailable."
            }

        if integrity_score is None:
            return {
                "score": None,
                "level": "INCONCLUSIVE",
                "reason":
                    "Evidence integrity information is unavailable."
            }

        # Weighted calculation:
        # AI confidence = 60%
        # Evidence integrity = 40%

        reliability_score = (
            (ai_score * 0.60)
            + (integrity_score * 0.40)
        )

        reliability_score = round(
            reliability_score,
            2
        )

        if reliability_score >= 80:
            level = "HIGH"

        elif reliability_score >= 60:
            level = "MODERATE"

        elif reliability_score >= 40:
            level = "LOW"

        else:
            level = "VERY_LOW"

        return {
            "score": reliability_score,
            "level": level,
            "reason":
                "Reliability combines AI confidence "
                "and evidence integrity."
        }

    # ---------------------------------------------------------
    # FULL ASSESSMENT
    # ---------------------------------------------------------

    def assess(
        self,
        ai_results,
        integrity_result
    ):

        ai_confidence = (
            self.calculate_ai_confidence(
                ai_results
            )
        )

        integrity = (
            self.evaluate_integrity(
                integrity_result
            )
        )

        reliability = (
            self.calculate_reliability(
                ai_confidence,
                integrity
            )
        )

        return {
            "assessment_generated_at":
                datetime.now().isoformat(),

            "evidence_id":
                self.evidence_id,

            "ai_confidence":
                ai_confidence,

            "evidence_integrity":
                integrity,

            "overall_reliability":
                reliability
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

def save_assessment(
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

def run_confidence_assessment(
    evidence_id,
    ai_results_path="output/ai_results.json",
    integrity_path="output/integrity_assessment.json",
    output_path="output/confidence_assessment.json"
):

    ai_results = load_json(
        ai_results_path
    )

    integrity_result = load_json(
        integrity_path
    )

    engine = ConfidenceReliabilityEngine(
        evidence_id
    )

    result = engine.assess(
        ai_results,
        integrity_result
    )

    save_assessment(
        result,
        output_path
    )

    return result


# -------------------------------------------------------------
# TEST
# -------------------------------------------------------------

if __name__ == "__main__":

    print("=" * 65)
    print("          CONFIDENCE / RELIABILITY ENGINE")
    print("=" * 65)

    evidence_id = "EVD-CONF-TEST"

    ai_file = "output/ai_results.json"
    integrity_file = (
        "output/integrity_assessment.json"
    )

    if not os.path.exists(ai_file):

        print("\nERROR:")
        print(
            "AI results not found:"
            f" {ai_file}"
        )

    elif not os.path.exists(integrity_file):

        print("\nERROR:")
        print(
            "Integrity assessment not found:"
            f" {integrity_file}"
        )

    else:

        try:

            result = run_confidence_assessment(
                evidence_id=evidence_id,
                ai_results_path=ai_file,
                integrity_path=integrity_file,
                output_path=
                    "output/confidence_assessment.json"
            )

            print("\nRESULT")
            print("-" * 45)

            ai = result["ai_confidence"]
            integrity = result[
                "evidence_integrity"
            ]
            reliability = result[
                "overall_reliability"
            ]

            print(
                "AI confidence     :",
                ai[
                    "average_confidence_percent"
                ],
                "%"
            )

            print(
                "Evidence integrity:",
                integrity["status"]
            )

            print(
                "Integrity score    :",
                integrity["score"]
            )

            print(
                "Reliability score  :",
                reliability["score"]
            )

            print(
                "Reliability level  :",
                reliability["level"]
            )

            print(
                "\nSaved to:"
                "\noutput/confidence_assessment.json"
            )

        except Exception as error:

            print("\nERROR:")
            print(error)