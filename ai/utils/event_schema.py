
from pydantic import BaseModel
from typing import Optional, List

class DetectionEvent(BaseModel):
    event_id: str
    video_source: str
    frame_number: int
    timestamp_sec: float          # seconds into video; backend normalizes to real time
    detection_type: str           # "motion" | "object" | "face"
    label: Optional[str] = None   # e.g. "person", "car"
    confidence: Optional[float] = None
    bbox: Optional[List[int]] = None   # [x, y, w, h]
    model: Optional[str] = None
    model_version: Optional[str] = None