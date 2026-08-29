"""
Motion detection using OpenCV background subtraction (MOG2 algorithm).

This is a real, working motion detection module -- it compares each
frame against a running model of the "background" and flags frames
where a large enough area changed (i.e. something moved). This is
the standard, well-established technique for motion detection before
reaching for anything heavier like deep learning object detection.
"""

import cv2

def detect_motion(video_path, motion_threshold=5000):
    """
    Scans a video file for motion. Returns a list of (frame_number,
    timestamp_seconds) tuples where motion was detected above the
    given threshold (in changed pixel area).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Could not open video: {video_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 20
    back_sub = cv2.createBackgroundSubtractorMOG2(history=50, varThreshold=40, detectShadows=True)

    motion_events = []
    frame_number = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        fg_mask = back_sub.apply(frame)
        # Count how many pixels changed (ignore shadow pixels, value 127)
        motion_pixels = cv2.countNonZero(cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)[1])

        if motion_pixels > motion_threshold:
            timestamp = frame_number / fps
            motion_events.append((frame_number, round(timestamp, 2)))

        frame_number += 1

    cap.release()
    return motion_events


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python motion_detector.py <path_to_video>")
        sys.exit(1)

    events = detect_motion(sys.argv[1])
    print(f"Detected motion in {len(events)} frame(s):")
    for frame_number, timestamp in events[:20]:  # show first 20 to avoid flooding the terminal
        print(f"  Frame {frame_number} at {timestamp}s")
    if len(events) > 20:
        print(f"  ... and {len(events) - 20} more")