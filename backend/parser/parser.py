import os
import json


def identify_video_format(file_extension):

    video_formats = {
        ".mp4": "MP4",
        ".avi": "AVI",
        ".mkv": "MKV",
        ".mov": "MOV",
        ".ts": "MPEG-TS",
        ".dav": "DAV",
        ".264": "H.264 Raw Video",
        ".h264": "H.264 Raw Video"
    }

    return video_formats.get(
        file_extension,
        "UNKNOWN"
    )


def identify_vendor(file_name):

    file_name_lower = file_name.lower()

    vendor_keywords = {
        "hikvision": "Hikvision",
        "dahua": "Dahua",
        "cpplus": "CP Plus",
        "cp_plus": "CP Plus",
        "honeywell": "Honeywell",
        "tplink": "TP-Link",
        "tp-link": "TP-Link",
        "godrej": "Godrej",
        "uniview": "Uniview",
        "matrix": "Matrix"
    }

    for keyword, vendor in vendor_keywords.items():

        if keyword in file_name_lower:
            return vendor

    return "UNKNOWN"


def detect_file_signature(file_path):

    with open(file_path, "rb") as file:

        header = file.read(16)

    if header.startswith(b"\x00\x00\x00"):

        if b"ftyp" in header:
            return "MP4/MOV"

    if header.startswith(b"RIFF") and b"AVI" in header:
        return "AVI"

    if header.startswith(b"\x1A\x45\xDF\xA3"):
        return "MKV/WebM"

    return "UNKNOWN"


def load_metadata(metadata_path):

    if not os.path.exists(metadata_path):
        return {}

    with open(metadata_path, "r") as file:
        return json.load(file)


def parse_evidence(file_path, metadata_path):

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Evidence file not found: {file_path}"
        )

    file_name = os.path.basename(file_path)
    file_extension = os.path.splitext(file_path)[1].lower()

    video_format = identify_video_format(
        file_extension
    )

    vendor = identify_vendor(
        file_name
    )

    file_signature = detect_file_signature(
        file_path
    )

    metadata = load_metadata(
        metadata_path
    )

    parsed_data = {
        "file_name": file_name,
        "file_extension": file_extension,
        "video_format": video_format,
        "file_signature": file_signature,
        "vendor": vendor,
        "file_size_bytes": os.path.getsize(file_path),
        "metadata": metadata,
        "parser_status": "SUCCESS"
    }

    return parsed_data


if __name__ == "__main__":

    evidence_path = "../device/hikvision_test.mp4"

    metadata_path = "../metadata/metadata_output.json"

    try:

        result = parse_evidence(
            evidence_path,
            metadata_path
        )

        print("\nEVIDENCE PARSER")
        print("────────────────────────────")

        print("File name      :", result["file_name"])
        print("Extension      :", result["file_extension"])
        print("Video format   :", result["video_format"])
        print("File signature :", result["file_signature"])
        print("Vendor         :", result["vendor"])
        print("Size           :", result["file_size_bytes"], "bytes")

        if result["metadata"]:

            print("\nMETADATA")
            print("────────────────────────────")

            for key, value in result["metadata"].items():

                print(f"{key}: {value}")

        else:

            print("\nNo metadata file found.")

        print("\nStatus:", result["parser_status"])

        output_path = "../output/parsed_evidence.json"

        with open(output_path, "w") as file:
            json.dump(result, file, indent=4)

        print("\nParser result saved successfully!")
        print("Saved as:", output_path)

    except Exception as error:

        print("Error:", error)