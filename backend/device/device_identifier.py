from pathlib import Path


def identify_device(file_path):
    evidence = Path(file_path)

    if not evidence.exists():
        print("❌ Evidence file not found.")
        return

    file_name = evidence.name.lower()
    file_extension = evidence.suffix.lower()

    print("\n" + "=" * 50)
    print("        DEVICE IDENTIFICATION")
    print("=" * 50)

    print("File Name     :", evidence.name)
    print("File Extension:", file_extension)

    # Initial vendor identification
    vendor = "Unknown"
    device_type = "Unknown"

    if "hikvision" in file_name or "hik" in file_name:
        vendor = "Hikvision"
        device_type = "NVR/DVR"

    elif "dahua" in file_name or "dh" in file_name:
        vendor = "Dahua"
        device_type = "NVR/DVR"

    elif "cpplus" in file_name or "cp_plus" in file_name:
        vendor = "CP Plus"
        device_type = "NVR/DVR"

    elif "uniview" in file_name or "unv" in file_name:
        vendor = "Uniview"
        device_type = "NVR/DVR"

    elif "matrix" in file_name:
        vendor = "Matrix"
        device_type = "NVR/DVR"

    elif "godrej" in file_name:
        vendor = "Godrej"
        device_type = "NVR/DVR"

    elif "honeywell" in file_name:
        vendor = "Honeywell"
        device_type = "NVR/DVR"

    elif "tplink" in file_name or "tp-link" in file_name:
        vendor = "TP-Link"
        device_type = "NVR/DVR"

    print("\nVendor        :", vendor)
    print("Device Type   :", device_type)

    if vendor == "Unknown":
        print("\n⚠️ Vendor could not be identified.")
        print("Further forensic analysis is required.")
    else:
        print("\n✓ Vendor identified from available evidence information.")

    print("=" * 50)


file_path = input("Enter the path of the evidence file: ")

identify_device(file_path)