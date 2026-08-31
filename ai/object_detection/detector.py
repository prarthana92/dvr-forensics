
import cv2
import uuid
import sys
import os
from ultralytics import YOLO

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.event_schema import DetectionEvent

RELEVANT_CLASSES = {"person", "car", "truck", "motorcycle", "backpack", "handbag", "bicycle"}

def detect_objects(video_path: str, sample_every_n_frames: int = 5, frames_of_interest: set = None):
    model = YOLO("yolov8n.pt")
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"ERROR: could not open video at {video_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 25

    events = []
    frame_num = 0
    frames_processed = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frames_of_interest is not None:
            should_process = frame_num in frames_of_interest
        else:
            should_process = frame_num % sample_every_n_frames == 0

        if should_process:
            frames_processed += 1
            results = model(frame, verbose=False)[0]
            for box in results.boxes:
                label = model.names[int(box.cls[0])]
                if label not in RELEVANT_CLASSES:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                events.append(DetectionEvent(
                    event_id=str(uuid.uuid4()),
                    video_source=video_path,
                    frame_number=frame_num,
                    timestamp_sec=frame_num / fps,
                    detection_type="object",
                    label=label,
                    confidence=float(box.conf[0]),
                    bbox=[x1, y1, x2 - x1, y2 - y1],
                    model="yolov8n",
                    model_version="8.x"
                ))

        frame_num += 1

    cap.release()
    print(f"  (object detection processed {frames_processed} of {frame_num} frames)")
    return events

if __name__ == "__main__":
    video_path = os.path.join(os.path.dirname(__file__), '..', 'sample_data', 'test1.mp4')
    results = detect_objects(video_path)
    print(f"Detected {len(results)} object events")