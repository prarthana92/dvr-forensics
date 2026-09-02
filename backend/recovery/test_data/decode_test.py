import cv2
import os


video_path = os.path.join(
    os.path.dirname(__file__),
    "damaged_test.mp4"
)


video = cv2.VideoCapture(video_path)

print("\nDECODE TEST")
print("────────────────────────────")

print("File:", video_path)
print("Opened:", video.isOpened())

reported_frames = int(
    video.get(cv2.CAP_PROP_FRAME_COUNT)
)

fps = video.get(
    cv2.CAP_PROP_FPS
)

print("Reported frames:", reported_frames)
print("FPS:", fps)

decoded_frames = 0

while True:

    success, frame = video.read()

    if not success:
        break

    decoded_frames += 1


video.release()

print("Actually decoded frames:", decoded_frames)

print("\nFILE SIZE")
print("────────────────────────────")
print(
    os.path.getsize(video_path),
    "bytes"
)

print("\nTEST COMPLETE")