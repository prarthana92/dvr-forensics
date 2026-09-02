import os
from datetime import datetime


def parse_generic_evidence(
    evidence_id,
    file_path
):
    """
    Generic parser used when the DVR/NVR vendor
    cannot be reliably identified.

    It does NOT assume a vendor.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Evidence file not found: {file_path}"
        )

    absolute_path = os.path.abspath(file_path)

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
            "code": "UNKNOWN",
            "name": "Unknown Vendor"
        },

        "source_file": absolute_path,

        "file": {
            "name": file_name,
            "extension": file_extension,
            "size_bytes": file_size
        },

        "parser": {
            "name": "Generic Evidence Parser",
            "version": "1.0",
            "status": "READY"
        },

        "analysis": {
            "vendor_identified": False,
            "vendor_assumption": False
        },

        "parsed_at": datetime.now().isoformat()
    }

    return result


if __name__ == "__main__":

    test_file = "device/hikvision_test.mp4"

    print("\n")
    print("=" * 60)
    print("             GENERIC PARSER TEST")
    print("=" * 60)

    try:

        result = parse_generic_evidence(
            "EVD-TEST-GENERIC",
            test_file
        )

        print("\nParser test successful.")

        print("\nVendor:")
        print(
            result["vendor"]["name"]
        )

        print("\nVendor identified:")
        print(
            result["analysis"]["vendor_identified"]
        )

        print("\nVendor assumption:")
        print(
            result["analysis"]["vendor_assumption"]
        )

        print("\nFile:")
        print(
            result["file"]["name"]
        )

        print("\nParser:")
        print(
            result["parser"]["name"]
        )

        print("\n")
        print("=" * 60)
        print("              TEST COMPLETE")
        print("=" * 60)

    except Exception as error:

        print("\nError:", error)