"""
Records a short test video from your laptop's webcam, purely so we
have something real to test motion/face detection against.
"""

import cv2

def record_video(output_path="test_video.mp4", seconds=10):
    cap = cv2.VideoCapture(0)  # 0 = default webcam

    if not cap.isOpened():
        print("Could not open webcam.")
        return

    fps = 20
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    print(f"Recording {seconds} seconds... move around / show your face for a good test.")
    frame_count = 0
    max_frames = fps * seconds

    while frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)
        cv2.imshow("Recording... press Q to stop early", frame)
        frame_count += 1
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print(f"Saved {output_path}")

if __name__ == "__main__":
    record_video()