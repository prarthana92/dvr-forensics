
import json
import os
from collections import defaultdict

def generate_summary(events_json_path: str, output_txt_path: str = "summary_report.txt"):
    with open(events_json_path, "r") as f:
        data = json.load(f)

    video_source = data.get("video_source", "unknown")
    sha256_hash = data.get("sha256_hash", "unknown")
    analyzed_at = data.get("analyzed_at", "unknown")
    events = data.get("events", [])

    # group by detection_type + label
    grouped = defaultdict(list)
    for e in events:
        key = (e["detection_type"], e.get("label") or e["detection_type"])
        grouped[key].append(e)

    lines = []
    lines.append("=" * 60)
    lines.append("FORENSIC AI ANALYSIS SUMMARY")
    lines.append("=" * 60)
    lines.append(f"Video source : {video_source}")
    lines.append(f"SHA-256 hash : {sha256_hash}")
    lines.append(f"Analyzed at  : {analyzed_at}")
    lines.append(f"Total events : {len(events)}")
    lines.append("-" * 60)

    for (detection_type, label), group in sorted(grouped.items()):
        timestamps = [g["timestamp_sec"] for g in group]
        confidences = [g["confidence"] for g in group if g.get("confidence") is not None]

        first_seen = min(timestamps)
        last_seen = max(timestamps)
        count = len(group)

        line = f"- {label.capitalize()} ({detection_type}): {count} detections, " \
               f"first at {first_seen:.1f}s, last at {last_seen:.1f}s"

        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            line += f", avg confidence {avg_conf:.2f}"

        lines.append(line)

    lines.append("=" * 60)

    report = "\n".join(lines)
    print(report)

    with open(output_txt_path, "w") as f:
        f.write(report)

    print(f"\nSummary saved to {output_txt_path}")
    return report

if __name__ == "__main__":
    events_path = os.path.join(os.path.dirname(__file__), 'events_output.json')
    generate_summary(events_path)