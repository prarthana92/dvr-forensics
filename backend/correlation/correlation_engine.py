import json
import os
from datetime import datetime


class EvidenceCorrelationEngine:
    """
    Correlates AI detections into a chronological
    forensic event timeline.
    """

    def __init__(self, evidence_id):
        self.evidence_id = evidence_id

    def _normalize_event(self, event, index):
        if not isinstance(event, dict):
            return None

        frame = event.get("frame")

        timestamp = (
            event.get("timestamp_seconds")
            or event.get("timestamp")
            or event.get("time")
        )

        try:
            timestamp = float(timestamp) if timestamp is not None else None
        except (ValueError, TypeError):
            timestamp = None

        detections = event.get("detections", [])

        if not isinstance(detections, list):
            detections = [detections] if detections else []

        event_type = str(
            event.get("event_type")
            or event.get("type")
            or event.get("label")
            or ""
        ).lower()

        # Start with top-level flags
        motion = (
            event.get("motion") is True
            or event.get("motion_detected") is True
            or "motion" in event_type
        )

        face = (
            event.get("face") is True
            or event.get("face_detected") is True
            or "face" in event_type
        )

        anomaly = (
            event.get("anomaly") is True
            or event.get("anomaly_detected") is True
            or "anomaly" in event_type
        )

        object_detected = (
            event.get("object") is not None
            or event.get("object_detected") is True
            or "object" in event_type
        )

        # Inspect nested detections
        for detection in detections:

            if not isinstance(detection, dict):
                continue

            detection_type = str(
                detection.get("type")
                or detection.get("event_type")
                or detection.get("label")
                or ""
            ).lower()

            if "motion" in detection_type:
                motion = True

            if "face" in detection_type:
                face = True

            if "anomaly" in detection_type:
                anomaly = True

            if "object" in detection_type:
                object_detected = True

            # A person/car/etc. is also an object detection
            if detection.get("confidence") is not None:
                label = str(
                    detection.get("label", "")
                ).lower()

                if label in {
                    "person",
                    "car",
                    "vehicle",
                    "bicycle",
                    "motorcycle",
                    "truck",
                    "bus",
                    "animal",
                }:
                    object_detected = True

        summary = event.get("summary")

        if not summary:

            detected_types = []

            if motion:
                detected_types.append("motion")

            if object_detected:
                detected_types.append("object")

            if face:
                detected_types.append("face")

            if anomaly:
                detected_types.append("anomaly")

            if detected_types:
                summary = " + ".join(detected_types).title()
            else:
                summary = "AI detected event"

        return {
            "event_id": f"{self.evidence_id}-EVT-{index:04d}",
            "evidence_id": self.evidence_id,
            "frame": frame,
            "timestamp_seconds": timestamp,
            "camera_id": event.get("camera_id"),
            "summary": summary,
            "event_type": event_type or "unknown",
            "motion_detected": motion,
            "face_detected": face,
            "anomaly_detected": anomaly,
            "object_detected": object_detected,
            "detections": detections,
        }

    def correlate(self, ai_results):

        events = []

        if isinstance(ai_results, list):
            raw_events = ai_results

        elif isinstance(ai_results, dict):
            raw_events = (
                ai_results.get("events")
                or ai_results.get("results")
                or ai_results.get("detections")
                or []
            )

        else:
            raw_events = []

        for index, event in enumerate(raw_events, start=1):

            normalized = self._normalize_event(
                event,
                index
            )

            if normalized:
                events.append(normalized)

        # Chronological ordering
        events.sort(
            key=lambda event: (
                event["timestamp_seconds"] is None,
                event["timestamp_seconds"]
                if event["timestamp_seconds"] is not None
                else float("inf"),
            )
        )

        # Re-number after sorting
        for index, event in enumerate(events, start=1):

            event["event_id"] = (
                f"{self.evidence_id}-EVT-{index:04d}"
            )

        summary = {
            "total_events": len(events),
            "motion_events": sum(
                1 for event in events
                if event["motion_detected"]
            ),
            "object_events": sum(
                1 for event in events
                if event["object_detected"]
            ),
            "face_events": sum(
                1 for event in events
                if event["face_detected"]
            ),
            "anomaly_events": sum(
                1 for event in events
                if event["anomaly_detected"]
            ),
        }

        return {
            "evidence_id": self.evidence_id,
            "correlation_generated_at": datetime.now().isoformat(),
            "summary": summary,
            "events": events,
        }


def load_ai_results(file_path):

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"AI results file not found: {file_path}"
        )

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def save_correlation_result(
    result,
    output_path
):

    directory = os.path.dirname(output_path)

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


def run_correlation(
    evidence_id,
    ai_results_path="output/ai_results.json",
    output_path="output/correlation_result.json",
):

    ai_results = load_ai_results(
        ai_results_path
    )

    engine = EvidenceCorrelationEngine(
        evidence_id
    )

    result = engine.correlate(
        ai_results
    )

    save_correlation_result(
        result,
        output_path
    )

    return result


if __name__ == "__main__":

    print("=" * 65)
    print("              EVIDENCE CORRELATION ENGINE")
    print("=" * 65)

    evidence_id = "EVD-CORR-TEST"

    ai_file = "output/ai_results.json"

    if os.path.exists(ai_file):

        print("\nLoading AI results...")
        print(f"File: {ai_file}")

        try:

            result = run_correlation(
                evidence_id=evidence_id,
                ai_results_path=ai_file,
                output_path="output/correlation_result.json",
            )

            print("\nCorrelation completed.")

            print("\nSUMMARY")
            print("-" * 40)

            for key, value in result["summary"].items():
                print(f"{key}: {value}")

            print(
                f"\nEvents generated: "
                f"{len(result['events'])}"
            )

            print(
                "\nSaved to:"
                "\noutput/correlation_result.json"
            )

        except Exception as error:

            print("\nERROR:")
            print(error)

    else:

        print("\nAI results file not found:")
        print(ai_file)

        print(
            "\nMake sure output/ai_results.json "
            "exists before running the test."
        )