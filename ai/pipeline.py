
import json
import os
from motion.detector import detect_motion
from object_detection.detector import detect_objects
from face_detection.detector import detect_faces
from anomaly.detector import detect_anomalies
from utils.frame_selector import frames_with_motion
from utils.format_converter import convert_to_final_format
from utils.filtering import filter_by_confidence

def run_pipeline(video_path: str, output_path: str = "ai_results.json", confidence_threshold: float = 0.4):
    print("Running motion detection...")
    motion_events = detect_motion(video_path)
    print(f"  -> {len(motion_events)} motion events")

    frames_of_interest = frames_with_motion(motion_events, padding_frames=2)
    print(f"  -> {len(frames_of_interest)} frames flagged for deeper analysis")

    print("Running object detection (motion-gated)...")
    object_events = detect_objects(video_path, frames_of_interest=frames_of_interest)
    print(f"  -> {len(object_events)} object events")

    print("Running face detection (motion-gated)...")
    face_events = detect_faces(video_path, frames_of_interest=frames_of_interest)
    print(f"  -> {len(face_events)} face events")

    print("Running anomaly detection...")
    anomaly_events = detect_anomalies(video_path)
    print(f"  -> {len(anomaly_events)} anomaly events")

    all_events = motion_events + object_events + face_events + anomaly_events
    all_events_dicts = [e.model_dump() for e in all_events]

    print(f"Filtering object/face detections below confidence {confidence_threshold}...")
    filtered_events = filter_by_confidence(all_events_dicts, min_confidence=confidence_threshold)
    dropped = len(all_events_dicts) - len(filtered_events)
    print(f"  -> dropped {dropped} low-confidence detections, {len(filtered_events)} remaining")

    final_output = convert_to_final_format(filtered_events, include_motion_regions=False)

    with open(output_path, "w") as f:
        json.dump(final_output, f, indent=2)

    print(f"\nDone. {len(final_output['events'])} frame-groups written to {output_path}")
    return final_output

if __name__ == "__main__":
    video_path = os.path.join(os.path.dirname(__file__), 'sample_data', 'test1.mp4')
    run_pipeline(video_path, confidence_threshold=0.4)