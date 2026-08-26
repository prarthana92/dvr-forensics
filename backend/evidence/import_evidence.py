from pathlib import Path
def import_evidence(file_path):
    evidence = Path(file_path)

    if not evidence.exists():
        print("Evidence file not found.")
        return

    print("Evidence imported successfully!")
    print("File name:", evidence.name)
    print("File size:", evidence.stat().st_size, "bytes")


file_path = input("Enter the path of the evidence file: ")

import_evidence(file_path)

