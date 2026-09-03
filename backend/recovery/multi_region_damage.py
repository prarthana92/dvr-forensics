import os
import shutil


# ============================================================
# TRACE-X CONTROLLED MULTI-REGION DAMAGE TEST
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SOURCE_FILE = os.path.join(
    BASE_DIR,
    "recovery",
    "test_data",
    "multi_region_source.mp4"
)

OUTPUT_FILE = os.path.join(
    BASE_DIR,
    "recovery",
    "test_data",
    "multi_region_damaged.mp4"
)


# ------------------------------------------------------------
# DAMAGE CONFIGURATION
# ------------------------------------------------------------
#
# IMPORTANT:
# This test removes complete byte ranges from the media data.
#
# The original MP4 metadata is preserved only as far as possible.
# This is a controlled forensic test fixture, NOT real recovery
# of a naturally damaged DVR file.
#
# We intentionally damage three separate areas.
# ------------------------------------------------------------

DAMAGE_RANGES = [
    (300000, 380000),
    (900000, 980000),
    (1500000, 1580000),
]


def create_damaged_file():
    print("=" * 70)
    print("       TRACE-X MULTI-REGION DAMAGE TEST")
    print("=" * 70)

    print()
    print("Source:")
    print(SOURCE_FILE)

    print()
    print("Output:")
    print(OUTPUT_FILE)

    if not os.path.exists(SOURCE_FILE):
        print()
        print("ERROR: Source file does not exist.")
        return False

    with open(SOURCE_FILE, "rb") as f:
        data = bytearray(f.read())

    original_size = len(data)

    print()
    print("-" * 70)
    print("ORIGINAL FILE")
    print("-" * 70)

    print(f"Size: {original_size} bytes")

    print()
    print("-" * 70)
    print("APPLYING CONTROLLED DAMAGE")
    print("-" * 70)

    for index, (start, end) in enumerate(DAMAGE_RANGES, start=1):

        if start >= original_size:
            print(
                f"Damage region {index}: SKIPPED "
                f"(start outside file)"
            )
            continue

        end = min(end, original_size)

        length = end - start

        print(
            f"Damage region {index}: "
            f"{start} → {end} "
            f"({length} bytes)"
        )

        # Replace the bytes with zeroes.
        #
        # We deliberately DO NOT remove bytes.
        # This keeps all original byte offsets unchanged.
        data[start:end] = b"\x00" * length

    with open(OUTPUT_FILE, "wb") as f:
        f.write(data)

    damaged_size = os.path.getsize(OUTPUT_FILE)

    print()
    print("-" * 70)
    print("DAMAGED FILE CREATED")
    print("-" * 70)

    print(f"Output size: {damaged_size} bytes")
    print(f"Size preserved: {damaged_size == original_size}")

    print()
    print("Damage regions:")

    for index, (start, end) in enumerate(DAMAGE_RANGES, start=1):
        print(
            f"  REGION-{index:03d}: "
            f"{start} → {end}"
        )

    print()
    print("-" * 70)
    print("IMPORTANT FORENSIC NOTE")
    print("-" * 70)

    print(
        "This fixture uses zeroed byte ranges instead of deleting bytes."
    )

    print(
        "The purpose is controlled testing of corruption handling."
    )

    print(
        "It does NOT represent naturally damaged DVR footage."
    )

    print(
        "No synthetic video frames were created."
    )

    print()
    print("=" * 70)
    print("       DAMAGE TEST COMPLETE")
    print("=" * 70)

    return True


if __name__ == "__main__":
    create_damaged_file()