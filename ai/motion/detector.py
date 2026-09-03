
import cv2
import uuid
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.event_schema import DetectionEvent

def detect_motion(video_path: str, min_area: int = 800):
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"ERROR: could not open video at {video_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    backsub = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=25, detectShadows=True)

    events = []
    frame_num = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        mask = backsub.apply(frame)
        mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)[1]
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for c in contours:
            if cv2.contourArea(c) < min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            events.append(DetectionEvent(
                event_id=str(uuid.uuid4()),
                video_source=video_path,
                frame_number=frame_num,
                timestamp_sec=frame_num / fps,
                detection_type="motion",
                bbox=[x, y, w, h],
                model="MOG2",
                model_version=cv2.__version__
            ))

        frame_num += 1

    cap.release()
    return events

if __name__ == "__main__":
    video_path = os.path.join(os.path.dirname(__file__), '..', 'sample_data', 'test1.mp4')
    results = detect_motion(video_path)
    print(f"Detected {len(results)} motion events")
    if results:
        print("First event:", results[0])