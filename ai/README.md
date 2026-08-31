
# AI Layer — DVR/NVR Forensic Analysis Tool (TraceX)

Handles motion, object, face, and anomaly detection on forensic video, producing
a compact results JSON for backend to store and connect to the timeline/report.

## Setup

Requires Python **3.11.x** specifically — MediaPipe does not support 3.14+.

```bash
cd ai
py -3.11 -m venv venv
venv\Scripts\activate          # Windows CMD/PowerShell
source venv/Scripts/activate   # Git Bash

pip install opencv-python ultralytics mediapipe numpy pydantic
```

## Modules

| Module | What it does |
|---|---|
| `motion/detector.py` | Motion detection via OpenCV MOG2 background subtraction |
| `object_detection/detector.py` | Object detection via YOLOv8n (person, car, truck, motorcycle, bicycle, backpack, handbag), motion-gated |
| `face_detection/detector.py` | Face detection via MediaPipe, motion-gated |
| `anomaly/detector.py` | Flags frozen/static segments, timestamp jumps, frame count mismatches |
| `correlation/event_linker.py` | Links detections across multiple camera sources (needs multi-camera input to produce results — returns empty on a single video) |
| `utils/frame_selector.py` | Motion-gating: determines which frames need heavier (object/face) processing |
| `utils/filtering.py` | Filters detections by minimum confidence |
| `utils/format_converter.py` | Converts internal flat event list into the backend's agreed JSON schema — aggregates motion per frame, keeps object/face/anomaly individual |
| `utils/event_schema.py` | Internal `DetectionEvent` data model used across all detectors |

## Running the pipeline

```bash
python pipeline.py
```

Reads `sample_data/test1.mp4`, runs all four detectors, filters low-confidence
object/face detections, and writes the final handoff file: **`ai_results.json`**.

## Output — `ai_results.json`

This is the one file backend consumes. Shape:

```json
{
  "events": [
    {
      "frame": 120,
      "timestamp_seconds": 4.0,
      "detections": [
        { "type": "motion", "label": "movement", "region_count": 17 },
        { "type": "object", "label": "person", "confidence": 0.94, "bbox": [x, y, w, h] },
        { "type": "face", "label": "face", "confidence": 0.88, "bbox": [x, y, w, h] },
        { "type": "anomaly", "label": "frozen_segment" }
      ]
    }
  ]
}
```

- **Motion** is aggregated per frame into one summary event (`region_count`) —
  individual bounding boxes are not sent, to keep the file manageable on
  full-length CCTV footage. Set `include_motion_regions=True` in
  `convert_to_final_format()` if raw regions are ever needed.
- **Object/face** detections are filtered by confidence before output — default
  threshold **0.4**, configurable via `run_pipeline(..., confidence_threshold=0.4)`.
  Anything below the threshold is dropped, not sent to backend.
- **Anomaly** events are always kept individually (no filtering).

## Division of responsibility (agreed with backend)

AI does **not** handle: forensic copying, evidence hashing, metadata extraction,
recovery, or building the evidence record. AI reads the verified forensic video
directly and returns only the detection-results JSON. Backend stores and
connects results to the timeline/report — it does not re-run or override AI's
confidence decisions.

## Known limitations

- Object detection confidence can be low (~0.25–0.5) on small/distant objects in
  wide-angle footage — the 0.4 filter threshold accounts for this but may need
  tuning per footage type.
- Correlation module only produces results with multiple video sources from the
  same time window.
- AI reads the raw video directly (not backend's extracted frame images) —
  required for motion/anomaly detection, which need continuous frame-to-frame
  comparison.