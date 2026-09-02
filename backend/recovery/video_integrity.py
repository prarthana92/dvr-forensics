import os
import cv2
import json
import subprocess


FFPROBE_PATH = (
    r"C:\ffmpeg\ffmpeg-9.0.1-essentials_build"
    r"\bin\ffprobe.exe"
)


def get_video_info(file_path):

    if not os.path.exists(file_path):
        return None

    video = cv2.VideoCapture(file_path)

    if not video.isOpened():
        video.release()
        return None

    frame_count = int(
        video.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    fps = video.get(
        cv2.CAP_PROP_FPS
    )

    duration = 0

    if fps > 0:
        duration = frame_count / fps

    video.release()

    return {
        "frame_count": frame_count,
        "fps": fps,
        "duration_seconds": duration,
        "file_size_bytes": os.path.getsize(file_path)
    }


def run_ffprobe(file_path):

    if not os.path.exists(file_path):

        return {
            "success": False,
            "error": "FILE_NOT_FOUND"
        }

    if not os.path.exists(FFPROBE_PATH):

        return {
            "success": False,
            "error": "FFPROBE_NOT_FOUND"
        }

    command = [
        FFPROBE_PATH,
        "-v",
        "error",
        "-show_entries",
        "format=format_name,duration,size",
        "-show_entries",
        "stream=index,codec_name,codec_type",
        "-of",
        "json",
        file_path
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True
        )

    except Exception as error:

        return {
            "success": False,
            "error": str(error)
        }

    if result.returncode != 0:

        error_message = result.stderr.strip()

        if not error_message:
            error_message = "FFPROBE_VALIDATION_FAILED"

        return {
            "success": False,
            "error": error_message
        }

    try:

        probe_data = json.loads(
            result.stdout
        )

    except json.JSONDecodeError:

        return {
            "success": False,
            "error": "INVALID_FFPROBE_OUTPUT"
        }

    return {
        "success": True,
        "data": probe_data
    }


def decode_video_frames(file_path):

    if not os.path.exists(file_path):

        return 0

    video = cv2.VideoCapture(file_path)

    if not video.isOpened():

        video.release()

        return 0

    decoded_frames = 0

    while True:

        success, frame = video.read()

        if not success:
            break

        decoded_frames += 1

    video.release()

    return decoded_frames


def check_video_integrity(
    original_path,
    test_path
):

    original_info = get_video_info(
        original_path
    )

    test_info = get_video_info(
        test_path
    )

    if original_info is None:

        return {
            "status": "ORIGINAL_UNREADABLE",
            "original": None,
            "test": test_info,
            "decoded_frames": 0,
            "ffprobe": None
        }

    if test_info is None:

        ffprobe_result = run_ffprobe(
            test_path
        )

        return {
            "status": "DAMAGED_OR_UNREADABLE",
            "original": original_info,
            "test": None,
            "decoded_frames": 0,
            "ffprobe": ffprobe_result
        }

    decoded_frames = decode_video_frames(
        test_path
    )

    ffprobe_result = run_ffprobe(
        test_path
    )

    if not ffprobe_result["success"]:

        return {
            "status": "DAMAGED_OR_UNREADABLE",
            "original": original_info,
            "test": test_info,
            "decoded_frames": decoded_frames,
            "ffprobe": ffprobe_result
        }

    if decoded_frames < original_info["frame_count"]:

        return {
            "status": "INCOMPLETE",
            "original": original_info,
            "test": test_info,
            "decoded_frames": decoded_frames,
            "ffprobe": ffprobe_result
        }

    return {
        "status": "READABLE",
        "original": original_info,
        "test": test_info,
        "decoded_frames": decoded_frames,
        "ffprobe": ffprobe_result
    }


if __name__ == "__main__":

    backend_folder = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    original_path = os.path.join(
        backend_folder,
        "device",
        "hikvision_test.mp4"
    )

    test_path = os.path.join(
        backend_folder,
        "recovery",
        "test_data",
        "damaged_test.mp4"
    )

    try:

        result = check_video_integrity(
            original_path,
            test_path
        )

        print("\nVIDEO INTEGRITY CHECK")
        print("────────────────────────────")

        print("\nORIGINAL VIDEO")

        if result["original"] is None:

            print(
                "Original video could not be opened."
            )

        else:

            print(
                "Frame count :",
                result["original"]["frame_count"]
            )

            print(
                "FPS         :",
                result["original"]["fps"]
            )

            print(
                "Duration    :",
                result["original"]["duration_seconds"]
            )

            print(
                "Size        :",
                result["original"]["file_size_bytes"]
            )

        print("\nTEST VIDEO")

        if result["test"] is None:

            print(
                "The test video could not be opened."
            )

        else:

            print(
                "Frame count :",
                result["test"]["frame_count"]
            )

            print(
                "FPS         :",
                result["test"]["fps"]
            )

            print(
                "Duration    :",
                result["test"]["duration_seconds"]
            )

            print(
                "Size        :",
                result["test"]["file_size_bytes"]
            )

        print(
            "\nActually decoded frames:",
            result["decoded_frames"]
        )

        print(
            "\nFFprobe validation:",
            result["ffprobe"]["success"]
        )

        if not result["ffprobe"]["success"]:

            print(
                "FFprobe error:",
                result["ffprobe"]["error"]
            )

        print(
            "\nSTATUS:",
            result["status"]
        )

    except Exception as error:

        print(
            "Error:",
            error
        )