
def filter_by_confidence(events: list, min_confidence: float = 0.5) -> list:
    """Returns only events at or above the given confidence threshold.
    Motion/anomaly events (no confidence score) always pass through."""
    return [e for e in events if e.get("confidence") is None or e["confidence"] >= min_confidence]