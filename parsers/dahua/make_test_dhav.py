"""
Builds syntactically correct DHAV frames for testing dhav_parser.py.
The payload content is meaningless test bytes, not real video -- this
only proves our byte offsets and dual-signature footer validation
work correctly, including skipping over junk bytes between frames
(simulating gaps you'd find on a real damaged disk).
"""

import struct

DHAV_HEADER_MAGIC = b"DHAV"
DHAV_FOOTER_MAGIC = b"dhav"


def build_fake_dhav_frame(frame_type=0xFD, channel=1, frame_number=1, payload=b"FAKEVIDEOPAYLOAD"):
    header = bytearray(24)
    header[0:4] = DHAV_HEADER_MAGIC
    header[4] = frame_type
    header[6] = channel
    struct.pack_into("<I", header, 8, frame_number)
    total_length = 24 + len(payload) + len(DHAV_FOOTER_MAGIC)
    struct.pack_into("<I", header, 12, total_length)
    return bytes(header) + payload + DHAV_FOOTER_MAGIC


if __name__ == "__main__":
    frame1 = build_fake_dhav_frame(frame_type=0xFD, channel=1, frame_number=1, payload=b"VIDEO_FRAME_ONE_DATA")
    frame2 = build_fake_dhav_frame(frame_type=0xF0, channel=1, frame_number=2, payload=b"AUDIO_FRAME_TWO")

    with open("fake_dhav_test.bin", "wb") as f:
        f.write(frame1)
        f.write(b"\x00" * 10)  # junk bytes between frames, simulating a real gap
        f.write(frame2)

    print("Created fake_dhav_test.bin with 2 synthetic DHAV frames (video + audio).")