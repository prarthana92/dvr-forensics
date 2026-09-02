import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo


class ChainOfCustodyEngine:
    """
    Automatic forensic chain-of-custody event generator.

    Records the actual IST timestamp whenever a backend
    forensic operation is recorded.
    """

    IST = ZoneInfo("Asia/Kolkata")

    def __init__(self, evidence_id):
        self.evidence_id = evidence_id
        self.events = []

    # ---------------------------------------------------------
    # CURRENT IST TIME
    # ---------------------------------------------------------

    @classmethod
    def _current_ist_time(cls):
        now = datetime.now(cls.IST)

        return now.strftime(
            "%d-%m-%Y %I:%M:%S %p IST"
        )

    # ---------------------------------------------------------
    # ADD EVENT
    # ---------------------------------------------------------

    def add_event(
        self,
        action,
        status="COMPLETED",
        details=None
    ):
        """
        Add one forensic event with the current IST timestamp.
        """

        event_number = len(self.events) + 1

        event = {
            "event_id":
                f"{self.evidence_id}-COC-{event_number:04d}",

            "evidence_id":
                self.evidence_id,

            "timestamp":
                self._current_ist_time(),

            "action":
                action,

            "status":
                status,

            "details":
                details or {}
        }

        self.events.append(event)

        return event

    # ---------------------------------------------------------
    # STANDARD FORENSIC EVENTS
    # ---------------------------------------------------------

    def record_acquisition(
        self,
        file_path,
        file_size=None
    ):

        details = {
            "file_path": file_path
        }

        if file_size is not None:
            details["file_size_bytes"] = file_size

        return self.add_event(
            action="EVIDENCE_ACQUIRED",
            status="COMPLETED",
            details=details
        )

    def record_hashing(
        self,
        md5=None,
        sha256=None
    ):

        return self.add_event(
            action="SHA256_CALCULATED",
            status="COMPLETED",
            details={
                "md5": md5,
                "sha256": sha256
            }
        )

    def record_forensic_copy(
        self,
        copy_path=None,
        sha256=None
    ):

        details = {}

        if copy_path:
            details["copy_path"] = copy_path

        if sha256:
            details["sha256"] = sha256

        return self.add_event(
            action="FORENSIC_COPY_CREATED",
            status="COMPLETED",
            details=details
        )

    def record_integrity(
        self,
        assessment,
        completeness=None
    ):

        details = {
            "assessment": assessment
        }

        if completeness is not None:
            details[
                "completeness_percent"
            ] = completeness

        return self.add_event(
            action="INTEGRITY_VERIFIED",
            status="COMPLETED",
            details=details
        )

    def record_vendor_analysis(
        self,
        vendor,
        confidence=None
    ):

        details = {
            "vendor": vendor
        }

        if confidence is not None:
            details[
                "confidence"
            ] = confidence

        return self.add_event(
            action="VENDOR_DETECTION_PERFORMED",
            status="COMPLETED",
            details=details
        )

    def record_ai_analysis(
        self,
        ai_status="RECEIVED"
    ):

        return self.add_event(
            action="AI_ANALYSIS_RECEIVED",
            status=ai_status
        )

    def record_correlation(
        self,
        total_events=0
    ):

        return self.add_event(
            action="EVIDENCE_CORRELATION_PERFORMED",
            status="COMPLETED",
            details={
                "correlated_events":
                    total_events
            }
        )

    def record_recovery_attempt(
        self,
        status="ATTEMPTED",
        details=None
    ):

        return self.add_event(
            action="RECOVERY_ATTEMPTED",
            status=status,
            details=details
        )

    def record_recovery_validation(
        self,
        status="COMPLETED",
        details=None
    ):

        return self.add_event(
            action="RECOVERY_VALIDATED",
            status=status,
            details=details
        )

    def record_report_generation(
        self,
        report_path=None
    ):

        details = {}

        if report_path:
            details[
                "report_path"
            ] = report_path

        return self.add_event(
            action="REPORT_GENERATED",
            status="COMPLETED",
            details=details
        )

    # ---------------------------------------------------------
    # BUILD RESULT
    # ---------------------------------------------------------

    def build_result(self):

        return {
            "evidence_id":
                self.evidence_id,

            "chain_of_custody_generated_at":
                self._current_ist_time(),

            "timezone":
                "Asia/Kolkata",

            "total_events":
                len(self.events),

            "events":
                self.events
        }


# -------------------------------------------------------------
# SAVE
# -------------------------------------------------------------

def save_chain_of_custody(
    result,
    output_path="output/chain_of_custody.json"
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
            indent=2,
            ensure_ascii=False
        )


# -------------------------------------------------------------
# TEST
# -------------------------------------------------------------

if __name__ == "__main__":

    print("=" * 70)
    print("             AUTOMATIC CHAIN OF CUSTODY")
    print("=" * 70)

    evidence_id = "EVD-COC-TEST"

    engine = ChainOfCustodyEngine(
        evidence_id
    )

    print("\nRecording forensic event timeline...\n")

    engine.record_acquisition(
        file_path="device/hikvision_test.mp4",
        file_size=1727518
    )

    engine.record_hashing(
        md5="bb8a35b57a137d5140ad59ddbed2b507",
        sha256=
            "c1ff46b6e53957dd27ef7013be74d11a106544424e654b03513316a97cb3d695"
    )

    engine.record_forensic_copy(
        copy_path="output/forensic_copy/hikvision_test.mp4",
        sha256=
            "c1ff46b6e53957dd27ef7013be74d11a106544424e654b03513316a97cb3d695"
    )

    engine.record_integrity(
        assessment="INTACT",
        completeness=100.0
    )

    engine.record_vendor_analysis(
        vendor="UNKNOWN",
        confidence="LOW"
    )

    engine.record_ai_analysis(
        ai_status="RECEIVED"
    )

    engine.record_correlation(
        total_events=2
    )

    engine.record_report_generation(
        report_path="output/forensic_report.pdf"
    )

    result = engine.build_result()

    save_chain_of_custody(
        result
    )

    # ---------------------------------------------------------
    # DISPLAY TIMELINE
    # ---------------------------------------------------------

    print("=" * 70)
    print("FORENSIC EVENT TIMELINE")
    print("=" * 70)

    for event in result["events"]:

        readable_action = event["action"].replace(
            "_",
            " "
        ).title()

        print(
            f"{event['timestamp']}  |  "
            f"{readable_action}"
        )

    print("\n" + "=" * 70)

    print(
        f"Evidence ID : {result['evidence_id']}"
    )

    print(
        f"Total events: {result['total_events']}"
    )

    print(
        "\nSaved to:"
        "\noutput/chain_of_custody.json"
    )