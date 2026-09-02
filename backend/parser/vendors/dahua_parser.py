import os
from datetime import datetime


def parse_dahua_evidence(
    evidence_id,
    file_path
):
    """
    Dahua-specific evidence parser.

    IMPORTANT:
    This parser does not identify the vendor.
    Vendor identification is handled by
    vendor_detector.py.

    This parser standardizes evidence information
    after Dahua has been identified.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Evidence file not found: {file_path}"
        )

    absolute_path = os.path.abspath(
        file_path
    )

    file_name = os.path.basename(
        absolute_path
    )

    file_extension = os.path.splitext(
        file_name
    )[1].lower()

    file_size = os.path.getsize(
        absolute_path
    )

    result = {
        "evidence_id": evidence_id,

        "vendor": {
            "code": "DAHUA",
            "name": "Dahua"
        },

        "source_file": absolute_path,

        "file": {
            "name": file_name,
            "extension": file_extension,
            "size_bytes": file_size
        },

        "parser": {
            "name": "Dahua Parser",
            "version": "1.0",
            "status": "READY"
        },

        "vendor_characteristics": {
            "common_export_formats": [
                ".dav",
                ".mp4",
                ".avi",
                ".ts",
                ".264"
            ],
            "notes": (
                "Dahua surveillance evidence may be "
                "provided in vendor-specific or standard "
                "video formats."
            )
        },

        "analysis": {
            "vendor_identified_by_parser": False,
            "vendor_assumption": False
        },

        "parsed_at": datetime.now().isoformat()
    }

    return result


if __name__ == "__main__":

    print("\n")
    print("=" * 60)
    print("               DAHUA PARSER TEST")
    print("=" * 60)

    print("\nParser module loaded successfully.")

    print("\nVendor handled:")
    print("Dahua")

    print("\nImportant:")
    print(
        "This parser does NOT identify arbitrary files as Dahua."
    )

    print(
        "Vendor identification is handled by vendor_detector.py."
    )

    print("\n")
    print("=" * 60)
    print("              TEST COMPLETE")
    print("=" * 60)