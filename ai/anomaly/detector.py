
import cv2
import uuid
import sys
import os
import numpy as np

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.event_schema import DetectionEvent

def detect_anomalies(video_path: str, freeze_threshold: float = 2.0, min_frozen_frames: int = 15):
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"ERROR: could not open video at {video_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    reported_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    events = []
    prev_gray = None
    frozen_run = 0
    frame_num = 0
    prev_timestamp_ms = None
    expected_interval_ms = 1000.0 / fps

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        current_timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)

        # --- Check 1: timestamp jump ---
        if prev_timestamp_ms is not None:
            actual_gap = current_timestamp_ms - prev_timestamp_ms
            if actual_gap > expected_interval_ms * 3:  # more than 3 frames' worth missing
                events.append(DetectionEvent(
                    event_id=str(uuid.uuid4()),
                    video_source=video_path,
                    frame_number=frame_num,
                    timestamp_sec=frame_num / fps,
                    detection_type="anomaly",
                    label="timestamp_jump",
                    confidence=None,
                    bbox=None,
                    model="anomaly_detector",
                    model_version="1.0"
                ))

        # --- Check 2: frozen/looped segment ---
        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray)
            mean_diff = np.mean(diff)
            if mean_diff < freeze_threshold:
                frozen_run += 1
            else:
                if frozen_run >= min_frozen_frames:
                    events.append(DetectionEvent(
                        event_id=str(uuid.uuid4()),
                        video_source=video_path,
                        frame_number=frame_num - frozen_run,
                        timestamp_sec=(frame_num - frozen_run) / fps,
                        detection_type="anomaly",
                        label="frozen_segment",
                        confidence=None,
                        bbox=None,
                        model="anomaly_detector",
                        model_version="1.0"
                    ))
                frozen_run = 0

        prev_gray = gray
        prev_timestamp_ms = current_timestamp_ms
        frame_num += 1

    # catch a frozen run that continues to the very end of the video
    if frozen_run >= min_frozen_frames:
        events.append(DetectionEvent(
            event_id=str(uuid.uuid4()),
            video_source=video_path,
            frame_number=frame_num - frozen_run,
            timestamp_sec=(frame_num - frozen_run) / fps,
            detection_type="anomaly",
            label="frozen_segment",
            confidence=None,
            bbox=None,
            model="anomaly_detector",
            model_version="1.0"
        ))

    actual_frame_count = frame_num
    cap.release()

    # --- Check 3: frame count mismatch ---
    if abs(reported_frame_count - actual_frame_count) > 5:
        events.append(DetectionEvent(
            event_id=str(uuid.uuid4()),
            video_source=video_path,
            frame_number=0,
            timestamp_sec=0.0,
            detection_type="anomaly",
            label="frame_count_mismatch",
            confidence=None,
            bbox=None,
            model="anomaly_detector",
            model_version="1.0"
        ))
        print(f"  WARNING: metadata says {reported_frame_count} frames, but {actual_frame_count} were actually readable")

    return events

if __name__ == "__main__":
    video_path = os.path.join(os.path.dirname(__file__), '..', 'sample_data', 'test1.mp4')
    results = detect_anomalies(video_path)
    print(f"Detected {len(results)} anomaly events")
    for e in results:
        print(f"  - {e.label} at {e.timestamp_sec:.1f}s")