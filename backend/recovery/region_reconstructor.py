import json
import os
import struct
import subprocess
import tempfile
from pathlib import Path


# ================================================================
# TRACEX REGION-BASED FORENSIC RECONSTRUCTION
# ================================================================
#
# Purpose:
#   Recover independently recoverable MP4/H.264 timeline regions
#   from a damaged MP4.
#
# Important forensic rule:
#   This program NEVER invents video frames.
#
#   It only uses sample bytes that are physically present and
#   marked recoverable by the forensic MP4 sample scanner.
#
# Output:
#   - One MP4 for every recoverable region
#   - One forensic reconstruction manifest
#
# The final MP4 regions are NOT claimed to be continuous with
# missing regions. Original timeline positions are preserved in
# the manifest.
# ================================================================


# ----------------------------------------------------------------
# BASIC HELPERS
# ----------------------------------------------------------------

def run_command(command):
    """
    Run an external command and return:
        success, stdout, stderr
    """

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        return (
            result.returncode == 0,
            result.stdout,
            result.stderr
        )

    except Exception as exc:
        return False, "", str(exc)


def format_time(seconds):
    """
    Convert seconds into HH:MM:SS.mmm
    """

    if seconds is None:
        seconds = 0.0

    seconds = float(seconds)

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def read_u32(data, offset):
    return struct.unpack_from(">I", data, offset)[0]


def read_u64(data, offset):
    return struct.unpack_from(">Q", data, offset)[0]


# ----------------------------------------------------------------
# MP4 BOX HELPERS
# ----------------------------------------------------------------

def iter_top_level_boxes(data):
    """
    Read top-level MP4 boxes.
    """

    boxes = []

    pos = 0
    data_len = len(data)

    while pos + 8 <= data_len:

        size = read_u32(data, pos)
        box_type = data[pos + 4:pos + 8]

        header_size = 8

        if size == 1:

            if pos + 16 > data_len:
                break

            size = read_u64(data, pos + 8)
            header_size = 16

        elif size == 0:

            size = data_len - pos

        if size < header_size:
            break

        end = pos + size

        if end > data_len:
            end = data_len

        boxes.append({
            "type": box_type.decode("latin1", errors="replace"),
            "start": pos,
            "end": end,
            "size": size,
            "header_size": header_size
        })

        if end <= pos:
            break

        pos = end

    return boxes


def find_all_box_markers(data, marker):
    """
    Return all raw positions of a four-byte box marker.
    """

    positions = []

    start = 0

    while True:

        pos = data.find(marker, start)

        if pos == -1:
            break

        positions.append(pos)

        start = pos + 1

    return positions


# ----------------------------------------------------------------
# AVC CONFIGURATION
# ----------------------------------------------------------------

def extract_avcc(source_bytes):
    """
    Extract AVCDecoderConfigurationRecord directly from avcC.

    We intentionally do NOT use the previous recursive MP4 parser.

    MP4's stsd and avc1 structures contain special fixed headers,
    which caused the previous recursive parser to miss avcC.

    The actual file has already been confirmed to contain:

        00 00 00 37 61 76 63 43

    at byte 2068270.
    """

    marker = b"avcC"

    positions = find_all_box_markers(source_bytes, marker)

    if not positions:
        raise RuntimeError(
            "Could not find avcC codec configuration."
        )

    # In this file the first valid avcC is the video configuration.
    for marker_pos in positions:

        if marker_pos < 4:
            continue

        box_start = marker_pos - 4

        box_size = read_u32(source_bytes, box_start)

        if box_size < 8:
            continue

        box_end = box_start + box_size

        if box_end > len(source_bytes):
            continue

        if source_bytes[marker_pos:marker_pos + 4] != b"avcC":
            continue

        payload_start = marker_pos + 4
        payload = source_bytes[payload_start:box_end]

        if len(payload) < 7:
            continue

        if payload[0] != 1:
            continue

        print()
        print("AVC CONFIGURATION")
        print("─" * 64)
        print(f"avcC found at byte: {marker_pos}")
        print(f"avcC box size: {box_size} bytes")
        print(f"avcC payload size: {len(payload)} bytes")

        return payload

    raise RuntimeError(
        "avcC marker was found, but no valid AVC configuration "
        "record could be parsed."
    )


def parse_avcc(avcc):
    """
    Parse AVCDecoderConfigurationRecord.

    Returns:
        {
            "nal_length_size": ...,
            "sps": [...],
            "pps": [...]
        }
    """

    if len(avcc) < 7:
        raise RuntimeError("Invalid avcC payload.")

    configuration_version = avcc[0]

    if configuration_version != 1:
        raise RuntimeError(
            f"Unsupported avcC configuration version: "
            f"{configuration_version}"
        )

    profile = avcc[1]
    compatibility = avcc[2]
    level = avcc[3]

    nal_length_size = (avcc[4] & 0x03) + 1

    num_sps = avcc[5] & 0x1F

    offset = 6

    sps_list = []
    pps_list = []

    for _ in range(num_sps):

        if offset + 2 > len(avcc):
            raise RuntimeError(
                "Invalid avcC SPS length."
            )

        sps_length = struct.unpack_from(
            ">H",
            avcc,
            offset
        )[0]

        offset += 2

        if offset + sps_length > len(avcc):
            raise RuntimeError(
                "Invalid avcC SPS data."
            )

        sps = avcc[offset:offset + sps_length]

        offset += sps_length

        sps_list.append(sps)

    if offset >= len(avcc):
        raise RuntimeError(
            "Invalid avcC PPS section."
        )

    num_pps = avcc[offset]

    offset += 1

    for _ in range(num_pps):

        if offset + 2 > len(avcc):
            raise RuntimeError(
                "Invalid avcC PPS length."
            )

        pps_length = struct.unpack_from(
            ">H",
            avcc,
            offset
        )[0]

        offset += 2

        if offset + pps_length > len(avcc):
            raise RuntimeError(
                "Invalid avcC PPS data."
            )

        pps = avcc[offset:offset + pps_length]

        offset += pps_length

        pps_list.append(pps)

    return {
        "profile": profile,
        "compatibility": compatibility,
        "level": level,
        "nal_length_size": nal_length_size,
        "sps": sps_list,
        "pps": pps_list
    }


# ----------------------------------------------------------------
# MP4 SAMPLE TABLE LOCATOR
# ----------------------------------------------------------------

def find_box_recursive(data, target, start=0, end=None):
    """
    Generic byte-level search for a box marker.

    This is intentionally conservative.

    We primarily use direct marker searches because stsd/avc1
    have special structures.
    """

    if end is None:
        end = len(data)

    marker = target.encode("latin1")

    positions = []

    cursor = start

    while True:

        pos = data.find(marker, cursor, end)

        if pos == -1:
            break

        if pos >= 4:

            box_start = pos - 4

            try:
                box_size = read_u32(data, box_start)

                if box_size >= 8:
                    box_end = box_start + box_size

                    if box_end <= end:
                        positions.append({
                            "start": box_start,
                            "type": target,
                            "size": box_size,
                            "end": box_end
                        })

            except Exception:
                pass

        cursor = pos + 1

    return positions


def find_first_valid_box(data, box_type, search_start=0):
    """
    Find the first valid box of a particular type.
    """

    results = find_box_recursive(
        data,
        box_type,
        search_start,
        len(data)
    )

    if not results:
        return None

    return results[0]


# ----------------------------------------------------------------
# STTS
# ----------------------------------------------------------------

def parse_stts(data, box):
    """
    Parse decoding time-to-sample table.

    Returns a list containing duration of each video sample
    in media timescale units.
    """

    start = box["start"]

    version_flags = data[start + 8:start + 12]

    entry_count = read_u32(data, start + 12)

    offset = start + 16

    durations = []

    for _ in range(entry_count):

        if offset + 8 > box["end"]:
            break

        sample_count = read_u32(data, offset)
        sample_delta = read_u32(data, offset + 4)

        offset += 8

        for _ in range(sample_count):
            durations.append(sample_delta)

    return durations


# ----------------------------------------------------------------
# STSZ
# ----------------------------------------------------------------

def parse_stsz(data, box):
    """
    Parse sample sizes.
    """

    start = box["start"]

    sample_size = read_u32(data, start + 12)
    sample_count = read_u32(data, start + 16)

    offset = start + 20

    if sample_size != 0:

        return [sample_size] * sample_count

    sizes = []

    for _ in range(sample_count):

        if offset + 4 > box["end"]:
            break

        sizes.append(
            read_u32(data, offset)
        )

        offset += 4

    return sizes


# ----------------------------------------------------------------
# STCO / CO64
# ----------------------------------------------------------------

def parse_chunk_offsets(data, box):
    """
    Parse chunk offsets.
    """

    start = box["start"]

    entry_count = read_u32(data, start + 12)

    offset = start + 16

    offsets = []

    for _ in range(entry_count):

        if offset + 4 > box["end"]:
            break

        offsets.append(
            read_u32(data, offset)
        )

        offset += 4

    return offsets


def parse_chunk_offsets_64(data, box):
    """
    Parse 64-bit chunk offsets.
    """

    start = box["start"]

    entry_count = read_u32(data, start + 12)

    offset = start + 16

    offsets = []

    for _ in range(entry_count):

        if offset + 8 > box["end"]:
            break

        offsets.append(
            read_u64(data, offset)
        )

        offset += 8

    return offsets


# ----------------------------------------------------------------
# STSC
# ----------------------------------------------------------------

def parse_stsc(data, box):
    """
    Parse sample-to-chunk table.

    Returns entries:
        {
            first_chunk,
            samples_per_chunk,
            sample_description_index
        }
    """

    start = box["start"]

    entry_count = read_u32(data, start + 12)

    offset = start + 16

    entries = []

    for _ in range(entry_count):

        if offset + 12 > box["end"]:
            break

        first_chunk = read_u32(data, offset)
        samples_per_chunk = read_u32(data, offset + 4)
        sample_description_index = read_u32(data, offset + 8)

        offset += 12

        entries.append({
            "first_chunk": first_chunk,
            "samples_per_chunk": samples_per_chunk,
            "sample_description_index":
                sample_description_index
        })

    return entries


# ----------------------------------------------------------------
# STSS
# ----------------------------------------------------------------

def parse_stss(data, box):
    """
    Parse sync samples / keyframes.
    """

    start = box["start"]

    entry_count = read_u32(data, start + 12)

    offset = start + 16

    keyframes = []

    for _ in range(entry_count):

        if offset + 4 > box["end"]:
            break

        keyframes.append(
            read_u32(data, offset)
        )

        offset += 4

    return keyframes


# ----------------------------------------------------------------
# STSD / VIDEO TRACK DISCOVERY
# ----------------------------------------------------------------

def locate_video_sample_tables(data):
    """
    Locate the video track's sample tables.

    For this project the MP4 contains a normal:
        moov
          trak
            mdia
              minf
                stbl

    We locate the relevant boxes by searching inside moov.
    """

    top_boxes = iter_top_level_boxes(data)

    moov = None

    for box in top_boxes:

        if box["type"] == "moov":

            moov = box
            break

    if moov is None:
        raise RuntimeError("moov box not found.")

    moov_start = moov["start"]
    moov_end = moov["end"]

    print()
    print("MP4 STRUCTURE")
    print("─" * 64)
    print(
        f"moov: {moov_start} → {moov_end}"
    )

    # Find handler boxes.
    handler_boxes = find_box_recursive(
        data,
        "hdlr",
        moov_start,
        moov_end
    )

    video_handler = None

    for handler in handler_boxes:

        payload_start = handler["start"] + 8

        # FullBox header = 4 bytes
        # pre_defined = 4 bytes
        # handler_type begins at +16
        handler_type_pos = handler["start"] + 16

        if handler_type_pos + 4 <= handler["end"]:

            handler_type = data[
                handler_type_pos:
                handler_type_pos + 4
            ]

            if handler_type == b"vide":

                video_handler = handler
                break

    if video_handler is None:
        raise RuntimeError(
            "Could not locate video handler."
        )

    # Find the trak enclosing the video handler.
    traks = find_box_recursive(
        data,
        "trak",
        moov_start,
        moov_end
    )

    video_trak = None

    for trak in traks:

        if (
            trak["start"] <= video_handler["start"]
            and video_handler["end"] <= trak["end"]
        ):

            video_trak = trak
            break

    if video_trak is None:

        # Fallback: use the first trak that contains a vide handler.
        for trak in traks:

            nested_handlers = find_box_recursive(
                data,
                "hdlr",
                trak["start"],
                trak["end"]
            )

            for handler in nested_handlers:

                if handler["start"] + 20 <= handler["end"]:

                    handler_type = data[
                        handler["start"] + 16:
                        handler["start"] + 20
                    ]

                    if handler_type == b"vide":

                        video_trak = trak
                        break

            if video_trak:
                break

    if video_trak is None:
        raise RuntimeError(
            "Could not locate video trak."
        )

    stbl_boxes = find_box_recursive(
        data,
        "stbl",
        video_trak["start"],
        video_trak["end"]
    )

    if not stbl_boxes:
        raise RuntimeError(
            "Could not locate video stbl."
        )

    stbl = stbl_boxes[0]

    return {
        "moov": moov,
        "video_trak": video_trak,
        "stbl": stbl
    }


# ----------------------------------------------------------------
# VIDEO TIMESCALE
# ----------------------------------------------------------------

def locate_video_timescale(data, video_trak):
    """
    Find mdhd in the video track and return timescale.
    """

    mdhd_boxes = find_box_recursive(
        data,
        "mdhd",
        video_trak["start"],
        video_trak["end"]
    )

    if not mdhd_boxes:
        raise RuntimeError(
            "Could not locate video mdhd."
        )

    mdhd = mdhd_boxes[0]

    version = data[mdhd["start"] + 8]

    if version == 0:

        timescale_offset = mdhd["start"] + 20

    else:

        timescale_offset = mdhd["start"] + 28

    timescale = read_u32(
        data,
        timescale_offset
    )

    return timescale


# ----------------------------------------------------------------
# SAMPLE MAP
# ----------------------------------------------------------------

def build_sample_map(source_bytes):
    """
    Build exact byte ranges for every video sample.

    Returns a list indexed by sample number - 1.

    Each record contains:
        sample_number
        byte_start
        byte_end
        size
        chunk
    """

    structure = locate_video_sample_tables(
        source_bytes
    )

    stbl = structure["stbl"]

    stts_boxes = find_box_recursive(
        source_bytes,
        "stts",
        stbl["start"],
        stbl["end"]
    )

    stsc_boxes = find_box_recursive(
        source_bytes,
        "stsc",
        stbl["start"],
        stbl["end"]
    )

    stsz_boxes = find_box_recursive(
        source_bytes,
        "stsz",
        stbl["start"],
        stbl["end"]
    )

    stco_boxes = find_box_recursive(
        source_bytes,
        "stco",
        stbl["start"],
        stbl["end"]
    )

    co64_boxes = find_box_recursive(
        source_bytes,
        "co64",
        stbl["start"],
        stbl["end"]
    )

    stss_boxes = find_box_recursive(
        source_bytes,
        "stss",
        stbl["start"],
        stbl["end"]
    )

    if not stsc_boxes:
        raise RuntimeError("stsc box not found.")

    if not stsz_boxes:
        raise RuntimeError("stsz box not found.")

    if not stco_boxes and not co64_boxes:
        raise RuntimeError(
            "Neither stco nor co64 box was found."
        )

    stsc = parse_stsc(
        source_bytes,
        stsc_boxes[0]
    )

    sample_sizes = parse_stsz(
        source_bytes,
        stsz_boxes[0]
    )

    if stco_boxes:

        chunk_offsets = parse_chunk_offsets(
            source_bytes,
            stco_boxes[0]
        )

    else:

        chunk_offsets = parse_chunk_offsets_64(
            source_bytes,
            co64_boxes[0]
        )

    sample_durations = []

    if stts_boxes:

        sample_durations = parse_stts(
            source_bytes,
            stts_boxes[0]
        )

    keyframes = set()

    if stss_boxes:

        keyframes = set(
            parse_stss(
                source_bytes,
                stss_boxes[0]
            )
        )

    sample_records = []

    sample_number = 1

    # MP4 chunk numbering starts at 1.
    for chunk_index in range(
        1,
        len(chunk_offsets) + 1
    ):

        chunk_offset = chunk_offsets[
            chunk_index - 1
        ]

        # Determine samples_per_chunk.
        samples_per_chunk = None

        for i, entry in enumerate(stsc):

            current_first = entry["first_chunk"]

            if i + 1 < len(stsc):

                next_first = stsc[
                    i + 1
                ]["first_chunk"]

            else:

                next_first = float("inf")

            if (
                current_first
                <= chunk_index
                < next_first
            ):

                samples_per_chunk = entry[
                    "samples_per_chunk"
                ]

                break

        if samples_per_chunk is None:
            continue

        current_offset = chunk_offset

        for _ in range(samples_per_chunk):

            if sample_number > len(sample_sizes):
                break

            size = sample_sizes[
                sample_number - 1
            ]

            byte_start = current_offset
            byte_end = current_offset + size

            inside_file = (
                byte_start >= 0
                and byte_end <= len(source_bytes)
                and byte_end > byte_start
            )

            sample_records.append({
                "sample_number": sample_number,
                "byte_start": byte_start,
                "byte_end": byte_end,
                "size": size,
                "chunk": chunk_index,
                "keyframe": sample_number in keyframes,
                "physically_inside_file": inside_file
            })

            current_offset += size
            sample_number += 1

    # Attach durations and timestamps.
    current_time = 0

    for index, record in enumerate(sample_records):

        if index < len(sample_durations):

            duration = sample_durations[index]

        else:

            # Fallback to previous duration.
            if index > 0:
                duration = sample_records[
                    index - 1
                ].get(
                    "duration_timescale",
                    1
                )

            else:
                duration = 1

        record["duration_timescale"] = duration
        record["timestamp_timescale"] = current_time

        current_time += duration

    return (
        structure,
        sample_records,
        keyframes
    )


# ----------------------------------------------------------------
# SAMPLE STATUS
# ----------------------------------------------------------------

def sample_is_zero_filled(source_bytes, sample):
    """
    Determine whether an entire sample is zero-filled.
    """

    start = sample["byte_start"]
    end = sample["byte_end"]

    if start < 0 or end > len(source_bytes):
        return False

    sample_bytes = source_bytes[
        start:end
    ]

    if not sample_bytes:
        return True

    return all(
        value == 0
        for value in sample_bytes
    )


def sample_is_usable(source_bytes, sample):
    """
    A sample is usable only when:
      1. Its full byte range exists.
      2. It is not entirely zero-filled.
    """

    if not sample["physically_inside_file"]:
        return False

    if sample_is_zero_filled(
        source_bytes,
        sample
    ):
        return False

    return True


# ----------------------------------------------------------------
# ANNEX-B CONVERSION
# ----------------------------------------------------------------

def sample_to_annex_b(
    sample_bytes,
    nal_length_size
):
    """
    Convert MP4 length-prefixed AVC samples into Annex-B.

    MP4 AVC sample:

        [NAL length][NAL data]
        [NAL length][NAL data]
        ...

    Annex-B:

        00 00 00 01 [NAL data]
        00 00 00 01 [NAL data]
        ...
    """

    output = bytearray()

    offset = 0

    while offset < len(sample_bytes):

        if offset + nal_length_size > len(sample_bytes):
            break

        if nal_length_size == 1:

            nal_length = sample_bytes[
                offset
            ]

        elif nal_length_size == 2:

            nal_length = struct.unpack_from(
                ">H",
                sample_bytes,
                offset
            )[0]

        elif nal_length_size == 3:

            nal_length = (
                (sample_bytes[offset] << 16)
                |
                (sample_bytes[offset + 1] << 8)
                |
                sample_bytes[offset + 2]
            )

        elif nal_length_size == 4:

            nal_length = struct.unpack_from(
                ">I",
                sample_bytes,
                offset
            )[0]

        else:

            raise RuntimeError(
                f"Unsupported NAL length size: "
                f"{nal_length_size}"
            )

        offset += nal_length_size

        if nal_length <= 0:
            break

        nal_end = offset + nal_length

        if nal_end > len(sample_bytes):
            break

        nal_data = sample_bytes[
            offset:nal_end
        ]

        output.extend(
            b"\x00\x00\x00\x01"
        )

        output.extend(
            nal_data
        )

        offset = nal_end

    return bytes(output)


def build_annex_b_stream(
    source_bytes,
    samples,
    avcc_info
):
    """
    Build an Annex-B elementary H.264 stream from samples.

    SPS/PPS are prepended from avcC.

    No generated video frames are created.
    """

    output = bytearray()

    # SPS
    for sps in avcc_info["sps"]:

        output.extend(
            b"\x00\x00\x00\x01"
        )

        output.extend(sps)

    # PPS
    for pps in avcc_info["pps"]:

        output.extend(
            b"\x00\x00\x00\x01"
        )

        output.extend(pps)

    for sample in samples:

        start = sample["byte_start"]
        end = sample["byte_end"]

        sample_bytes = source_bytes[
            start:end
        ]

        annex_b = sample_to_annex_b(
            sample_bytes,
            avcc_info["nal_length_size"]
        )

        if annex_b:

            output.extend(
                annex_b
            )

    return bytes(output)


# ----------------------------------------------------------------
# SCANNER REPORT
# ----------------------------------------------------------------

def load_scanner_report(scanner_path):
    """
    Load the dynamic MP4 sample recovery scanner report.
    """

    with open(
        scanner_path,
        "r",
        encoding="utf-8"
    ) as f:

        report = json.load(f)

    samples = report.get(
        "samples",
        report.get(
            "sample_records",
            []
        )
    )

    regions = report.get(
        "recovery_regions",
        []
    )

    gops = report.get(
        "gop_analysis",
        report.get(
            "gops",
            []
        )
    )

    return report, samples, regions, gops


# ----------------------------------------------------------------
# REGION HELPERS
# ----------------------------------------------------------------

def get_region_number(region, fallback):
    return region.get(
        "region_number",
        fallback
    )


def get_region_status(region):
    return str(
        region.get(
            "status",
            ""
        )
    ).upper()


def get_region_sample_start(region):
    """
    Accept multiple possible scanner key names.
    """

    for key in [
        "sample_start",
        "start_sample",
        "first_sample"
    ]:

        value = region.get(key)

        if value is not None:
            return int(value)

    return None


def get_region_sample_end(region):
    """
    Accept multiple possible scanner key names.
    """

    for key in [
        "sample_end",
        "end_sample",
        "last_sample"
    ]:

        value = region.get(key)

        if value is not None:
            return int(value)

    return None


def get_region_time_start(region):
    """
    Return original timeline start.
    """

    if region.get(
        "time_start_seconds"
    ) is not None:

        return float(
            region[
                "time_start_seconds"
            ]
        )

    value = region.get(
        "time_start",
        0.0
    )

    if isinstance(value, (int, float)):
        return float(value)

    return 0.0


def get_region_time_end(region):
    """
    Return original timeline end.
    """

    if region.get(
        "time_end_seconds"
    ) is not None:

        return float(
            region[
                "time_end_seconds"
            ]
        )

    value = region.get(
        "time_end"
    )

    if isinstance(value, (int, float)):
        return float(value)

    return 0.0


# ----------------------------------------------------------------
# REGION VALIDATION
# ----------------------------------------------------------------

def validate_video_file(video_path):
    """
    Validate a reconstructed MP4 using ffprobe and ffmpeg.
    """

    probe_command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,nb_frames,duration",
        "-of",
        "json",
        str(video_path)
    ]

    probe_ok, probe_stdout, probe_stderr = run_command(
        probe_command
    )

    if not probe_ok:

        return {
            "valid": False,
            "ffprobe_ok": False,
            "ffmpeg_decode_ok": False,
            "reason": "FFPROBE_FAILED",
            "ffprobe_error": probe_stderr
        }

    try:

        probe_json = json.loads(
            probe_stdout
        )

    except Exception:

        return {
            "valid": False,
            "ffprobe_ok": True,
            "ffmpeg_decode_ok": False,
            "reason": "INVALID_FFPROBE_JSON"
        }

    streams = probe_json.get(
        "streams",
        []
    )

    if not streams:

        return {
            "valid": False,
            "ffprobe_ok": True,
            "ffmpeg_decode_ok": False,
            "reason": "NO_VIDEO_STREAM"
        }

    decode_command = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(video_path),
        "-map",
        "0:v:0",
        "-f",
        "null",
        "-"
    ]

    decode_ok, _, decode_stderr = run_command(
        decode_command
    )

    return {
        "valid": (
            probe_ok
            and decode_ok
        ),
        "ffprobe_ok": probe_ok,
        "ffmpeg_decode_ok": decode_ok,
        "ffprobe": probe_json,
        "ffmpeg_decode_error":
            decode_stderr if not decode_ok else ""
    }


# ----------------------------------------------------------------
# CREATE REGION VIDEO
# ----------------------------------------------------------------

def create_region_video(
    annex_b_data,
    output_path,
    fps
):
    """
    Encode one recovered H.264 region into an MP4.

    The source data is the actual recovered sample data.
    FFmpeg only repackages/decodes/re-encodes it.
    """

    temp_dir = tempfile.mkdtemp(
        prefix="tracex_region_"
    )

    raw_path = Path(
        temp_dir
    ) / "region.h264"

    try:

        with open(
            raw_path,
            "wb"
        ) as f:

            f.write(
                annex_b_data
            )

        command = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "h264",
            "-r",
            str(fps),
            "-i",
            str(raw_path),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            str(output_path)
        ]

        ok, stdout, stderr = run_command(
            command
        )

        if not ok:

            return {
                "success": False,
                "reason":
                    "FFMPEG_REGION_ENCODING_FAILED",
                "error": stderr
            }

        return {
            "success": True,
            "reason": "REGION_CREATED"
        }

    finally:

        try:
            raw_path.unlink(
                missing_ok=True
            )

        except Exception:
            pass

        try:
            Path(
                temp_dir
            ).rmdir()

        except Exception:
            pass


# ----------------------------------------------------------------
# MAIN RECONSTRUCTION
# ----------------------------------------------------------------

def reconstruct_recovered_regions(
    source_path,
    scanner_report_path,
    output_dir
):
    """
    Main TraceX region reconstruction engine.
    """

    source_path = Path(
        source_path
    )

    scanner_report_path = Path(
        scanner_report_path
    )

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    print("=" * 70)
    print(
        "        TRACEX REGION-BASED FORENSIC RECONSTRUCTION"
    )
    print("=" * 70)

    print()
    print("Source:")
    print(source_path)

    print()
    print("Scanner report:")
    print(scanner_report_path)

    if not source_path.exists():
        raise FileNotFoundError(
            f"Source file not found:\n{source_path}"
        )

    if not scanner_report_path.exists():
        raise FileNotFoundError(
            f"Scanner report not found:\n"
            f"{scanner_report_path}"
        )

    # ------------------------------------------------------------
    # LOAD SOURCE
    # ------------------------------------------------------------

    with open(
        source_path,
        "rb"
    ) as f:

        source_bytes = f.read()

    print()
    print(
        f"Source size: {len(source_bytes)} bytes"
    )

    # ------------------------------------------------------------
    # LOAD SCANNER
    # ------------------------------------------------------------

    scanner_report, scanner_samples, regions, gops = (
        load_scanner_report(
            scanner_report_path
        )
    )

    print()
    print(
        f"Total scanner samples: "
        f"{len(scanner_samples)}"
    )

    print(
        f"Total timeline regions: "
        f"{len(regions)}"
    )

    recoverable_regions = [
        region
        for region in regions
        if get_region_status(region)
        in {
            "RECOVERED",
            "RECOVERABLE"
        }
    ]

    print(
        f"Recoverable regions: "
        f"{len(recoverable_regions)}"
    )

    # ------------------------------------------------------------
    # BUILD ACTUAL SAMPLE MAP
    # ------------------------------------------------------------

    print()
    print(
        "BUILDING MP4 SAMPLE MAP..."
    )

    structure, sample_map, keyframes = (
        build_sample_map(
            source_bytes
        )
    )

    print(
        f"Mapped video samples: "
        f"{len(sample_map)}"
    )

    print(
        f"Keyframes: "
        f"{len(keyframes)}"
    )

    # ------------------------------------------------------------
    # AVC CONFIG
    # ------------------------------------------------------------

    print()
    print(
        "SEARCHING FOR AVC CONFIGURATION..."
    )

    avcc = extract_avcc(
        source_bytes
    )

    avcc_info = parse_avcc(
        avcc
    )

    print(
        f"NAL length size: "
        f"{avcc_info['nal_length_size']}"
    )

    print(
        f"SPS count: "
        f"{len(avcc_info['sps'])}"
    )

    print(
        f"PPS count: "
        f"{len(avcc_info['pps'])}"
    )

    # ------------------------------------------------------------
    # VIDEO TIMESCALE
    # ------------------------------------------------------------

    timescale = locate_video_timescale(
        source_bytes,
        structure["video_trak"]
    )

    print(
        f"Video timescale: "
        f"{timescale}"
    )

    # Estimate FPS from sample durations.
    duration_values = [
        sample.get(
            "duration_timescale",
            0
        )
        for sample in sample_map
    ]

    valid_durations = [
        value
        for value in duration_values
        if value > 0
    ]

    if valid_durations:

        average_duration = (
            sum(valid_durations)
            /
            len(valid_durations)
        )

        fps = (
            timescale
            /
            average_duration
        )

    else:

        fps = 30.0

    print(
        f"Estimated FPS: "
        f"{fps:.6f}"
    )

    # ------------------------------------------------------------
    # RECONSTRUCTION MANIFEST
    # ------------------------------------------------------------

    manifest = {
        "tool": "TraceX",
        "operation":
            "REGION_BASED_FORENSIC_RECONSTRUCTION",
        "source_file":
            str(source_path),
        "scanner_report":
            str(scanner_report_path),
        "source_size_bytes":
            len(source_bytes),
        "total_samples":
            len(sample_map),
        "total_timeline_regions":
            len(regions),
        "recoverable_regions":
            len(recoverable_regions),
        "video_timescale":
            timescale,
        "estimated_fps":
            fps,
        "synthetic_content_added":
            False,
        "timeline_preserved":
            True,
        "regions": []
    }

    # ------------------------------------------------------------
    # PROCESS EACH REGION
    # ------------------------------------------------------------

    successful = 0
    failed = 0
    missing_count = 0

    for region_index, region in enumerate(
        regions,
        start=1
    ):

        region_number = get_region_number(
            region,
            region_index
        )

        status = get_region_status(
            region
        )

        sample_start = (
            get_region_sample_start(
                region
            )
        )

        sample_end = (
            get_region_sample_end(
                region
            )
        )

        time_start = (
            get_region_time_start(
                region
            )
        )

        time_end = (
            get_region_time_end(
                region
            )
        )

        print()
        print("-" * 70)
        print(
            f"REGION-{int(region_number):03d}"
        )

        print(
            f"Samples: "
            f"{sample_start} → {sample_end}"
        )

        print(
            f"Original position: "
            f"{format_time(time_start)} → "
            f"{format_time(time_end)}"
        )

        print(
            f"Status: {status}"
        )

        manifest_region = {
            "region_number":
                int(region_number),
            "sample_start":
                sample_start,
            "sample_end":
                sample_end,
            "original_time_start_seconds":
                time_start,
            "original_time_end_seconds":
                time_end,
            "original_time_start":
                format_time(time_start),
            "original_time_end":
                format_time(time_end),
            "scanner_status":
                status,
            "synthetic_content_added":
                False
        }

        # --------------------------------------------------------
        # MISSING REGION
        # --------------------------------------------------------

        if status not in {
            "RECOVERED",
            "RECOVERABLE"
        }:

            print(
                "Reconstruction: NOT PERFORMED"
            )

            print(
                "Reason: REGION_IS_MISSING_OR_UNRECOVERABLE"
            )

            manifest_region[
                "reconstruction_status"
            ] = "NOT_RECONSTRUCTED"

            manifest_region[
                "reason"
            ] = (
                "REGION_IS_MISSING_OR_UNRECOVERABLE"
            )

            manifest[
                "regions"
            ].append(
                manifest_region
            )

            missing_count += 1

            continue

        # --------------------------------------------------------
        # CHECK SAMPLE RANGE
        # --------------------------------------------------------

        if (
            sample_start is None
            or sample_end is None
        ):

            print(
                "Reconstruction: FAILED"
            )

            print(
                "Reason: "
                "REGION_SAMPLE_RANGE_MISSING"
            )

            manifest_region[
                "reconstruction_status"
            ] = "FAILED"

            manifest_region[
                "reason"
            ] = "REGION_SAMPLE_RANGE_MISSING"

            manifest[
                "regions"
            ].append(
                manifest_region
            )

            failed += 1

            continue

        # --------------------------------------------------------
        # GET SAMPLE OBJECTS
        # --------------------------------------------------------

        selected_samples = [
            sample
            for sample in sample_map
            if (
                sample["sample_number"]
                >= sample_start
                and
                sample["sample_number"]
                <= sample_end
            )
        ]

        print(
            f"Samples found in source: "
            f"{len(selected_samples)}"
        )

        if not selected_samples:

            print(
                "Reconstruction: FAILED"
            )

            print(
                "Reason: NO_SOURCE_SAMPLES_FOUND"
            )

            manifest_region[
                "reconstruction_status"
            ] = "FAILED"

            manifest_region[
                "reason"
            ] = "NO_SOURCE_SAMPLES_FOUND"

            manifest[
                "regions"
            ].append(
                manifest_region
            )

            failed += 1

            continue

        # --------------------------------------------------------
        # CHECK PHYSICAL AVAILABILITY
        # --------------------------------------------------------

        unusable_samples = []

        for sample in selected_samples:

            if not sample_is_usable(
                source_bytes,
                sample
            ):

                unusable_samples.append(
                    sample[
                        "sample_number"
                    ]
                )

        if unusable_samples:

            print(
                "Reconstruction: FAILED"
            )

            print(
                "Reason: "
                "REGION_CONTAINS_UNUSABLE_SAMPLE_DATA"
            )

            print(
                f"Unusable samples: "
                f"{unusable_samples}"
            )

            manifest_region[
                "reconstruction_status"
            ] = "FAILED"

            manifest_region[
                "reason"
            ] = (
                "REGION_CONTAINS_UNUSABLE_SAMPLE_DATA"
            )

            manifest_region[
                "unusable_samples"
            ] = unusable_samples

            manifest[
                "regions"
            ].append(
                manifest_region
            )

            failed += 1

            continue

        # --------------------------------------------------------
        # BUILD H264
        # --------------------------------------------------------

        print(
            "Extracting actual sample bytes..."
        )

        annex_b = build_annex_b_stream(
            source_bytes,
            selected_samples,
            avcc_info
        )

        if not annex_b:

            print(
                "Reconstruction: FAILED"
            )

            print(
                "Reason: "
                "NO_VALID_H264_NAL_UNITS"
            )

            manifest_region[
                "reconstruction_status"
            ] = "FAILED"

            manifest_region[
                "reason"
            ] = "NO_VALID_H264_NAL_UNITS"

            manifest[
                "regions"
            ].append(
                manifest_region
            )

            failed += 1

            continue

        # --------------------------------------------------------
        # OUTPUT PATH
        # --------------------------------------------------------

        region_filename = (
            f"REGION-{int(region_number):03d}"
            f"_reconstructed.mp4"
        )

        region_output = (
            output_dir
            /
            region_filename
        )

        print(
            "Encoding recovered region..."
        )

        creation_result = create_region_video(
            annex_b,
            region_output,
            fps
        )

        if not creation_result[
            "success"
        ]:

            print(
                "Reconstruction: FAILED"
            )

            print(
                f"Reason: "
                f"{creation_result['reason']}"
            )

            if creation_result.get(
                "error"
            ):

                print(
                    creation_result[
                        "error"
                    ]
                )

            manifest_region[
                "reconstruction_status"
            ] = "FAILED"

            manifest_region[
                "reason"
            ] = creation_result[
                "reason"
            ]

            manifest[
                "regions"
            ].append(
                manifest_region
            )

            failed += 1

            continue

        # --------------------------------------------------------
        # VALIDATE
        # --------------------------------------------------------

        print(
            "Validating reconstructed region..."
        )

        validation = validate_video_file(
            region_output
        )

        if not validation[
            "valid"
        ]:

            print(
                "Reconstruction: FAILED VALIDATION"
            )

            print(
                f"Reason: "
                f"{validation.get('reason', 'UNKNOWN')}"
            )

            if validation.get(
                "ffmpeg_decode_error"
            ):

                print(
                    validation[
                        "ffmpeg_decode_error"
                    ]
                )

            manifest_region[
                "reconstruction_status"
            ] = "FAILED_VALIDATION"

            manifest_region[
                "reason"
            ] = "RECONSTRUCTED_VIDEO_VALIDATION_FAILED"

            manifest_region[
                "validation"
            ] = validation

            manifest[
                "regions"
            ].append(
                manifest_region
            )

            failed += 1

            try:
                region_output.unlink(
                    missing_ok=True
                )
            except Exception:
                pass

            continue

        # --------------------------------------------------------
        # SUCCESS
        # --------------------------------------------------------

        file_size = region_output.stat().st_size

        print(
            "Reconstruction: SUCCESS"
        )

        print(
            f"Output: "
            f"{region_output}"
        )

        print(
            f"Output size: "
            f"{file_size} bytes"
        )

        manifest_region[
            "reconstruction_status"
        ] = "SUCCESS"

        manifest_region[
            "output_file"
        ] = str(
            region_output
        )

        manifest_region[
            "output_file_size_bytes"
        ] = file_size

        manifest_region[
            "source_samples_used"
        ] = len(
            selected_samples
        )

        manifest_region[
            "source_sample_numbers"
        ] = [
            sample[
                "sample_number"
            ]
            for sample in selected_samples
        ]

        manifest_region[
            "source_byte_start"
        ] = selected_samples[0][
            "byte_start"
        ]

        manifest_region[
            "source_byte_end"
        ] = selected_samples[-1][
            "byte_end"
        ]

        manifest_region[
            "validation"
        ] = validation

        manifest[
            "regions"
        ].append(
            manifest_region
        )

        successful += 1

    # ------------------------------------------------------------
    # FINAL SUMMARY
    # ------------------------------------------------------------

    manifest[
        "successfully_reconstructed"
    ] = successful

    manifest[
        "validation_failures"
    ] = failed

    manifest[
        "missing_regions_preserved"
    ] = missing_count

    manifest[
        "overall_status"
    ] = (
        "FULLY_RECONSTRUCTED_REGIONS"
        if (
            successful > 0
            and missing_count == 0
            and failed == 0
        )
        else
        "PARTIALLY_RECONSTRUCTED"
        if successful > 0
        else
        "NO_REGIONS_RECONSTRUCTED"
    )

    manifest[
        "forensic_note"
    ] = (
        "Reconstructed region files contain only "
        "physically recoverable source sample data. "
        "Missing timeline regions are not filled with "
        "synthetic footage. Original timeline positions "
        "are preserved in this manifest."
    )

    manifest[
        "timeline_compression_warning"
    ] = (
        "Individual reconstructed MP4 files are "
        "standalone region files. They must not be "
        "interpreted as a continuous recording across "
        "missing timeline regions."
    )

    manifest_path = (
        output_dir
        /
        "region_reconstruction_manifest.json"
    )

    with open(
        manifest_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            manifest,
            f,
            indent=4
        )

    print()
    print("=" * 70)
    print(
        "RECONSTRUCTION SUMMARY"
    )
    print("=" * 70)

    print(
        f"Successfully reconstructed: "
        f"{successful}"
    )

    print(
        f"Validation failures: "
        f"{failed}"
    )

    print(
        f"Missing regions preserved: "
        f"{missing_count}"
    )

    print(
        "Synthetic content added: False"
    )

    print(
        "Original timeline preserved: True"
    )

    print()
    print(
        "MANIFEST"
    )
    print("─" * 70)
    print(
        manifest_path
    )

    print()
    print(
        "OUTPUT DIRECTORY"
    )
    print("─" * 70)
    print(
        output_dir
    )

    print()
    print(
        "TraceX region reconstruction complete."
    )

    return manifest


# ----------------------------------------------------------------
# DIRECT EXECUTION
# ----------------------------------------------------------------

if __name__ == "__main__":

    SOURCE = (
        r".\recovery\test_data"
        r"\multi_region_damaged.mp4"
    )

    SCANNER_REPORT = (
        r".\output\recovery"
        r"\multi_region_damaged"
        r"\mp4_sample_recovery_scan.json"
    )

    OUTPUT_DIR = (
        r".\output\recovery"
        r"\multi_region_damaged"
        r"\reconstructed_regions"
    )

    reconstruct_recovered_regions(
        SOURCE,
        SCANNER_REPORT,
        OUTPUT_DIR
    )