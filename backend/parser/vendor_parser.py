from datetime import datetime
import os


def create_standardized_metadata(
    evidence_id,
    file_path,
    vendor_code,
    vendor_name,
    file_type,
    file_size
):
    """
    Creates a common metadata structure for all vendors.
    """

    return {
        "evidence_id": evidence_id,
        "vendor": {
            "code": vendor_code,
            "name": vendor_name
        },
        "source_file": file_path,
        "file_type": file_type,
        "file_size_bytes": file_size,
        "parser_status": "READY",
        "parsed_at": datetime.now().isoformat()
    }


def parse_vendor_evidence(
    evidence_id,
    file_path,
    vendor_information
):
    """
    Creates a standardized result for evidence
    from a detected vendor.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Evidence file not found: {file_path}"
        )

    vendor_code = vendor_information["vendor_code"]
    vendor_name = vendor_information["vendor_name"]

    file_type = "UNKNOWN"

    if "." in file_path:
        file_type = file_path.rsplit(
            ".",
            1
        )[1].upper()

    file_size = os.path.getsize(
        file_path
    )

    metadata = create_standardized_metadata(
        evidence_id,
        file_path,
        vendor_code,
        vendor_name,
        file_type,
        file_size
    )

    return metadata


if __name__ == "__main__":

    print("\n")
    print("=" * 60)
    print("          STANDARDIZED VENDOR PARSER")
    print("=" * 60)

    test_vendor = {
        "vendor_code": "HIKVISION",
        "vendor_name": "Hikvision",
        "supported": True
    }

    test_file = "device/hikvision_test.mp4"

    try:

        result = parse_vendor_evidence(
            "EVD-TEST-VENDOR",
            test_file,
            test_vendor
        )

        print("\nParser test successful.")

        print("\nStandardized result:")
        print("-" * 60)

        for key, value in result.items():

            print(
                f"{key}: {value}"
            )

        print("\n")
        print("=" * 60)
        print("              TEST COMPLETE")
        print("=" * 60)

    except Exception as error:

        print("\nError:", error)