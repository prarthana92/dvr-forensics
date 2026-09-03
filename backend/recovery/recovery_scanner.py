import os


def scan_for_video_files(folder_path):

    video_extensions = [
        ".mp4",
        ".avi",
        ".mkv",
        ".mov",
        ".ts",
        ".dav",
        ".264",
        ".h264"
    ]

    found_files = []

    for root, folders, files in os.walk(folder_path):

        for file_name in files:

            file_extension = os.path.splitext(
                file_name
            )[1].lower()

            if file_extension in video_extensions:

                full_path = os.path.join(
                    root,
                    file_name
                )

                found_files.append(full_path)

    return found_files


if __name__ == "__main__":

    evidence_folder = "../device"

    try:

        video_files = scan_for_video_files(
            evidence_folder
        )

        print("\nRECOVERY SCANNER")
        print("────────────────────────────")

        if video_files:

            print("Video files found:")

            for file_path in video_files:
                print("-", file_path)

        else:

            print("No video files found.")

        print("\nTotal video files:", len(video_files))

    except Exception as error:

        print("Error:", error)