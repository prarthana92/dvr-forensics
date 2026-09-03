
import json
from collections import defaultdict

def convert_to_final_format(events: list, include_motion_regions: bool = False) -> dict:
    """
    Converts internal flat event list into the agreed backend format:
    - motion events are aggregated per frame into one summary event (region_count,
      optionally regions if include_motion_regions=True)
    - object, face, and anomaly events stay as individual detections
    """
    grouped = defaultdict(list)
    frame_timestamps = {}
    motion_regions_by_frame = defaultdict(list)

    for e in events:
        frame_num = e["frame_number"]
        frame_timestamps[frame_num] = e["timestamp_sec"]

        if e["detection_type"] == "motion":
            if e.get("bbox") is not None:
                motion_regions_by_frame[frame_num].append(e["bbox"])
            continue

        detection = {"type": e["detection_type"]}

        label = e.get("label")
        if not label:
            label = e["detection_type"]
        detection["label"] = label

        if e.get("confidence") is not None:
            detection["confidence"] = round(e["confidence"], 2)

        if e.get("bbox") is not None:
            detection["bbox"] = e["bbox"]

        grouped[frame_num].append(detection)

    for frame_num, regions in motion_regions_by_frame.items():
        motion_event = {
            "type": "motion",
            "label": "movement",
            "region_count": len(regions)
        }
        if include_motion_regions:
            motion_event["regions"] = regions
        grouped[frame_num].insert(0, motion_event)
        frame_timestamps.setdefault(frame_num, None)

    result_events = []
    for frame_num in sorted(grouped.keys()):
        result_events.append({
            "frame": frame_num,
            "timestamp_seconds": round(frame_timestamps[frame_num], 3) if frame_timestamps[frame_num] is not None else None,
            "detections": grouped[frame_num]
        })

    return {"events": result_events}