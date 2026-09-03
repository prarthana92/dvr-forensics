
import cv2
import uuid
import sys
import os
import mediapipe as mp

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.event_schema import DetectionEvent

def detect_faces(video_path: str, sample_every_n_frames: int = 5, frames_of_interest: set = None):
    mp_face = mp.solutions.face_detection
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"ERROR: could not open video at {video_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 25

    events = []
    frame_num = 0
    frames_processed = 0

    with mp_face.FaceDetection(model_selection=1, min_detection_confidence=0.5) as detector:
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
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = detector.process(rgb)
                h, w, _ = frame.shape

                if results.detections:
                    for det in results.detections:
                        box = det.location_data.relative_bounding_box
                        x, y = int(box.xmin * w), int(box.ymin * h)
                        bw, bh = int(box.width * w), int(box.height * h)
                        events.append(DetectionEvent(
                            event_id=str(uuid.uuid4()),
                            video_source=video_path,
                            frame_number=frame_num,
                            timestamp_sec=frame_num / fps,
                            detection_type="face",
                            label="face",
                            confidence=float(det.score[0]),
                            bbox=[x, y, bw, bh],
                            model="mediapipe_face_detection",
                            model_version="0.10.x"
                        ))

            frame_num += 1

    cap.release()
    print(f"  (face detection processed {frames_processed} of {frame_num} frames)")
    return events

if __name__ == "__main__":
    video_path = os.path.join(os.path.dirname(__file__), '..', 'sample_data', 'test1.mp4')
    results = detect_faces(video_path)
    print(f"Detected {len(results)} face events")