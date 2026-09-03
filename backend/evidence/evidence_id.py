import uuid
from datetime import datetime


def generate_evidence_id():

    date_part = datetime.now().strftime("%Y%m%d")

    unique_part = uuid.uuid4().hex[:8].upper()

    evidence_id = (
        f"EVD-{date_part}-{unique_part}"
    )

    return evidence_id


if __name__ == "__main__":

    evidence_id = generate_evidence_id()

    print("\nEVIDENCE ID GENERATOR")
    print("────────────────────────────")

    print(
        "Generated Evidence ID:",
        evidence_id
    )