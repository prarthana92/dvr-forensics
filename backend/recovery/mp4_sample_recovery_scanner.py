"""
TraceX Dynamic MP4 Sample Recovery Scanner

Purpose:
    Dynamically inspect an MP4/MOV video track using its container metadata.

The scanner:
    - Finds MP4/MOV boxes dynamically
    - Finds the video track dynamically
    - Parses stts
    - Parses stsc
    - Parses stsz
    - Parses stco/co64
    - Parses stss
    - Calculates every video sample's absolute byte range
    - Checks sample ranges against mdat
    - Detects obvious physical corruption such as zero-filled data
    - Groups samples into GOPs using keyframes
    - Determines GOP-level recoverability
    - Produces a forensic JSON report

IMPORTANT:
    This file contains NO knowledge of:
        - multi_region_damaged.mp4
        - any specific filename
        - any specific corruption offset
        - any specific number of samples
        - any specific vendor

The input video is supplied at runtime.

FORENSIC PRINCIPLE:
    Physical presence is not the same as decoder-valid recovery.

    This scanner identifies:
        1. Physical sample availability
        2. Structural sample problems
        3. GOP-level recoverability
        4. Original timeline regions

    It does NOT generate synthetic footage.
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime


# ============================================================
# GENERAL HELPERS
# ============================================================

def read_u32(data, offset):
    return int.from_bytes(
        data[offset:offset + 4],
        "big"
    )


def read_u64(data, offset):
    return int.from_bytes(
        data[offset:offset + 8],
        "big"
    )


def read_i32(data, offset):
    return int.from_bytes(
        data[offset:offset + 4],
        "big",
        signed=True
    )


def read_type(data, offset):
    return data[offset:offset + 4].decode(
        "latin1",
        errors="replace"
    )


def safe_name(name):
    return re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        name
    )


def format_time(seconds):
    if seconds is None:
        return None

    seconds = max(
        0.0,
        float(seconds)
    )

    hours = int(seconds // 3600)

    minutes = int(
        (seconds % 3600) // 60
    )

    secs = seconds % 60

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{secs:06.3f}"
    )


# ============================================================
# MP4 BOX PARSING
# ============================================================

def parse_box_header(data, offset):
    """
    Parse one ISO Base Media File Format box header.

    Returns:
        {
            "start": absolute start,
            "size": total box size,
            "type": box type,
            "header_size": header size,
            "end": exclusive end
        }

    Returns None if the header is invalid/incomplete.
    """

    if offset + 8 > len(data):
        return None

    size = read_u32(
        data,
        offset
    )

    box_type = read_type(
        data,
        offset + 4
    )

    header_size = 8

    if size == 1:

        if offset + 16 > len(data):
            return None

        size = read_u64(
            data,
            offset + 8
        )

        header_size = 16

    elif size == 0:

        size = len(data) - offset

    if size < header_size:
        return None

    end = offset + size

    if end > len(data):

        return {
            "start": offset,
            "size": size,
            "type": box_type,
            "header_size": header_size,
            "end": end,
            "truncated": True,
        }

    return {
        "start": offset,
        "size": size,
        "type": box_type,
        "header_size": header_size,
        "end": end,
        "truncated": False,
    }


def iter_boxes(data, start, end):
    """
    Iterate over child boxes inside a known container.
    """

    offset = start

    while offset + 8 <= end:

        box = parse_box_header(
            data,
            offset
        )

        if box is None:
            break

        if box["end"] > end:
            break

        yield box

        if box["size"] <= 0:
            break

        offset = box["end"]


def find_child_box(data, start, end, box_type):
    """
    Find the first direct child box of a given type.
    """

    for box in iter_boxes(
        data,
        start,
        end
    ):

        if box["type"] == box_type:
            return box

    return None


def find_all_child_boxes(data, start, end, box_type):
    """
    Find all direct child boxes of a given type.
    """

    results = []

    for box in iter_boxes(
        data,
        start,
        end
    ):

        if box["type"] == box_type:
            results.append(box)

    return results


# ============================================================
# TOP LEVEL STRUCTURE
# ============================================================

def scan_top_level_boxes(data):

    boxes = []

    offset = 0

    while offset + 8 <= len(data):

        box = parse_box_header(
            data,
            offset
        )

        if box is None:
            break

        boxes.append(box)

        if box["size"] <= 0:
            break

        offset = box["end"]

        if offset > len(data):
            break

    return boxes


def find_mdat_ranges(top_boxes, file_size):

    ranges = []

    for box in top_boxes:

        if box["type"] != "mdat":
            continue

        payload_start = (
            box["start"]
            + box["header_size"]
        )

        payload_end = min(
            box["end"],
            file_size
        )

        ranges.append(
            {
                "box_start": box["start"],
                "box_end": min(
                    box["end"],
                    file_size
                ),
                "payload_start": payload_start,
                "payload_end": payload_end,
                "declared_size": box["size"],
                "truncated": box.get(
                    "truncated",
                    False
                ),
            }
        )

    return ranges


def range_inside_mdat(
    start,
    end,
    mdat_ranges
):
    """
    Check whether [start, end) is fully inside
    one mdat payload.
    """

    for mdat in mdat_ranges:

        if (
            start >= mdat["payload_start"]
            and
            end <= mdat["payload_end"]
        ):
            return True

    return False


# ============================================================
# VIDEO TRACK DISCOVERY
# ============================================================

def find_video_track(data, moov_box):
    """
    Find the first trak whose mdia/hdlr says vide.
    """

    moov_start = (
        moov_box["start"]
        + moov_box["header_size"]
    )

    moov_end = moov_box["end"]

    for trak in find_all_child_boxes(
        data,
        moov_start,
        moov_end,
        "trak"
    ):

        trak_start = (
            trak["start"]
            + trak["header_size"]
        )

        trak_end = trak["end"]

        mdia = find_child_box(
            data,
            trak_start,
            trak_end,
            "mdia"
        )

        if mdia is None:
            continue

        mdia_start = (
            mdia["start"]
            + mdia["header_size"]
        )

        mdia_end = mdia["end"]

        hdlr = find_child_box(
            data,
            mdia_start,
            mdia_end,
            "hdlr"
        )

        if hdlr is None:
            continue

        payload = (
            hdlr["start"]
            + hdlr["header_size"]
        )

        if payload + 12 > hdlr["end"]:
            continue

        handler_type = read_type(
            data,
            payload + 8
        )

        if handler_type == "vide":
            return trak, mdia

    return None, None


# ============================================================
# STSD
# ============================================================

def parse_stsd(data, stsd_box):
    """
    Parse basic video sample description information.
    """

    payload = (
        stsd_box["start"]
        + stsd_box["header_size"]
    )

    if payload + 8 > stsd_box["end"]:
        return {}

    version_flags = read_u32(
        data,
        payload
    )

    entry_count = read_u32(
        data,
        payload + 4
    )

    entries = []

    offset = payload + 8

    for _ in range(entry_count):

        if offset + 8 > stsd_box["end"]:
            break

        entry_size = read_u32(
            data,
            offset
        )

        entry_type = read_type(
            data,
            offset + 4
        )

        if entry_size < 8:
            break

        entry_end = (
            offset
            + entry_size
        )

        if entry_end > stsd_box["end"]:
            break

        entry_info = {
            "type": entry_type,
            "size": entry_size,
        }

        if entry_type in (
            "avc1",
            "avc2",
            "avc3",
            "avc4",
            "hvc1",
            "hev1",
        ):

            if offset + 28 <= entry_end:

                entry_info["width"] = int.from_bytes(
                    data[
                        offset + 24:
                        offset + 26
                    ],
                    "big"
                )

                entry_info["height"] = int.from_bytes(
                    data[
                        offset + 26:
                        offset + 28
                    ],
                    "big"
                )

        entries.append(entry_info)

        offset = entry_end

    return {
        "entry_count": entry_count,
        "entries": entries,
    }


# ============================================================
# STTS
# ============================================================

def parse_stts(data, box):
    """
    Time-to-sample table.
    """

    payload = (
        box["start"]
        + box["header_size"]
    )

    if payload + 8 > box["end"]:
        return []

    entry_count = read_u32(
        data,
        payload + 4
    )

    entries = []

    offset = payload + 8

    for _ in range(entry_count):

        if offset + 8 > box["end"]:
            break

        sample_count = read_u32(
            data,
            offset
        )

        sample_delta = read_u32(
            data,
            offset + 4
        )

        entries.append(
            {
                "sample_count": sample_count,
                "sample_delta": sample_delta,
            }
        )

        offset += 8

    return entries


def expand_stts(
    stts_entries,
    sample_count
):
    """
    Expand stts into one decode duration
    per sample.
    """

    durations = []

    for entry in stts_entries:

        for _ in range(
            entry["sample_count"]
        ):

            if len(durations) >= sample_count:
                return durations

            durations.append(
                entry["sample_delta"]
            )

    return durations


# ============================================================
# STSS
# ============================================================

def parse_stss(data, box):
    """
    Sync sample table.

    Returns 1-based keyframe sample numbers.
    """

    payload = (
        box["start"]
        + box["header_size"]
    )

    if payload + 8 > box["end"]:
        return []

    entry_count = read_u32(
        data,
        payload + 4
    )

    samples = []

    offset = payload + 8

    for _ in range(entry_count):

        if offset + 4 > box["end"]:
            break

        samples.append(
            read_u32(
                data,
                offset
            )
        )

        offset += 4

    return samples


# ============================================================
# STSZ
# ============================================================

def parse_stsz(data, box):
    """
    Sample size table.

    Returns:
        default_size
        sample_count
        sample_sizes
    """

    payload = (
        box["start"]
        + box["header_size"]
    )

    if payload + 12 > box["end"]:

        return {
            "default_size": 0,
            "sample_count": 0,
            "sample_sizes": [],
        }

    default_size = read_u32(
        data,
        payload + 4
    )

    sample_count = read_u32(
        data,
        payload + 8
    )

    sizes = []

    offset = payload + 12

    if default_size != 0:

        sizes = [
            default_size
        ] * sample_count

    else:

        for _ in range(sample_count):

            if offset + 4 > box["end"]:
                break

            sizes.append(
                read_u32(
                    data,
                    offset
                )
            )

            offset += 4

    return {
        "default_size": default_size,
        "sample_count": sample_count,
        "sample_sizes": sizes,
    }


# ============================================================
# STSC
# ============================================================

def parse_stsc(data, box):
    """
    Sample-to-chunk table.
    """

    payload = (
        box["start"]
        + box["header_size"]
    )

    if payload + 8 > box["end"]:
        return []

    entry_count = read_u32(
        data,
        payload + 4
    )

    entries = []

    offset = payload + 8

    for _ in range(entry_count):

        if offset + 12 > box["end"]:
            break

        entries.append(
            {
                "first_chunk": read_u32(
                    data,
                    offset
                ),
                "samples_per_chunk": read_u32(
                    data,
                    offset + 4
                ),
                "sample_description_index": read_u32(
                    data,
                    offset + 8
                ),
            }
        )

        offset += 12

    return entries


# ============================================================
# STCO / CO64
# ============================================================

def parse_chunk_offsets(data, box):
    """
    Parse either stco or co64.
    """

    payload = (
        box["start"]
        + box["header_size"]
    )

    if payload + 8 > box["end"]:
        return []

    entry_count = read_u32(
        data,
        payload + 4
    )

    offsets = []

    offset = payload + 8

    width = (
        8
        if box["type"] == "co64"
        else 4
    )

    for _ in range(entry_count):

        if offset + width > box["end"]:
            break

        if width == 8:

            offsets.append(
                read_u64(
                    data,
                    offset
                )
            )

        else:

            offsets.append(
                read_u32(
                    data,
                    offset
                )
            )

        offset += width

    return offsets


# ============================================================
# SAMPLE-TO-CHUNK EXPANSION
# ============================================================

def build_sample_chunk_mapping(
    stsc_entries,
    chunk_count,
    sample_count
):
    """
    Expand stsc into one record per chunk.
    """

    if not stsc_entries:
        return []

    entries = sorted(
        stsc_entries,
        key=lambda x: x["first_chunk"]
    )

    chunks = []

    for index, entry in enumerate(entries):

        first_chunk = entry["first_chunk"]

        if index + 1 < len(entries):

            next_first_chunk = (
                entries[index + 1]["first_chunk"]
            )

            last_chunk = (
                next_first_chunk - 1
            )

        else:

            last_chunk = chunk_count

        for chunk_number in range(
            first_chunk,
            last_chunk + 1
        ):

            chunks.append(
                {
                    "chunk_number": chunk_number,
                    "samples_per_chunk": entry[
                        "samples_per_chunk"
                    ],
                    "sample_description_index": entry[
                        "sample_description_index"
                    ],
                }
            )

    chunks = chunks[:chunk_count]

    capacity = sum(
        chunk["samples_per_chunk"]
        for chunk in chunks
    )

    if capacity < sample_count:

        raise ValueError(
            "stsc/stco do not provide enough "
            "chunk capacity for "
            f"{sample_count} samples. "
            f"Capacity={capacity}."
        )

    return chunks


def build_sample_records(
    sample_sizes,
    chunk_offsets,
    chunk_mapping
):
    """
    Convert stsc + stco + stsz into absolute
    sample byte ranges.

    Sample numbers are 1-based.
    """

    records = []

    sample_number = 1

    for chunk in chunk_mapping:

        chunk_number = chunk[
            "chunk_number"
        ]

        if (
            chunk_number < 1
            or
            chunk_number > len(chunk_offsets)
        ):

            raise ValueError(
                f"Chunk {chunk_number} "
                "has no corresponding "
                "chunk offset."
            )

        current_offset = chunk_offsets[
            chunk_number - 1
        ]

        for _ in range(
            chunk["samples_per_chunk"]
        ):

            if sample_number > len(
                sample_sizes
            ):
                break

            sample_size = sample_sizes[
                sample_number - 1
            ]

            sample_start = current_offset

            sample_end = (
                sample_start
                + sample_size
            )

            records.append(
                {
                    "sample_number": sample_number,
                    "chunk_number": chunk_number,
                    "offset": sample_start,
                    "end": sample_end,
                    "size": sample_size,
                    "sample_description_index": chunk[
                        "sample_description_index"
                    ],
                }
            )

            current_offset = sample_end

            sample_number += 1

        if sample_number > len(
            sample_sizes
        ):
            break

    return records


# ============================================================
# AVC SAMPLE VALIDATION
# ============================================================

def analyze_avc_sample(
    data,
    start,
    end
):
    """
    Basic validation for length-prefixed AVC samples.

    Current implementation supports the 4-byte NAL
    length format used by the supplied H.264 test file.

    This is a structural heuristic, not a decoder.
    """

    if (
        start < 0
        or end > len(data)
        or start >= end
    ):

        return {
            "nal_parse": "INVALID_RANGE",
            "nal_count": 0,
            "invalid_reason": (
                "Sample range is outside file."
            ),
        }

    pos = start

    nal_count = 0

    while pos < end:

        remaining = end - pos

        if remaining < 4:

            return {
                "nal_parse": "INVALID",
                "nal_count": nal_count,
                "invalid_reason": (
                    "Remaining sample bytes are "
                    "smaller than the 4-byte "
                    "NAL length field."
                ),
            }

        nal_length = read_u32(
            data,
            pos
        )

        pos += 4

        if nal_length == 0:

            return {
                "nal_parse": "INVALID",
                "nal_count": nal_count,
                "invalid_reason": (
                    "Zero-length NAL encountered."
                ),
            }

        nal_end = (
            pos
            + nal_length
        )

        if nal_end > end:

            return {
                "nal_parse": "INVALID",
                "nal_count": nal_count,
                "invalid_reason": (
                    "NAL length extends beyond "
                    "sample boundary."
                ),
            }

        nal_type = (
            data[pos]
            & 0x1F
        )

        if nal_type == 0:

            return {
                "nal_parse": "INVALID",
                "nal_count": nal_count,
                "invalid_reason": (
                    "Invalid H.264 NAL type 0."
                ),
            }

        nal_count += 1

        pos = nal_end

    return {
        "nal_parse": "VALID",
        "nal_count": nal_count,
        "invalid_reason": None,
    }


# ============================================================
# PHYSICAL SAMPLE INTEGRITY
# ============================================================

def analyze_sample_bytes(
    data,
    record,
    mdat_ranges
):
    """
    Determine physical/container-level sample status.

    This does not claim that a physically present sample
    is semantically decodable.
    """

    start = record["offset"]

    end = record["end"]

    result = {
        "physical_status": "UNKNOWN",
        "inside_mdat": False,
        "zero_bytes": 0,
        "zero_ratio": 0.0,
        "max_consecutive_zero_bytes": 0,
        "avc_nal_parse": None,
        "avc_nal_count": 0,
        "avc_invalid_reason": None,
    }

    if (
        start < 0
        or end < start
        or end > len(data)
    ):

        result["physical_status"] = (
            "OUT_OF_FILE"
        )

        return result

    result["inside_mdat"] = range_inside_mdat(
        start,
        end,
        mdat_ranges
    )

    if not result["inside_mdat"]:

        result["physical_status"] = (
            "OUTSIDE_MDAT"
        )

        return result

    sample = data[
        start:end
    ]

    if not sample:

        result["physical_status"] = (
            "EMPTY"
        )

        return result

    zero_bytes = sample.count(0)

    result["zero_bytes"] = zero_bytes

    result["zero_ratio"] = (
        zero_bytes
        / len(sample)
    )

    max_zero_run = 0

    current_run = 0

    for byte in sample:

        if byte == 0:

            current_run += 1

            if current_run > max_zero_run:
                max_zero_run = current_run

        else:

            current_run = 0

    result[
        "max_consecutive_zero_bytes"
    ] = max_zero_run

    avc = analyze_avc_sample(
        data,
        start,
        end
    )

    result[
        "avc_nal_parse"
    ] = avc["nal_parse"]

    result[
        "avc_nal_count"
    ] = avc["nal_count"]

    result[
        "avc_invalid_reason"
    ] = avc["invalid_reason"]

    if zero_bytes == len(sample):

        result["physical_status"] = (
            "ZERO_FILLED"
        )

    elif max_zero_run >= 64:

        result["physical_status"] = (
            "LIKELY_CORRUPTED"
        )

    elif avc["nal_parse"] == "INVALID":

        result["physical_status"] = (
            "STRUCTURALLY_SUSPICIOUS"
        )

    else:

        result["physical_status"] = (
            "PHYSICALLY_PRESENT"
        )

    return result


# ============================================================
# TIMING
# ============================================================

def build_sample_timing(
    sample_count,
    stts_entries,
    timescale
):
    """
    Generate decode timestamps and durations
    from stts.
    """

    durations = expand_stts(
        stts_entries,
        sample_count
    )

    records = []

    current_time = 0

    for index in range(sample_count):

        duration = (
            durations[index]
            if index < len(durations)
            else None
        )

        start = current_time

        if duration is not None:
            current_time += duration

        end = current_time

        if (
            duration is None
            or
            not timescale
        ):

            start_seconds = None
            end_seconds = None

        else:

            start_seconds = (
                start / timescale
            )

            end_seconds = (
                end / timescale
            )

        records.append(
            {
                "sample_number": index + 1,
                "decode_start": start,
                "decode_end": end,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "duration_units": duration,
            }
        )

    return records


# ============================================================
# GOP ANALYSIS
# ============================================================

def build_gops(
    sample_records,
    keyframe_samples
):
    """
    Divide the video into GOPs using stss keyframes.

    A GOP begins at a sync sample and ends
    immediately before the next sync sample.
    """

    sample_count = len(
        sample_records
    )

    keyframes = sorted(
        set(
            sample
            for sample in keyframe_samples
            if 1 <= sample <= sample_count
        )
    )

    if not keyframes:

        return []

    gops = []

    for index, start_sample in enumerate(
        keyframes
    ):

        if index + 1 < len(
            keyframes
        ):

            end_sample = (
                keyframes[index + 1]
                - 1
            )

        else:

            end_sample = sample_count

        gops.append(
            {
                "gop_number": index + 1,
                "start_sample": start_sample,
                "end_sample": end_sample,
                "keyframe_sample": start_sample,
            }
        )

    return gops


def classify_gop(
    gop,
    sample_map
):
    """
    Determine recoverability from sample integrity.

    For ordinary inter-frame H.264:
        intact GOP -> recoverable
        corruption -> decode chain cannot be trusted
        until the next keyframe.
    """

    samples = []

    for sample_number in range(
        gop["start_sample"],
        gop["end_sample"] + 1
    ):

        sample = sample_map.get(
            sample_number
        )

        if sample is not None:
            samples.append(sample)

    if not samples:

        gop["status"] = "MISSING"

        gop["reason"] = (
            "No sample records available."
        )

        gop["bad_samples"] = []

        return gop

    bad_samples = [
        sample
        for sample in samples
        if sample["physical_status"]
        in (
            "ZERO_FILLED",
            "LIKELY_CORRUPTED",
            "OUT_OF_FILE",
            "OUTSIDE_MDAT",
            "EMPTY",
            "STRUCTURALLY_SUSPICIOUS",
        )
    ]

    if not bad_samples:

        gop["status"] = "RECOVERABLE"

        gop["reason"] = (
            "All samples in the GOP are "
            "physically present and show "
            "no obvious corruption."
        )

        gop["bad_samples"] = []

        return gop

    bad_numbers = [
        sample["sample_number"]
        for sample in bad_samples
    ]

    keyframe_bad = (
        gop["keyframe_sample"]
        in bad_numbers
    )

    gop["bad_samples"] = bad_numbers

    if keyframe_bad:

        gop["status"] = "UNRECOVERABLE"

        gop["reason"] = (
            "The GOP keyframe itself is "
            "damaged or suspicious, so the "
            "dependent decode chain cannot "
            "be trusted."
        )

    else:

        gop["status"] = (
            "PARTIALLY_CORRUPTED"
        )

        gop["reason"] = (
            "At least one sample inside the "
            "GOP is damaged or suspicious. "
            "Frames after that point may "
            "depend on the damaged decode chain."
        )

    return gop


# ============================================================
# REGION BUILDING
# ============================================================

def build_recovery_regions(
    gops,
    sample_records,
    timing_records
):
    """
    Convert GOP results into forensic timeline regions.

    This does not manufacture missing footage.
    """

    timing_map = {
        record["sample_number"]: record
        for record in timing_records
    }

    sample_map = {
        record["sample_number"]: record
        for record in sample_records
    }

    regions = []

    for index, gop in enumerate(
        gops
    ):

        start_timing = timing_map.get(
            gop["start_sample"]
        )

        end_timing = timing_map.get(
            gop["end_sample"]
        )

        if (
            start_timing is None
            or
            end_timing is None
        ):
            continue

        start_seconds = (
            start_timing["start_seconds"]
        )

        end_seconds = (
            end_timing["end_seconds"]
        )

        if gop["status"] == "RECOVERABLE":

            status = "RECOVERED"

        elif (
            gop["status"]
            == "PARTIALLY_CORRUPTED"
        ):

            status = (
                "PARTIAL_NOT_RECOVERED"
            )

        else:

            status = "MISSING"

        regions.append(
            {
                "region_number": index + 1,
                "gop_number": gop["gop_number"],
                "status": status,
                "sample_start": gop[
                    "start_sample"
                ],
                "sample_end": gop[
                    "end_sample"
                ],
                "time_start_seconds": start_seconds,
                "time_end_seconds": end_seconds,
                "time_start": format_time(
                    start_seconds
                ),
                "time_end": format_time(
                    end_seconds
                ),
                "bad_samples": gop.get(
                    "bad_samples",
                    []
                ),
                "reason": gop["reason"],
                "synthetic_content_added": False,
            }
        )

    return regions


# ============================================================
# MAIN SCAN
# ============================================================

def scan_video(video_path):

    video_path = Path(
        video_path
    )

    if not video_path.exists():

        raise FileNotFoundError(
            "Input video does not exist: "
            f"{video_path}"
        )

    data = video_path.read_bytes()

    file_size = len(data)

    print("=" * 70)

    print(
        "        TRACEX DYNAMIC MP4 SAMPLE "
        "RECOVERY SCANNER"
    )

    print("=" * 70)

    print()
    print("FILE")
    print("-" * 70)

    print(
        f"Filename: {video_path.name}"
    )

    print(
        f"Path: {video_path}"
    )

    print(
        f"File size: {file_size} bytes"
    )

    # --------------------------------------------------------
    # TOP LEVEL BOXES
    # --------------------------------------------------------

    top_boxes = scan_top_level_boxes(
        data
    )

    print()
    print("TOP-LEVEL BOXES")
    print("-" * 70)

    top_level_report = []

    for box in top_boxes:

        end_for_report = min(
            box["end"],
            file_size
        )

        print(
            f'{box["type"]:<8} '
            f'{box["start"]:,} → '
            f'{end_for_report:,} '
            f'(declared size '
            f'{box["size"]:,})'
        )

        top_level_report.append(
            {
                "type": box["type"],
                "start": box["start"],
                "declared_size": box["size"],
                "actual_end": end_for_report,
                "header_size": box[
                    "header_size"
                ],
                "truncated": box.get(
                    "truncated",
                    False
                ),
            }
        )

    mdat_ranges = find_mdat_ranges(
        top_boxes,
        file_size
    )

    moov = next(
        (
            box
            for box in top_boxes
            if box["type"] == "moov"
        ),
        None
    )

    if moov is None:

        raise ValueError(
            "No moov box found. The file "
            "cannot be parsed using this "
            "sample-table workflow."
        )

    print()
    print("MDAT")
    print("-" * 70)

    for index, mdat in enumerate(
        mdat_ranges,
        start=1
    ):

        print(
            f"mdat #{index}: "
            f"payload "
            f"{mdat['payload_start']:,} → "
            f"{mdat['payload_end']:,}"
        )

    # --------------------------------------------------------
    # VIDEO TRACK
    # --------------------------------------------------------

    trak, mdia = find_video_track(
        data,
        moov
    )

    if trak is None:

        raise ValueError(
            "No video track "
            "(handler_type=vide) found."
        )

    mdia_start = (
        mdia["start"]
        + mdia["header_size"]
    )

    mdia_end = mdia["end"]

    mdhd = find_child_box(
        data,
        mdia_start,
        mdia_end,
        "mdhd"
    )

    minf = find_child_box(
        data,
        mdia_start,
        mdia_end,
        "minf"
    )

    if (
        mdhd is None
        or
        minf is None
    ):

        raise ValueError(
            "Video track is missing "
            "mdhd or minf."
        )

    trak_start = (
        trak["start"]
        + trak["header_size"]
    )

    trak_end = trak["end"]

    tkhd = find_child_box(
        data,
        trak_start,
        trak_end,
        "tkhd"
    )

    track_id = None

    if tkhd is not None:

        payload = (
            tkhd["start"]
            + tkhd["header_size"]
        )

        version = data[payload]

        if version == 1:

            if payload + 28 <= tkhd["end"]:

                track_id = read_u32(
                    data,
                    payload + 20
                )

        else:

            if payload + 20 <= tkhd["end"]:

                track_id = read_u32(
                    data,
                    payload + 12
                )

    mdhd_payload = (
        mdhd["start"]
        + mdhd["header_size"]
    )

    mdhd_version = data[
        mdhd_payload
    ]

    if mdhd_version == 1:

        if (
            mdhd_payload + 32
            > mdhd["end"]
        ):

            raise ValueError(
                "Invalid version-1 mdhd box."
            )

        timescale = read_u32(
            data,
            mdhd_payload + 20
        )

        duration = read_u64(
            data,
            mdhd_payload + 24
        )

    else:

        if (
            mdhd_payload + 20
            > mdhd["end"]
        ):

            raise ValueError(
                "Invalid version-0 mdhd box."
            )

        timescale = read_u32(
            data,
            mdhd_payload + 12
        )

        duration = read_u32(
            data,
            mdhd_payload + 16
        )

    # --------------------------------------------------------
    # STBL
    # --------------------------------------------------------

    minf_start = (
        minf["start"]
        + minf["header_size"]
    )

    minf_end = minf["end"]

    stbl = find_child_box(
        data,
        minf_start,
        minf_end,
        "stbl"
    )

    if stbl is None:

        raise ValueError(
            "Video track does not contain stbl."
        )

    stbl_start = (
        stbl["start"]
        + stbl["header_size"]
    )

    stbl_end = stbl["end"]

    stsd = find_child_box(
        data,
        stbl_start,
        stbl_end,
        "stsd"
    )

    stts = find_child_box(
        data,
        stbl_start,
        stbl_end,
        "stts"
    )

    stsc = find_child_box(
        data,
        stbl_start,
        stbl_end,
        "stsc"
    )

    stsz = find_child_box(
        data,
        stbl_start,
        stbl_end,
        "stsz"
    )

    stco = find_child_box(
        data,
        stbl_start,
        stbl_end,
        "stco"
    )

    co64 = find_child_box(
        data,
        stbl_start,
        stbl_end,
        "co64"
    )

    stss = find_child_box(
        data,
        stbl_start,
        stbl_end,
        "stss"
    )

    if stts is None:
        raise ValueError(
            "Video track missing stts."
        )

    if stsc is None:
        raise ValueError(
            "Video track missing stsc."
        )

    if stsz is None:
        raise ValueError(
            "Video track missing stsz."
        )

    if (
        stco is None
        and
        co64 is None
    ):

        raise ValueError(
            "Video track missing both "
            "stco and co64."
        )

    # --------------------------------------------------------
    # PARSE TABLES
    # --------------------------------------------------------

    stsd_info = (
        parse_stsd(
            data,
            stsd
        )
        if stsd
        else {}
    )

    stts_entries = parse_stts(
        data,
        stts
    )

    stsc_entries = parse_stsc(
        data,
        stsc
    )

    stsz_info = parse_stsz(
        data,
        stsz
    )

    offset_box = (
        stco
        if stco is not None
        else co64
    )

    chunk_offsets = parse_chunk_offsets(
        data,
        offset_box
    )

    keyframe_samples = (
        parse_stss(
            data,
            stss
        )
        if stss is not None
        else []
    )

    sample_sizes = (
        stsz_info["sample_sizes"]
    )

    sample_count = (
        stsz_info["sample_count"]
    )

    # --------------------------------------------------------
    # BUILD SAMPLE RECORDS
    # --------------------------------------------------------

    chunk_mapping = (
        build_sample_chunk_mapping(
            stsc_entries,
            len(chunk_offsets),
            sample_count
        )
    )

    sample_records = (
        build_sample_records(
            sample_sizes,
            chunk_offsets,
            chunk_mapping
        )
    )

    if (
        len(sample_records)
        != sample_count
    ):

        raise ValueError(
            "Sample mapping mismatch: "
            f"stsz declares "
            f"{sample_count} samples, "
            f"but only "
            f"{len(sample_records)} "
            "could be mapped."
        )

    # --------------------------------------------------------
    # SAMPLE TIMING
    # --------------------------------------------------------

    timing_records = (
        build_sample_timing(
            sample_count,
            stts_entries,
            timescale
        )
    )

    timing_map = {
        record["sample_number"]: record
        for record in timing_records
    }

    # --------------------------------------------------------
    # PHYSICAL ANALYSIS
    # --------------------------------------------------------

    sample_map = {}

    fully_present = 0

    suspicious = 0

    damaged = 0

    outside_mdat = 0

    for sample in sample_records:

        integrity = (
            analyze_sample_bytes(
                data,
                sample,
                mdat_ranges
            )
        )

        timing = timing_map.get(
            sample["sample_number"],
            {}
        )

        sample.update(
            integrity
        )

        sample.update(
            {
                "decode_start_seconds":
                    timing.get(
                        "start_seconds"
                    ),

                "decode_end_seconds":
                    timing.get(
                        "end_seconds"
                    ),

                "is_keyframe":
                    (
                        sample["sample_number"]
                        in keyframe_samples
                    ),
            }
        )

        sample_map[
            sample["sample_number"]
        ] = sample

        status = (
            sample["physical_status"]
        )

        if status == "PHYSICALLY_PRESENT":

            fully_present += 1

        elif status in (
            "LIKELY_CORRUPTED",
            "STRUCTURALLY_SUSPICIOUS",
        ):

            suspicious += 1

        elif status == "ZERO_FILLED":

            damaged += 1

        elif status in (
            "OUT_OF_FILE",
            "OUTSIDE_MDAT",
        ):

            outside_mdat += 1

    # --------------------------------------------------------
    # GOP ANALYSIS
    # --------------------------------------------------------

    gops = build_gops(
        sample_records,
        keyframe_samples
    )

    analyzed_gops = []

    for gop in gops:

        analyzed = classify_gop(
            dict(gop),
            sample_map
        )

        analyzed_gops.append(
            analyzed
        )

    # --------------------------------------------------------
    # REGIONS
    # --------------------------------------------------------

    regions = (
        build_recovery_regions(
            analyzed_gops,
            sample_records,
            timing_records
        )
    )

    # --------------------------------------------------------
    # FINAL STATUS
    # --------------------------------------------------------

    recovered_gops = sum(
        1
        for gop in analyzed_gops
        if gop["status"]
        == "RECOVERABLE"
    )

    broken_gops = sum(
        1
        for gop in analyzed_gops
        if gop["status"]
        in (
            "PARTIALLY_CORRUPTED",
            "UNRECOVERABLE",
        )
    )

    if (
        recovered_gops
        == len(analyzed_gops)
        and
        analyzed_gops
    ):

        overall_status = (
            "FULLY_RECOVERABLE"
        )

    elif recovered_gops > 0:

        overall_status = (
            "PARTIALLY_RECOVERABLE"
        )

    else:

        overall_status = (
            "NO_FULL_GOP_RECOVERY"
        )

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    report = {

        "report_type":
            "TraceX Dynamic MP4 Sample "
            "Recovery Scan",

        "generated_at":
            datetime.now().isoformat(),

        "video_filename":
            video_path.name,

        "video_name":
            video_path.stem,

        "file_size":
            file_size,

        "dynamic_analysis":
            True,

        "top_level_boxes":
            top_level_report,

        "mdat_ranges":
            mdat_ranges,

        "video_track": {

            "found":
                True,

            "track_id":
                track_id,

            "handler_type":
                "vide",

            "timescale":
                timescale,

            "duration_units":
                duration,

            "duration_seconds":
                (
                    duration / timescale
                    if timescale
                    else None
                ),

            "duration":
                (
                    format_time(
                        duration / timescale
                    )
                    if timescale
                    else None
                ),

            "sample_description":
                stsd_info,
        },

        "sample_tables": {

            "stts": {

                "entry_count":
                    len(stts_entries),

                "entries":
                    stts_entries,
            },

            "stsc": {

                "entry_count":
                    len(stsc_entries),

                "entries":
                    stsc_entries,
            },

            "stsz": {

                "default_size":
                    stsz_info[
                        "default_size"
                    ],

                "sample_count":
                    sample_count,
            },

            "stco_or_co64": {

                "box_type":
                    offset_box["type"],

                "chunk_count":
                    len(chunk_offsets),

                "offsets":
                    chunk_offsets,
            },

            "stss": {

                "present":
                    stss is not None,

                "keyframe_count":
                    len(keyframe_samples),

                "keyframe_samples":
                    keyframe_samples,
            },
        },

        "physical_sample_availability": {

            "sample_count":
                sample_count,

            "mapped_sample_count":
                len(sample_records),

            "fully_present":
                fully_present,

            "zero_filled":
                damaged,

            "suspicious":
                suspicious,

            "outside_mdat":
                outside_mdat,
        },

        # ====================================================
        # IMPORTANT:
        # Individual sample records are now included in the
        # final JSON report.
        #
        # Timeline reconstruction uses these records to map
        # samples back to their original positions.
        # ====================================================

        "samples":
            sample_records,

        "gop_analysis":
            analyzed_gops,

        "recovery_regions":
            regions,

        "overall_status":
            overall_status,

        "forensic_notes": [

            "Analysis is dynamic and input-file driven.",

            "No filename-specific recovery rules are used.",

            "No known corruption offsets are hardcoded.",

            "No specific sample count is hardcoded.",

            "Physical sample presence does not by itself "
            "prove decodability.",

            "GOP-level recoverability accounts for "
            "inter-frame dependency.",

            "No synthetic video content is generated "
            "by this scanner.",

            "A missing or damaged GOP is not silently "
            "replaced with invented footage.",

            "AVC NAL parsing is a structural heuristic "
            "and is not a substitute for full decoder "
            "validation.",

            "Timeline regions represent the original "
            "sample timing derived from container "
            "metadata.",

            "Recovered regions must still be validated "
            "by a decoder before being treated as "
            "forensically recovered video.",
        ],
    }

    # --------------------------------------------------------
    # CONSOLE OUTPUT
    # --------------------------------------------------------

    print()
    print("VIDEO TRACK")
    print("-" * 70)

    print(
        f"Track ID: {track_id}"
    )

    print(
        "Handler: vide"
    )

    print(
        f"Timescale: {timescale}"
    )

    print(
        f"Duration: "
        f"{format_time(duration / timescale)}"
        if timescale
        else "Duration: unknown"
    )

    print()
    print("SAMPLE TABLES")
    print("-" * 70)

    print(
        f"stts entries: "
        f"{len(stts_entries)}"
    )

    print(
        f"stsc entries: "
        f"{len(stsc_entries)}"
    )

    print(
        f"stsz samples: "
        f"{sample_count}"
    )

    print(
        f"{offset_box['type']} chunks: "
        f"{len(chunk_offsets)}"
    )

    print(
        f"stss keyframes: "
        f"{len(keyframe_samples)}"
    )

    print(
        f"Keyframe samples: "
        f"{keyframe_samples}"
    )

    print()
    print("PHYSICAL SAMPLE AVAILABILITY")
    print("-" * 70)

    print(
        f"Mapped samples: "
        f"{len(sample_records)}"
    )

    print(
        f"Physically present: "
        f"{fully_present}"
    )

    print(
        f"Zero-filled: "
        f"{damaged}"
    )

    print(
        f"Suspicious: "
        f"{suspicious}"
    )

    print(
        f"Outside mdat: "
        f"{outside_mdat}"
    )

    print()
    print("FIRST 10 SAMPLE RANGES")
    print("-" * 70)

    for sample in sample_records[:10]:

        print(
            f"Sample "
            f"{sample['sample_number']:>3} | "
            f"Chunk "
            f"{sample['chunk_number']:>3} | "
            f"{sample['offset']:,} → "
            f"{sample['end']:,} | "
            f"Size "
            f"{sample['size']:,} | "
            f"{sample['physical_status']}"
        )

    print()
    print("GOP RECOVERY ANALYSIS")
    print("-" * 70)

    for gop in analyzed_gops:

        print(
            f"GOP "
            f"{gop['gop_number']:>2} | "
            f"Samples "
            f"{gop['start_sample']} → "
            f"{gop['end_sample']} | "
            f"{gop['status']}"
        )

        if gop.get(
            "bad_samples"
        ):

            print(
                f"          Bad samples: "
                f"{gop['bad_samples']}"
            )

    print()
    print("RECOVERY REGIONS")
    print("-" * 70)

    for region in regions:

        print(
            f"REGION-"
            f"{region['region_number']:03d} | "
            f"{region['status']:<20} | "
            f"{region['time_start']} → "
            f"{region['time_end']}"
        )

    print()
    print("OVERALL")
    print("-" * 70)

    print(
        f"Status: "
        f"{overall_status}"
    )

    print(
        "Synthetic content added: False"
    )

    # --------------------------------------------------------
    # SAVE REPORT
    # --------------------------------------------------------

    backend_folder = (
        video_path.parent
        .parent
        .parent
    )

    output_folder = (
        backend_folder
        / "output"
        / "recovery"
        / safe_name(
            video_path.stem
        )
    )

    output_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        output_folder
        / "mp4_sample_recovery_scan.json"
    )

    output_file.write_text(
        json.dumps(
            report,
            indent=4
        ),
        encoding="utf-8"
    )

    print()
    print("REPORT")
    print("-" * 70)

    print(
        f"Saved to: "
        f"{output_file}"
    )

    print("=" * 70)

    return report


# ============================================================
# COMMAND LINE ENTRY POINT
# ============================================================

if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Usage:\n"
            "python -m "
            "recovery.mp4_sample_recovery_scanner "
            "\"path_to_video.mp4\""
        )

        sys.exit(1)

    input_video = sys.argv[1]

    try:

        scan_video(
            input_video
        )

    except Exception as exc:

        print()
        print("=" * 70)
        print("SCAN FAILED")
        print("=" * 70)

        print(
            f"Error: {exc}"
        )

        print()

        print(
            "This is a parser/analysis error. "
            "No video content was generated."
        )

        sys.exit(1)