import os


source_file = "C:/Users/imneh/Desktop/DVR/data/uploads/WIN_20260906_11_57_55_Pro.mp4"
damaged_file = "damaged_test.mp4"


try:

    with open(source_file, "rb") as source:

        data = source.read()

    damaged_size = len(data) // 2

    with open(damaged_file, "wb") as damaged:

        damaged.write(data[:damaged_size])

    print("\nDAMAGED TEST FILE CREATED")
    print("────────────────────────────")
    print("Original :", source_file)
    print("Damaged  :", damaged_file)
    print("Original size :", len(data), "bytes")
    print("Damaged size  :", damaged_size, "bytes")

except Exception as error:

    print("Error:", error)