
def frames_with_motion(motion_events, padding_frames: int = 2) -> set:
    """
    Takes motion events and returns the set of frame numbers worth running
    heavier detectors (YOLO, face) on -- each motion frame plus a small
    buffer of neighboring frames, so we don't miss an object/face that's
    slightly out of sync with the exact motion frame.
    """
    frame_numbers = set(e.frame_number for e in motion_events)
    padded = set()
    for f in frame_numbers:
        for offset in range(-padding_frames, padding_frames + 1):
            if f + offset >= 0:
                padded.add(f + offset)
    return padded