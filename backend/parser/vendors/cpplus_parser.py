import os
from datetime import datetime


def parse_cpplus_evidence(evidence_id, file_path):

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Evidence file not found: {file_path}"
        )

    absolute_path = os.path.abspath(file_path)
    file_name = os.path.basename(absolute_path)
    extension = os.path.splitext(file_name)[1].lower()
    file_size = os.path.getsize(absolute_path)

    return {
        "evidence_id": evidence_id,
        "vendor": {
            "code": "CP_PLUS",
            "name": "CP Plus"
        },
        "source_file": absolute_path,
        "file": {
            "name": file_name,
            "extension": extension,
            "size_bytes": file_size
        },
        "parser": {
            "name": "CP Plus Parser",
            "version": "1.0",
            "status": "READY"
        },
        "vendor_characteristics": {
            "common_export_formats": [
                ".dav",
                ".mp4",
                ".avi",
                ".264"
            ]
        },
        "analysis": {
            "vendor_identified_by_parser": False,
            "vendor_assumption": False
        },
        "parsed_at": datetime.now().isoformat()
    }


if __name__ == "__main__":
    print("\nCP PLUS PARSER")
    print("Parser module loaded successfully.")
    print("Vendor identification is handled separately.")