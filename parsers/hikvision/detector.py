"""
Hikvision DVR/NVR device identification module.

Based on: Han, J. & Jeong, D. (2015). "Analysis of the HIKVISION DVR
file system." ICDF2C 2015. Confirmed structure: a Master Sector at
disk offset 0x200 (512 bytes in), beginning with the ASCII signature
'HIKVISION@HANGZHOU' (18 bytes).

This module ONLY identifies whether a disk image is Hikvision-formatted.
It does not yet parse the rest of the Master Sector fields (capacity,
video data offset, HIKBTREE offset, etc.) -- those exact byte positions
still need to be confirmed against a real Hikvision disk image, ideally
by hex-inspecting a known-good image alongside the DVR's own reported
configuration (known disk size, known number of channels, etc.).
"""

HIKVISION_SIGNATURE = b"HIKVISION@HANGZHOU"
MASTER_SECTOR_OFFSET = 0x200  # 512 in decimal


def is_hikvision_image(disk_image_path):
    """
    Returns True if the given disk image has the Hikvision Master Sector
    signature at the documented offset.
    """
    with open(disk_image_path, "rb") as f:
        f.seek(MASTER_SECTOR_OFFSET)
        chunk = f.read(len(HIKVISION_SIGNATURE))
    return chunk == HIKVISION_SIGNATURE


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python detector.py <path_to_disk_image>")
        sys.exit(1)

    path = sys.argv[1]
    if is_hikvision_image(path):
        print(f"MATCH: {path} appears to be a Hikvision DVR/NVR disk image.")
    else:
        print(f"NO MATCH: {path} does not have the Hikvision Master Sector signature at offset 0x200.")