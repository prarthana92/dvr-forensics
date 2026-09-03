import hashlib
import json
import os
import subprocess
from datetime import datetime


class EvidenceFingerprintEngine:
    """
    Generates a technical fingerprint for forensic evidence.

    The fingerprint combines stable file characteristics so that
    evidence can be identified and compared without relying only
    on the filename.
    """

    def __init__(self, file_path, evidence_id="EVD-UNKNOWN"):
        self.file_path = file_path
        self.evidence_id = evidence_id

    # ---------------------------------------------------------
    # HASH
    # ---------------------------------------------------------

    def calculate_sha256(self):
        sha256 = hashlib.sha256()

        with open(self.file_path, "rb") as file:
            while True:
                chunk = file.read(1024 * 1024)

                if not chunk:
                    break

                sha256.update(chunk)

        return sha256.hexdigest()

    # ---------------------------------------------------------
    # FFPROBE
    # ---------------------------------------------------------

    def get_media_metadata(self):

        ffprobe_path = (
            r"C:\ffmpeg\ffmpeg-9.0.1-essentials_build"
            r"\bin\ffprobe.exe"
        )

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
            (
                "format=format_name,duration,size,"
                "bit_rate:stream=codec_type,codec_name,"
                "width,height,r_frame_rate"
            ),
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
                    "reason": result.stderr.strip()
                }

            data = json.loads(result.stdout)

            format_data = data.get(
                "format",
                {}
            )

            streams = data.get(
                "streams",
                []
            )

            video_stream = None

            for stream in streams:

                if stream.get("codec_type") == "video":
                    video_stream = stream
                    break

            if video_stream is None:
                video_stream = {}

            return {
                "status": "PASS",

                "container":
                    format_data.get("format_name"),

                "duration_seconds":
                    self._safe_float(
                        format_data.get("duration")
                    ),

                "bitrate":
                    self._safe_int(
                        format_data.get("bit_rate")
                    ),

                "codec":
                    video_stream.get("codec_name"),

                "width":
                    video_stream.get("width"),

                "height":
                    video_stream.get("height"),

                "frame_rate":
                    video_stream.get("r_frame_rate")
            }

        except Exception as error:

            return {
                "status": "FAIL",
                "reason": str(error)
            }

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def _safe_float(value):

        try:
            return float(value)

        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(value):

        try:
            return int(value)

        except (ValueError, TypeError):
            return None

    # ---------------------------------------------------------
    # FINGERPRINT STRING
    # ---------------------------------------------------------

    def generate_fingerprint(self, sha256, metadata):

        fingerprint_source = "|".join(
            [
                sha256,
                str(
                    os.path.getsize(
                        self.file_path
                    )
                ),
                str(
                    metadata.get("container")
                ),
                str(
                    metadata.get("codec")
                ),
                str(
                    metadata.get("width")
                ),
                str(
                    metadata.get("height")
                ),
                str(
                    metadata.get("duration_seconds")
                ),
                str(
                    metadata.get("frame_rate")
                )
            ]
        )

        fingerprint = hashlib.sha256(
            fingerprint_source.encode("utf-8")
        ).hexdigest()

        return {
            "fingerprint": fingerprint,
            "source_components": {
                "sha256": sha256,
                "size_bytes":
                    os.path.getsize(
                        self.file_path
                    ),
                "container":
                    metadata.get("container"),
                "codec":
                    metadata.get("codec"),
                "width":
                    metadata.get("width"),
                "height":
                    metadata.get("height"),
                "duration_seconds":
                    metadata.get(
                        "duration_seconds"
                    ),
                "frame_rate":
                    metadata.get("frame_rate")
            }
        }

    # ---------------------------------------------------------
    # FULL ASSESSMENT
    # ---------------------------------------------------------

    def generate(self):

        if not os.path.exists(self.file_path):

            raise FileNotFoundError(
                f"Evidence file not found: "
                f"{self.file_path}"
            )

        file_size = os.path.getsize(
            self.file_path
        )

        sha256 = self.calculate_sha256()

        metadata = self.get_media_metadata()

        if metadata["status"] == "PASS":

            fingerprint_data = (
                self.generate_fingerprint(
                    sha256,
                    metadata
                )
            )

        else:

            fingerprint_data = {
                "fingerprint": None,
                "source_components": {
                    "sha256": sha256,
                    "size_bytes": file_size
                }
            }

        return {
            "fingerprint_generated_at":
                datetime.now().isoformat(),

            "evidence_id":
                self.evidence_id,

            "file":
                self.file_path,

            "file_size_bytes":
                file_size,

            "sha256":
                sha256,

            "media_metadata":
                metadata,

            "fingerprint":
                fingerprint_data["fingerprint"],

            "fingerprint_components":
                fingerprint_data[
                    "source_components"
                ]
        }


# -------------------------------------------------------------
# SAVE
# -------------------------------------------------------------

def save_fingerprint(
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

def run_fingerprint(
    file_path,
    evidence_id="EVD-UNKNOWN",
    output_path="output/evidence_fingerprint.json"
):

    engine = EvidenceFingerprintEngine(
        file_path,
        evidence_id
    )

    result = engine.generate()

    save_fingerprint(
        result,
        output_path
    )

    return result


# -------------------------------------------------------------
# TEST
# -------------------------------------------------------------

if __name__ == "__main__":

    print("=" * 65)
    print("                 EVIDENCE FINGERPRINT")
    print("=" * 65)

    test_file = "device/hikvision_test.mp4"

    evidence_id = "EVD-FINGERPRINT-TEST"

    print("\nTesting file:")
    print(test_file)

    if not os.path.exists(test_file):

        print("\nERROR:")
        print("Test file not found.")

    else:

        try:

            result = run_fingerprint(
                file_path=test_file,
                evidence_id=evidence_id,
                output_path=
                    "output/evidence_fingerprint.json"
            )

            print("\nRESULT")
            print("-" * 45)

            print(
                "Evidence ID :",
                result["evidence_id"]
            )

            print(
                "File size   :",
                result["file_size_bytes"],
                "bytes"
            )

            print(
                "SHA-256     :",
                result["sha256"]
            )

            metadata = result[
                "media_metadata"
            ]

            print(
                "Container   :",
                metadata.get("container")
            )

            print(
                "Codec       :",
                metadata.get("codec")
            )

            print(
                "Resolution  :",
                f"{metadata.get('width')} x "
                f"{metadata.get('height')}"
            )

            print(
                "Duration    :",
                metadata.get(
                    "duration_seconds"
                ),
                "seconds"
            )

            print(
                "Frame rate  :",
                metadata.get("frame_rate")
            )

            print(
                "Fingerprint :",
                result["fingerprint"]
            )

            print(
                "\nSaved to:"
                "\noutput/evidence_fingerprint.json"
            )

        except Exception as error:

            print("\nERROR:")
            print(error)