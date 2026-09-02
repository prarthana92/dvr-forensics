import hashlib
import json
import os
import subprocess
from datetime import datetime


class IntegrityAssessmentEngine:
    """
    Performs a technical integrity assessment of a forensic
    evidence/video file.

    The engine checks:
    1. File existence
    2. File size
    3. MD5 and SHA-256 hashes
    4. Container validity using FFprobe
    5. Video decode completeness using OpenCV
    """

    def __init__(self, file_path):
        self.file_path = file_path

    # ---------------------------------------------------------
    # FILE INFORMATION
    # ---------------------------------------------------------

    def check_file(self):
        if not os.path.exists(self.file_path):
            return {
                "status": "FAIL",
                "exists": False,
                "size_bytes": 0
            }

        return {
            "status": "PASS",
            "exists": True,
            "size_bytes": os.path.getsize(self.file_path)
        }

    # ---------------------------------------------------------
    # HASH CALCULATION
    # ---------------------------------------------------------

    def calculate_hashes(self):
        md5 = hashlib.md5()
        sha256 = hashlib.sha256()

        with open(self.file_path, "rb") as file:
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

    # ---------------------------------------------------------
    # FFPROBE CONTAINER CHECK
    # ---------------------------------------------------------

    def check_container(self):
        ffprobe_path = r"C:\ffmpeg\ffmpeg-9.0.1-essentials_build\bin\ffprobe.exe"

        if not os.path.exists(ffprobe_path):
            return {
                "status": "UNKNOWN",
                "reason": "FFprobe executable not found."
            }

        command = [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=format_name,duration,size",
            "-show_entries",
            "stream=codec_name,width,height,r_frame_rate",
            "-of",
            "json",
            self.file_path
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "status": "FAIL",
                    "reason": result.stderr.strip() or "FFprobe failed."
                }

            data = json.loads(result.stdout)

            return {
                "status": "PASS",
                "format": data.get("format", {}),
                "streams": data.get("streams", [])
            }

        except Exception as error:
            return {
                "status": "FAIL",
                "reason": str(error)
            }

    # ---------------------------------------------------------
    # VIDEO DECODE CHECK
    # ---------------------------------------------------------

    def check_decode(self):
        try:
            import cv2
        except ImportError:
            return {
                "status": "UNKNOWN",
                "reason": "OpenCV is not installed."
            }

        capture = cv2.VideoCapture(self.file_path)

        if not capture.isOpened():
            return {
                "status": "FAIL",
                "decoded_frames": 0,
                "expected_frames": 0,
                "completeness_percent": 0.0
            }

        expected_frames = int(
            capture.get(cv2.CAP_PROP_FRAME_COUNT)
        )

        decoded_frames = 0

        while True:
            success, frame = capture.read()

            if not success:
                break

            decoded_frames += 1

        capture.release()

        if expected_frames <= 0:
            return {
                "status": "UNKNOWN",
                "decoded_frames": decoded_frames,
                "expected_frames": expected_frames,
                "completeness_percent": None
            }

        completeness = (
            decoded_frames / expected_frames
        ) * 100

        completeness = min(completeness, 100.0)

        if decoded_frames == expected_frames:
            status = "PASS"

        elif decoded_frames > 0:
            status = "PARTIAL"

        else:
            status = "FAIL"

        return {
            "status": status,
            "decoded_frames": decoded_frames,
            "expected_frames": expected_frames,
            "completeness_percent": round(
                completeness,
                2
            )
        }

    # ---------------------------------------------------------
    # OVERALL ASSESSMENT
    # ---------------------------------------------------------

    def calculate_overall_status(
        self,
        file_check,
        container_check,
        decode_check
    ):

        if file_check["status"] == "FAIL":
            return "INVALID_EVIDENCE"

        if container_check["status"] == "FAIL":
            return "DAMAGED_OR_UNREADABLE"

        if decode_check["status"] == "FAIL":
            return "SEVERELY_DAMAGED"

        if decode_check["status"] == "PARTIAL":
            return "PARTIALLY_INTACT"

        if (
            container_check["status"] == "PASS"
            and decode_check["status"] == "PASS"
        ):
            return "INTACT"

        return "INCONCLUSIVE"

    # ---------------------------------------------------------
    # FULL ASSESSMENT
    # ---------------------------------------------------------

    def assess(self):

        file_check = self.check_file()

        if not file_check["exists"]:
            return {
                "assessment_generated_at":
                    datetime.now().isoformat(),

                "file": self.file_path,

                "overall_assessment":
                    "INVALID_EVIDENCE",

                "file_check": file_check
            }

        hashes = self.calculate_hashes()

        container_check = self.check_container()

        decode_check = self.check_decode()

        overall_status = self.calculate_overall_status(
            file_check,
            container_check,
            decode_check
        )

        return {
            "assessment_generated_at":
                datetime.now().isoformat(),

            "file": self.file_path,

            "overall_assessment":
                overall_status,

            "file_check": file_check,

            "hashes": hashes,

            "container_integrity": container_check,

            "decode_integrity": decode_check
        }


# -------------------------------------------------------------
# SAVE RESULT
# -------------------------------------------------------------

def save_assessment(result, output_path):

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


# -------------------------------------------------------------
# RUN ASSESSMENT
# -------------------------------------------------------------

def run_integrity_assessment(
    file_path,
    output_path="output/integrity_assessment.json"
):

    engine = IntegrityAssessmentEngine(
        file_path
    )

    result = engine.assess()

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
    print("              FORENSIC INTEGRITY ASSESSMENT")
    print("=" * 65)

    test_file = "device/hikvision_test.mp4"

    print("\nTesting file:")
    print(test_file)

    if not os.path.exists(test_file):

        print("\nERROR:")
        print("Test file not found.")

    else:

        try:

            result = run_integrity_assessment(
                test_file
            )

            print("\nRESULT")
            print("-" * 45)

            print(
                "File status       :",
                result["file_check"]["status"]
            )

            print(
                "File size         :",
                result["file_check"]["size_bytes"],
                "bytes"
            )

            print(
                "Hash calculation  : PASS"
            )

            print(
                "Container status  :",
                result["container_integrity"]["status"]
            )

            print(
                "Decode status     :",
                result["decode_integrity"]["status"]
            )

            print(
                "Decoded frames    :",
                result["decode_integrity"]["decoded_frames"]
            )

            print(
                "Expected frames   :",
                result["decode_integrity"]["expected_frames"]
            )

            print(
                "Completeness      :",
                result["decode_integrity"]["completeness_percent"],
                "%"
            )

            print(
                "Overall assessment:",
                result["overall_assessment"]
            )

            print(
                "\nSaved to:"
                "\noutput/integrity_assessment.json"
            )

        except Exception as error:

            print("\nERROR:")
            print(error)