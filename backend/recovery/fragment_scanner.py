import os
import json


VIDEO_SIGNATURES = {
    b"ftyp": "MP4/MOV",
    b"RIFF": "AVI",
    b"\x1A\x45\xDF\xA3": "MKV/WebM"
}


def find_all_occurrences(data, signature):
    """
    Find every occurrence of a byte signature
    inside the supplied data.
    """

    positions = []
    start = 0

    while True:

        position = data.find(
            signature,
            start
        )

        if position == -1:
            break

        positions.append(position)

        # Move forward so the same occurrence
        # is not found again.
        start = position + 1

    return positions


def scan_for_video_signatures(file_path):

    if not os.path.exists(file_path):

        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    found_signatures = []

    with open(file_path, "rb") as file:

        data = file.read()

    for signature, file_type in VIDEO_SIGNATURES.items():

        positions = find_all_occurrences(
            data,
            signature
        )

        for position in positions:

            found_signatures.append({
                "file_type": file_type,
                "signature": signature.hex(),
                "position": position
            })

    # Sort all detected signatures by their
    # position inside the file.
    found_signatures.sort(
        key=lambda item: item["position"]
    )

    return found_signatures


if __name__ == "__main__":

    evidence_path = os.path.join(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        ),
        "device",
        "hikvision_test.mp4"
    )

    output_folder = os.path.join(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        ),
        "output"
    )

    output_path = os.path.join(
        output_folder,
        "fragment_scan.json"
    )

    try:

        results = scan_for_video_signatures(
            evidence_path
        )

        print("\nVIDEO FRAGMENT SCANNER")
        print("────────────────────────────")

        print(
            "Scanned file:",
            evidence_path
        )

        print(
            "File size:",
            os.path.getsize(evidence_path),
            "bytes"
        )

        if results:

            print("\nVideo signatures found:")

            for number, result in enumerate(
                results,
                start=1
            ):

                print(
                    f"{number}.",
                    result["file_type"],
                    "| Position:",
                    result["position"]
                )

        else:

            print(
                "\nNo known video signatures found."
            )

        report = {
            "scanned_file": evidence_path,
            "file_size_bytes": os.path.getsize(
                evidence_path
            ),
            "signatures_found": len(results),
            "results": results
        }

        os.makedirs(
            output_folder,
            exist_ok=True
        )

        with open(
            output_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                report,
                file,
                indent=4
            )

        print(
            "\nTotal signatures found:",
            len(results)
        )

        print(
            "\nFragment scan report saved successfully!"
        )

        print(
            "Saved as:",
            output_path
        )

    except Exception as error:

        print(
            "Error:",
            error
        )