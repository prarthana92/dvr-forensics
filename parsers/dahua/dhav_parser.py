"""
Dahua DHAV frame parser.

Based on documented DHAV frame structure: each frame begins with the
ASCII header 'DHAV' (uppercase) and ends with the footer 'dhav'
(lowercase). This dual-signature design lets us validate individual
frames even when surrounding file system metadata is damaged or
missing entirely -- which is exactly the situation forensic recovery
usually deals with.

Documented header layout (24-byte fixed header):
    bytes 0-3   : magic "DHAV"
    byte  4     : frame type (0xFD = video, 0xF0 = audio)
    byte  6     : channel identifier
    bytes 8-11  : frame number (uint32, little-endian)
    bytes 12-15 : frame length (uint32, little-endian) -- total frame
                  size including header, payload, and footer
    bytes 16-23 : date/time fields (raw, exact bit encoding not yet
                  confirmed -- needs real Dahua footage to decode)
"""

import struct

DHAV_HEADER_MAGIC = b"DHAV"
DHAV_FOOTER_MAGIC = b"dhav"
FIXED_HEADER_SIZE = 24

FRAME_TYPE_VIDEO = 0xFD
FRAME_TYPE_AUDIO = 0xF0


class DHAVFrame:
    def __init__(self, frame_type, channel, frame_number, frame_length, raw_timestamp, offset):
        self.frame_type = frame_type
        self.channel = channel
        self.frame_number = frame_number
        self.frame_length = frame_length
        self.raw_timestamp = raw_timestamp
        self.offset = offset

    def type_name(self):
        if self.frame_type == FRAME_TYPE_VIDEO:
            return "video"
        elif self.frame_type == FRAME_TYPE_AUDIO:
            return "audio"
        return f"unknown(0x{self.frame_type:02X})"

    def __repr__(self):
        return (f"DHAVFrame(offset={self.offset}, type={self.type_name()}, "
                f"channel={self.channel}, frame_number={self.frame_number}, "
                f"length={self.frame_length})")


def parse_dhav_header(data, offset):
    if data[offset:offset+4] != DHAV_HEADER_MAGIC:
        return None

    frame_type = data[offset+4]
    channel = data[offset+6]
    frame_number = struct.unpack_from("<I", data, offset+8)[0]
    frame_length = struct.unpack_from("<I", data, offset+12)[0]
    raw_timestamp = data[offset+16:offset+24]

    return DHAVFrame(frame_type, channel, frame_number, frame_length, raw_timestamp, offset)


def validate_footer(data, frame):
    """
    Dual-signature validation: confirms the frame ends with the lowercase
    'dhav' footer exactly where frame_length says it should.
    """
    footer_pos = frame.offset + frame.frame_length - len(DHAV_FOOTER_MAGIC)
    if footer_pos < 0 or footer_pos + len(DHAV_FOOTER_MAGIC) > len(data):
        return False
    return data[footer_pos:footer_pos+len(DHAV_FOOTER_MAGIC)] == DHAV_FOOTER_MAGIC


def scan_for_dhav_frames(data):
    """
    Scans a byte buffer for valid DHAV frames, skipping over junk/gap
    bytes and validating each candidate with the header+footer check
    before accepting it.
    """
    frames = []
    i = 0
    while i < len(data) - FIXED_HEADER_SIZE:
        if data[i:i+4] == DHAV_HEADER_MAGIC:
            frame = parse_dhav_header(data, i)
            if frame and validate_footer(data, frame):
                frames.append(frame)
                i += frame.frame_length
                continue
        i += 1
    return frames


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python dhav_parser.py <path_to_file>")
        sys.exit(1)

    with open(sys.argv[1], "rb") as f:
        data = f.read()

    frames = scan_for_dhav_frames(data)
    print(f"Found {len(frames)} validated DHAV frame(s):")
    for frame in frames:
        print(f"  {frame}")