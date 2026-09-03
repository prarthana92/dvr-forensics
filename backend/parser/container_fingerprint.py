import os
import struct
import hashlib
from datetime import datetime


# ============================================================
# TRACE X
# MP4 CONTAINER FORENSIC ANALYZER
# Metadata + Structure Extraction
# ============================================================


MAX_SCAN_SIZE = 20 * 1024 * 1024


CONTAINER_BOXES = {
    "moov",
    "trak",
    "mdia",
    "minf",
    "dinf",
    "stbl",
    "edts",
    "udta",
    "meta",
}


KNOWN_BOXES = {
    "ftyp", "free", "skip", "mdat", "moov",
    "mvhd", "trak", "tkhd", "mdia", "mdhd",
    "hdlr", "minf", "vmhd", "smhd",
    "dinf", "dref", "url ", "urn ",
    "stbl", "stsd", "stts", "stsc",
    "stsz", "stco", "co64", "stss",
    "ctts", "edts", "elst",
    "udta", "meta", "ilst",
    "wide", "uuid"
}


def read_box_header(file):

    position = file.tell()

    header = file.read(8)

    if len(header) < 8:
        return None

    size = struct.unpack(
        ">I",
        header[:4]
    )[0]

    box_type = header[4:8].decode(
        "latin-1",
        errors="replace"
    )

    header_size = 8

    if size == 1:

        extended = file.read(8)

        if len(extended) < 8:
            return None

        size = struct.unpack(
            ">Q",
            extended
        )[0]

        header_size = 16

    elif size == 0:

        current = file.tell()

        file.seek(0, os.SEEK_END)

        end = file.tell()

        file.seek(current)

        size = end - position

    return {
        "position": position,
        "size": size,
        "type": box_type,
        "header_size": header_size
    }


def scan_boxes(file, end_position, depth=0):

    boxes = []

    while file.tell() < end_position:

        position = file.tell()

        if position >= MAX_SCAN_SIZE:
            break

        box = read_box_header(file)

        if box is None:
            break

        size = box["size"]
        header_size = box["header_size"]

        if size < header_size:
            break

        box_end = position + size

        if box_end > end_position:

            boxes.append({
                **box,
                "depth": depth,
                "status": "TRUNCATED",
                "children": []
            })

            break

        record = {
            **box,
            "depth": depth,
            "status": "VALID",
            "children": []
        }

        if box["type"] in CONTAINER_BOXES:

            file.seek(position + header_size)

            record["children"] = scan_boxes(
                file,
                box_end,
                depth + 1
            )

        file.seek(box_end)

        boxes.append(record)

    return boxes


def flatten_boxes(boxes):

    result = []

    for box in boxes:

        result.append(box)

        if box["children"]:

            result.extend(
                flatten_boxes(
                    box["children"]
                )
            )

    return result


def calculate_sha256(file_path):

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        while True:

            data = file.read(1024 * 1024)

            if not data:
                break

            sha256.update(data)

    return sha256.hexdigest()


def read_box_data(file_path, box):

    with open(file_path, "rb") as file:

        file.seek(
            box["position"]
            + box["header_size"]
        )

        return file.read(
            min(
                box["size"]
                - box["header_size"],
                4096
            )
        )


def parse_ftyp(file_path, box):

    data = read_box_data(
        file_path,
        box
    )

    if len(data) < 8:
        return {}

    major_brand = data[0:4].decode(
        "latin-1",
        errors="replace"
    )

    minor_version = struct.unpack(
        ">I",
        data[4:8]
    )[0]

    compatible = []

    for i in range(8, len(data), 4):

        brand = data[i:i + 4]

        if len(brand) == 4:

            compatible.append(
                brand.decode(
                    "latin-1",
                    errors="replace"
                )
            )

    return {
        "major_brand": major_brand,
        "minor_version": minor_version,
        "compatible_brands": compatible
    }


def parse_hdlr(file_path, box):

    data = read_box_data(
        file_path,
        box
    )

    if len(data) < 12:
        return {}

    # Full box header = version + flags
    handler_offset = 8

    handler_type = data[
        handler_offset:
        handler_offset + 4
    ].decode(
        "latin-1",
        errors="replace"
    )

    return {
        "handler_type": handler_type
    }


def parse_mvhd(file_path, box):

    data = read_box_data(
        file_path,
        box
    )

    if len(data) < 20:
        return {}

    version = data[0]

    if version == 0:

        timescale = struct.unpack(
            ">I",
            data[12:16]
        )[0]

        duration = struct.unpack(
            ">I",
            data[16:20]
        )[0]

    else:

        if len(data) < 32:
            return {}

        timescale = struct.unpack(
            ">I",
            data[20:24]
        )[0]

        duration = struct.unpack(
            ">Q",
            data[24:32]
        )[0]

    return {
        "version": version,
        "timescale": timescale,
        "duration_units": duration
    }


def parse_mdhd(file_path, box):

    data = read_box_data(
        file_path,
        box
    )

    if len(data) < 20:
        return {}

    version = data[0]

    if version == 0:

        timescale = struct.unpack(
            ">I",
            data[12:16]
        )[0]

        duration = struct.unpack(
            ">I",
            data[16:20]
        )[0]

    else:

        if len(data) < 32:
            return {}

        timescale = struct.unpack(
            ">I",
            data[20:24]
        )[0]

        duration = struct.unpack(
            ">Q",
            data[24:32]
        )[0]

    return {
        "version": version,
        "timescale": timescale,
        "duration_units": duration
    }


def inspect_stsd(file_path, box):

    data = read_box_data(
        file_path,
        box
    )

    if len(data) < 16:
        return {}

    entry_count = struct.unpack(
        ">I",
        data[4:8]
    )[0]

    sample_entries = []

    offset = 8

    for _ in range(entry_count):

        if offset + 8 > len(data):
            break

        entry_size = struct.unpack(
            ">I",
            data[offset:offset + 4]
        )[0]

        entry_type = data[
            offset + 4:
            offset + 8
        ].decode(
            "latin-1",
            errors="replace"
        )

        sample_entries.append({
            "type": entry_type,
            "size": entry_size
        })

        if entry_size <= 0:
            break

        offset += entry_size

    return {
        "entry_count": entry_count,
        "sample_entries": sample_entries
    }


def inspect_beam(file_path, box):

    data = read_box_data(
        file_path,
        box
    )

    return {
        "size": box["size"],
        "raw_hex_preview": data.hex(),
        "ascii_preview": data.decode(
            "latin-1",
            errors="replace"
        )
    }


def analyze(file_path):

    if not os.path.exists(file_path):

        raise FileNotFoundError(
            f"Evidence file not found: {file_path}"
        )

    boxes = []

    with open(file_path, "rb") as file:

        file_size = os.path.getsize(
            file_path
        )

        boxes = scan_boxes(
            file,
            file_size
        )

    flat = flatten_boxes(boxes)

    counts = {}

    unknown = []

    for box in flat:

        box_type = box["type"]

        counts[box_type] = (
            counts.get(box_type, 0) + 1
        )

        if (
            box_type not in KNOWN_BOXES
            and box_type not in unknown
        ):

            unknown.append(box_type)

    result = {

        "analysis": {
            "type":
                "MP4_METADATA_STRUCTURAL_ANALYSIS",

            "analyzed_at":
                datetime.now().isoformat(),

            "vendor_identified":
                False
        },

        "file": {
            "name":
                os.path.basename(file_path),

            "size_bytes":
                os.path.getsize(file_path),

            "sha256":
                calculate_sha256(file_path),

            "path":
                os.path.abspath(file_path)
        },

        "container": {
            "box_count":
                len(flat),

            "box_counts":
                counts,

            "unknown_box_types":
                unknown,

            "box_sequence":
                [
                    box["type"]
                    for box in flat
                ]
        },

        "metadata": {}
    }

    # --------------------------------------------------------
    # Extract selected metadata
    # --------------------------------------------------------

    for box in flat:

        box_type = box["type"]

        if box_type == "ftyp":

            result["metadata"]["ftyp"] = (
                parse_ftyp(
                    file_path,
                    box
                )
            )

        elif box_type == "hdlr":

            result["metadata"].setdefault(
                "handlers",
                []
            ).append(
                parse_hdlr(
                    file_path,
                    box
                )
            )

        elif box_type == "mvhd":

            result["metadata"]["mvhd"] = (
                parse_mvhd(
                    file_path,
                    box
                )
            )

        elif box_type == "mdhd":

            result["metadata"].setdefault(
                "mdhd",
                []
            ).append(
                parse_mdhd(
                    file_path,
                    box
                )
            )

        elif box_type == "stsd":

            result["metadata"].setdefault(
                "sample_descriptions",
                []
            ).append(
                inspect_stsd(
                    file_path,
                    box
                )
            )

        elif box_type == "beam":

            result["metadata"]["beam"] = (
                inspect_beam(
                    file_path,
                    box
                )
            )

    result["forensic_note"] = (
        "Extracted container characteristics are "
        "descriptive evidence. Vendor identification "
        "requires validation against known samples."
    )

    return result


def print_tree(boxes, indent=0):

    for box in boxes:

        print(
            "  " * indent
            + f"{box['type']} "
            + f"(size={box['size']}, "
            + f"offset={box['position']})"
        )

        if box["children"]:

            print_tree(
                box["children"],
                indent + 1
            )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_file = (
        "parser/test_data/"
        "WhatsApp Video 2026-08-31 at 10.10.38 PM.mp4"
    )

    print()
    print("=" * 65)
    print(
        "       MP4 FORENSIC METADATA ANALYSIS"
    )
    print("=" * 65)

    try:

        result = analyze(test_file)

        print()
        print("FILE")
        print("─────────────────────────────────")

        print(
            result["file"]["name"]
        )

        print(
            "Size:",
            result["file"]["size_bytes"],
            "bytes"
        )

        print()
        print("CONTAINER")
        print("─────────────────────────────────")

        print(
            "Boxes:",
            result["container"]["box_count"]
        )

        print(
            "Sequence:"
        )

        print(
            " → ".join(
                result[
                    "container"
                ]["box_sequence"]
            )
        )

        print()
        print("FTYP")
        print("─────────────────────────────────")

        print(
            result[
                "metadata"
            ].get(
                "ftyp",
                "Not found"
            )
        )

        print()
        print("HANDLER TYPES")
        print("─────────────────────────────────")

        print(
            result[
                "metadata"
            ].get(
                "handlers",
                "Not found"
            )
        )

        print()
        print("SAMPLE DESCRIPTIONS / CODEC")
        print("─────────────────────────────────")

        print(
            result[
                "metadata"
            ].get(
                "sample_descriptions",
                "Not found"
            )
        )

        print()
        print("TIMING")
        print("─────────────────────────────────")

        print(
            "Movie header:",
            result[
                "metadata"
            ].get(
                "mvhd",
                "Not found"
            )
        )

        print(
            "Media header:",
            result[
                "metadata"
            ].get(
                "mdhd",
                "Not found"
            )
        )

        print()
        print("CUSTOM / UNKNOWN BOXES")
        print("─────────────────────────────────")

        unknown = result[
            "container"
        ]["unknown_box_types"]

        if unknown:

            for item in unknown:

                print(
                    "-",
                    repr(item)
                )

        else:

            print("None")

        print()
        print("VENDOR IDENTIFICATION")
        print("─────────────────────────────────")

        print(
            "Vendor identified:",
            result[
                "analysis"
            ]["vendor_identified"]
        )

        # ----------------------------------------------------
        # SAVE JSON
        # ----------------------------------------------------

        output_directory = "output"

        os.makedirs(
            output_directory,
            exist_ok=True
        )

        output_file = os.path.join(
            output_directory,
            "container_fingerprint.json"
        )

        import json

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

        print()
        print("OUTPUT")
        print("─────────────────────────────────")

        print(
            "Fingerprint saved to:",
            output_file
        )

        print()
        print("=" * 65)
        print("                 COMPLETE")
        print("=" * 65)

    except Exception as error:

        print()
        print(
            "ERROR:",
            error
        )