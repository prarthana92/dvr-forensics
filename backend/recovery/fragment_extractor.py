import os
import json


def extract_fragment(
    source_file,
    output_file,
    start_position,
    end_position=None
):
    """
    Extract a byte fragment from a source file.

    If end_position is provided:
        extract from start_position up to end_position.

    If end_position is not provided:
        extract from start_position to the end of the file.
    """

    if not os.path.exists(source_file):

        raise FileNotFoundError(
            f"Source file not found: {source_file}"
        )

    file_size = os.path.getsize(
        source_file
    )

    if start_position < 0:

        raise ValueError(
            "Start position cannot be negative."
        )

    if start_position >= file_size:

        raise ValueError(
            "Start position is outside the file."
        )

    if end_position is not None:

        if end_position <= start_position:

            raise ValueError(
                "End position must be greater than start position."
            )

        if end_position > file_size:

            end_position = file_size

    output_folder = os.path.dirname(
        os.path.abspath(output_file)
    )

    os.makedirs(
        output_folder,
        exist_ok=True
    )

    with open(
        source_file,
        "rb"
    ) as source:

        source.seek(start_position)

        if end_position is None:

            bytes_to_read = (
                file_size - start_position
            )

        else:

            bytes_to_read = (
                end_position - start_position
            )

        data = source.read(
            bytes_to_read
        )

    with open(
        output_file,
        "wb"
    ) as output:

        output.write(data)

    return len(data)


if __name__ == "__main__":

    backend_folder = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    evidence_path = os.path.join(
        backend_folder,
        "device",
        "hikvision_test.mp4"
    )

    scan_path = os.path.join(
        backend_folder,
        "output",
        "fragment_scan.json"
    )

    output_path = os.path.join(
        backend_folder,
        "output",
        "recovered_fragment.mp4"
    )

    try:

        if not os.path.exists(scan_path):

            print(
                "Fragment scan report not found."
            )

            print(
                "Run fragment_scanner.py first."
            )

        else:

            with open(
                scan_path,
                "r",
                encoding="utf-8"
            ) as file:

                scan_result = json.load(
                    file
                )

            results = scan_result.get(
                "results",
                []
            )

            if not results:

                print(
                    "No video fragments found."
                )

            else:

                first_result = results[0]

                start_position = first_result[
                    "position"
                ]

                bytes_extracted = extract_fragment(
                    evidence_path,
                    output_path,
                    start_position
                )

                print(
                    "\nFRAGMENT EXTRACTION"
                )

                print(
                    "────────────────────────────"
                )

                print(
                    "Detected type:",
                    first_result["file_type"]
                )

                print(
                    "Start position:",
                    start_position
                )

                print(
                    "End position:",
                    os.path.getsize(
                        evidence_path
                    )
                )

                print(
                    "Bytes extracted:",
                    bytes_extracted
                )

                print(
                    "\nFragment extracted successfully!"
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