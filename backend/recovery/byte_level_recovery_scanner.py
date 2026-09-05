import os
import struct
import json
from datetime import datetime


# ============================================================
# MP4 BOX PARSER
# ============================================================

def read_mp4_boxes(file_path):
    """
    Read the MP4/MOV container structure directly from raw bytes.

    This does NOT decode video.
    It only identifies container boxes such as:
        ftyp
        moov
        mdat
        free
        wide
        etc.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    file_size = os.path.getsize(file_path)

    boxes = []

    with open(file_path, "rb") as file:

        position = 0

        while position + 8 <= file_size:

            file.seek(position)

            header = file.read(8)

            if len(header) < 8:
                break

            size = struct.unpack(">I", header[:4])[0]
            box_type = header[4:8].decode(
                "latin-1",
                errors="replace"
            )

            header_size = 8

            # ------------------------------------------------
            # Extended 64-bit box size
            # ------------------------------------------------

            if size == 1:

                extended = file.read(8)

                if len(extended) < 8:
                    break

                size = struct.unpack(
                    ">Q",
                    extended
                )[0]

                header_size = 16

            # ------------------------------------------------
            # Box extends to EOF
            # ------------------------------------------------

            elif size == 0:

                size = file_size - position

            # ------------------------------------------------
            # Invalid box
            # ------------------------------------------------

            if size < header_size:

                boxes.append(
                    {
                        "position": position,
                        "type": box_type,
                        "size": size,
                        "header_size": header_size,
                        "status": "INVALID_SIZE"
                    }
                )

                break

            end_position = position + size

            if end_position > file_size:

                boxes.append(
                    {
                        "position": position,
                        "type": box_type,
                        "size": size,
                        "header_size": header_size,
                        "end_position": end_position,
                        "status": "TRUNCATED"
                    }
                )

                break

            boxes.append(
                {
                    "position": position,
                    "type": box_type,
                    "size": size,
                    "header_size": header_size,
                    "end_position": end_position,
                    "status": "VALID"
                }
            )

            position = end_position

    return boxes


# ============================================================
# RAW SIGNATURE SCANNER
# ============================================================

def find_signatures(file_path):

    signatures = {

        b"ftyp": "MP4/MOV file type box",

        b"moov": "MP4/MOV movie box",

        b"mdat": "MP4/MOV media data box",

        b"free": "MP4/MOV free space box",

        b"wide": "MP4/MOV wide box",

        b"\x00\x00\x00\x01": "H.264 Annex-B start code",

        b"\x00\x00\x01": "H.264 Annex-B start code"
    }

    results = []

    with open(file_path, "rb") as file:

        data = file.read()

    for signature, description in signatures.items():

        start = 0

        while True:

            position = data.find(
                signature,
                start
            )

            if position == -1:
                break

            results.append(
                {
                    "position": position,
                    "signature_hex":
                        signature.hex(),
                    "description":
                        description
                }
            )

            start = position + 1

    results.sort(
        key=lambda item: item["position"]
    )

    return results


# ============================================================
# H.264 LENGTH-PREFIX INSPECTION
# ============================================================

def inspect_h264_length_prefixes(
    file_path,
    start_position,
    end_position
):
    """
    Inspect a media-data region for H.264-style
    4-byte length-prefixed NAL units.

    This is intentionally conservative.

    We do NOT declare something recovered merely because
    a 4-byte integer looks like a plausible NAL length.
    """

    results = []

    with open(file_path, "rb") as file:

        file.seek(start_position)

        data = file.read(
            end_position - start_position
        )

    position = 0

    data_length = len(data)

    while position + 4 <= data_length:

        nal_size = struct.unpack(
            ">I",
            data[position:position + 4]
        )[0]

        nal_start = (
            start_position
            + position
            + 4
        )

        nal_end = (
            nal_start
            + nal_size
        )

        # ----------------------------------------------------
        # Zero-sized NAL
        # ----------------------------------------------------

        if nal_size == 0:

            results.append(
                {
                    "length_prefix_position":
                        start_position + position,

                    "nal_size":
                        0,

                    "nal_start":
                        nal_start,

                    "nal_end":
                        nal_end,

                    "status":
                        "ZERO_LENGTH"
                }
            )

            position += 4
            continue

        # ----------------------------------------------------
        # NAL fits inside media region
        # ----------------------------------------------------

        if nal_end <= end_position:

            nal_header = data[
                position + 4
            ]

            nal_type = nal_header & 0x1F

            results.append(
                {
                    "length_prefix_position":
                        start_position + position,

                    "nal_size":
                        nal_size,

                    "nal_start":
                        nal_start,

                    "nal_end":
                        nal_end,

                    "nal_type":
                        nal_type,

                    "status":
                        "WITHIN_BOUNDS"
                }
            )

            position += 4 + nal_size

        else:

            # ------------------------------------------------
            # NAL extends beyond available bytes
            # ------------------------------------------------

            results.append(
                {
                    "length_prefix_position":
                        start_position + position,

                    "nal_size":
                        nal_size,

                    "nal_start":
                        nal_start,

                    "nal_end":
                        nal_end,

                    "available_end":
                        end_position,

                    "missing_bytes":
                        nal_end - end_position,

                    "status":
                        "TRUNCATED"
                }
            )

            break

    return results


# ============================================================
# MAIN ANALYSIS
# ============================================================

def analyze_byte_structure(file_path):

    file_size = os.path.getsize(file_path)

    print()
    print("File size:", file_size, "bytes")
    print()

    # --------------------------------------------------------
    # MP4 boxes
    # --------------------------------------------------------

    print("-" * 70)
    print("MP4 CONTAINER BOX ANALYSIS")
    print("-" * 70)

    boxes = read_mp4_boxes(file_path)

    for index, box in enumerate(boxes, start=1):

        print(
            f"{index:02d}. "
            f"{box['type']} "
            f"at {box['position']} "
            f"size={box['size']} "
            f"status={box['status']}"
        )

    # --------------------------------------------------------
    # Locate media boxes
    # --------------------------------------------------------

    mdat_boxes = [
        box
        for box in boxes
        if box["type"] == "mdat"
    ]

    print()
    print(
        "Media data boxes found:",
        len(mdat_boxes)
    )

    # --------------------------------------------------------
    # Raw signatures
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("RAW SIGNATURE ANALYSIS")
    print("-" * 70)

    signatures = find_signatures(
        file_path
    )

    for item in signatures:

        print(
            f"{item['description']} "
            f"at byte {item['position']} "
            f"(hex {item['signature_hex']})"
        )

    # --------------------------------------------------------
    # Inspect mdat regions
    # --------------------------------------------------------

    nal_results = []

    for index, mdat in enumerate(
        mdat_boxes,
        start=1
    ):

        print()
        print("-" * 70)
        print(
            f"ANALYZING MDAT REGION {index}"
        )
        print("-" * 70)

        media_start = (
            mdat["position"]
            + mdat["header_size"]
        )

        media_end = (
            mdat["end_position"]
        )

        print(
            "Media start:",
            media_start
        )

        print(
            "Media end:",
            media_end
        )

        print(
            "Available media bytes:",
            media_end - media_start
        )

        try:

            result = inspect_h264_length_prefixes(
                file_path,
                media_start,
                media_end
            )

            nal_results.extend(result)

            valid_count = sum(
                1
                for item in result
                if item["status"]
                == "WITHIN_BOUNDS"
            )

            truncated_count = sum(
                1
                for item in result
                if item["status"]
                == "TRUNCATED"
            )

            print(
                "Plausible in-bounds NAL units:",
                valid_count
            )

            print(
                "Truncated NAL units:",
                truncated_count
            )

            # Print first few only
            for item in result[:15]:

                print(
                    "NAL:",
                    "position=",
                    item[
                        "length_prefix_position"
                    ],
                    "size=",
                    item["nal_size"],
                    "status=",
                    item["status"]
                )

        except Exception as error:

            print(
                "NAL inspection failed:",
                error
            )

    # --------------------------------------------------------
    # Determine whether later raw data exists
    # --------------------------------------------------------

    later_signatures = []

    if mdat_boxes:

        first_mdat_end = (
            mdat_boxes[0]["end_position"]
        )

        for item in signatures:

            if item["position"] > first_mdat_end:

                later_signatures.append(item)

    # --------------------------------------------------------
    # Final forensic interpretation
    # --------------------------------------------------------

    if later_signatures:

        additional_region_status = (
            "POTENTIAL_LATER_DATA_FOUND"
        )

    else:

        additional_region_status = (
            "NO_LATER_CONTAINER_SIGNATURE_FOUND"
        )

    result = {

        "video_file":
            os.path.abspath(file_path),

        "analysis_timestamp":
            datetime.now().isoformat(),

        "file_size_bytes":
            file_size,

        "mp4_boxes":
            boxes,

        "mdat_boxes":
            mdat_boxes,

        "raw_signatures":
            signatures,

        "h264_nal_analysis":
            nal_results,

        "additional_region_analysis":
            {
                "status":
                    additional_region_status,

                "later_signatures":
                    later_signatures,

                "note":
                    "A raw signature or plausible NAL boundary "
                    "does not by itself prove recoverability. "
                    "Any candidate region must be independently "
                    "decoded and validated before being classified "
                    "as recovered."
            },

        "synthetic_frames_created":
            0,

        "synthetic_content_added":
            False
    }

    return result


# ============================================================
# SAVE REPORT
# ============================================================

def save_report(result, output_file):

    folder = os.path.dirname(
        output_file
    )

    if folder:
        os.makedirs(
            folder,
            exist_ok=True
        )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            indent=4
        )


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("             BYTE-LEVEL RECOVERY SCANNER")
    print("=" * 70)

    backend_folder = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    video_path = os.path.join(
        backend_folder,
        "recovery",
        "test_data",
        "damaged_test.mp4"
    )

    output_folder = os.path.join(
        backend_folder,
        "output",
        "recovery",
        "EVD-TEST-RECOVERY"
    )

    output_file = os.path.join(
        output_folder,
        "byte_level_recovery_scan.json"
    )

    print()
    print("Video:")
    print(video_path)

    if not os.path.exists(video_path):

        print()
        print("ERROR:")
        print("Damaged video was not found.")
        print(video_path)

        raise SystemExit(1)

    try:

        result = analyze_byte_structure(
            video_path
        )

        save_report(
            result,
            output_file
        )

        print()
        print("=" * 70)
        print("BYTE-LEVEL ANALYSIS COMPLETE")
        print("=" * 70)

        print()
        print(
            "Report:"
        )

        print(
            output_file
        )

        print()

        print(
            "Additional region status:"
        )

        print(
            result[
                "additional_region_analysis"
            ][
                "status"
            ]
        )

        print()
        print(
            "Synthetic frames created: 0"
        )

        print(
            "Synthetic content added: False"
        )

        print()
        print("=" * 70)

    except Exception as error:

        print()
        print("ERROR:")
        print(error)

        print()
        print("=" * 70)