
import json
import os
import sys
from collections import defaultdict
from typing import List, Dict

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.event_schema import DetectionEvent

TIME_WINDOW_SEC = 2.0  # events within this many seconds count as "the same moment"

def load_events(json_path: str) -> List[DetectionEvent]:
    with open(json_path, "r") as f:
        raw = json.load(f)
    events_list = raw["events"] if isinstance(raw, dict) else raw
    return [DetectionEvent(**item) for item in events_list]

def correlate_events(events: List[DetectionEvent], time_window: float = TIME_WINDOW_SEC) -> List[Dict]:
    """
    Finds object/face detections that share the same label and occur on
    DIFFERENT video sources within `time_window` seconds of each other --
    a signal they may be the same real-world event seen by multiple cameras.
    """
    relevant = [e for e in events if e.detection_type in ("object", "face")]

    by_label: Dict[str, List[DetectionEvent]] = defaultdict(list)
    for e in relevant:
        by_label[e.label].append(e)

    clusters = []
    used = set()

    for label, group in by_label.items():
        group_sorted = sorted(group, key=lambda e: e.timestamp_sec)
        for i, e1 in enumerate(group_sorted):
            if e1.event_id in used:
                continue
            cluster = [e1]
            used.add(e1.event_id)
            for e2 in group_sorted[i + 1:]:
                if e2.event_id in used:
                    continue
                if e2.video_source == e1.video_source:
                    continue  # same camera -- not a cross-camera correlation
                if abs(e2.timestamp_sec - e1.timestamp_sec) <= time_window:
                    cluster.append(e2)
                    used.add(e2.event_id)

            if len(cluster) > 1:
                clusters.append({
                    "label": label,
                    "event_ids": [e.event_id for e in cluster],
                    "sources": list(set(e.video_source for e in cluster)),
                    "timestamps": [e.timestamp_sec for e in cluster],
                })

    return clusters

if __name__ == "__main__":
    events_path = os.path.join(os.path.dirname(__file__), '..', 'events_output.json')
    events = load_events(events_path)
    print(f"Loaded {len(events)} events")

    clusters = correlate_events(events)
    print(f"Found {len(clusters)} cross-camera correlated clusters")

    output_path = os.path.join(os.path.dirname(__file__), '..', 'correlated_events.json')
    with open(output_path, "w") as f:
        json.dump(clusters, f, indent=2)
    print(f"Written to {output_path}")