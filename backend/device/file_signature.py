from pathlib import Path


def detect_file_signature(file_path):

    file = Path(file_path)

    if not file.exists():
        print("❌ File not found.")
        return

    with open(file, "rb") as f:
        header = f.read(16)

    print("\n" + "=" * 50)
    print("        FILE SIGNATURE ANALYSIS")
    print("=" * 50)

    print("File Name :", file.name)
    print("Header    :", header.hex(" "))

    file_type = "Unknown"

    # MP4/MOV files usually contain 'ftyp'
    if b"ftyp" in header:
        file_type = "MP4 / MOV Video"

    # AVI files begin with RIFF and contain AVI
    elif header.startswith(b"RIFF") and b"AVI" in header:
        file_type = "AVI Video"

    # JPEG image signature
    elif header.startswith(b"\xff\xd8\xff"):
        file_type = "JPEG Image"

    # PNG image signature
    elif header.startswith(b"\x89PNG"):
        file_type = "PNG Image"

    print("\nDetected Type :", file_type)

    if file_type == "Unknown":
        print("⚠️ File format could not be identified.")
    else:
        print("✓ File signature recognized.")

    print("=" * 50)


file_path = input("Enter the path of the evidence file: ")

detect_file_signature(file_path)