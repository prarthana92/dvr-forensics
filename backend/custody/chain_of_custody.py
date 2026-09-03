import json
from pathlib import Path
from datetime import datetime


# ============================================================
# BACKEND FOLDER
# ============================================================

BACKEND_FOLDER = Path(__file__).resolve().parent.parent

CUSTODY_FOLDER = (
    BACKEND_FOLDER / "output" / "custody"
)


# ============================================================
# CREATE CUSTODY FOLDER
# ============================================================

CUSTODY_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# ADD CUSTODY EVENT
# ============================================================

def add_custody_event(
    evidence_id,
    action,
    description
):

    custody_file = (
        CUSTODY_FOLDER
        / f"{evidence_id}_custody.json"
    )

    # --------------------------------------------------------
    # LOAD EXISTING CUSTODY RECORD
    # --------------------------------------------------------

    if custody_file.exists():

        with open(
            custody_file,
            "r",
            encoding="utf-8"
        ) as file:

            custody_record = json.load(file)

    else:

        custody_record = {

            "evidence_id": evidence_id,

            "chain_of_custody": []

        }

    # --------------------------------------------------------
    # CREATE NEW EVENT
    # --------------------------------------------------------

    event = {

        "timestamp":
            datetime.now().isoformat(),

        "action":
            action,

        "description":
            description

    }

    # --------------------------------------------------------
    # ADD EVENT
    # --------------------------------------------------------

    custody_record[
        "chain_of_custody"
    ].append(event)

    # --------------------------------------------------------
    # SAVE RECORD
    # --------------------------------------------------------

    with open(
        custody_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            custody_record,
            file,
            indent=4
        )

    return custody_file


# ============================================================
# DISPLAY CUSTODY RECORD
# ============================================================

def display_custody_record(evidence_id):

    custody_file = (
        CUSTODY_FOLDER
        / f"{evidence_id}_custody.json"
    )

    if not custody_file.exists():

        print(
            "\nNo chain-of-custody record found."
        )

        return

    with open(
        custody_file,
        "r",
        encoding="utf-8"
    ) as file:

        custody_record = json.load(file)

    print("\n" + "=" * 70)

    print(
        "                 CHAIN OF CUSTODY"
    )

    print("=" * 70)

    print(
        "\nEvidence ID:",
        evidence_id
    )

    print(
        "\nCustody Events:"
    )

    print("-" * 70)

    for number, event in enumerate(
        custody_record[
            "chain_of_custody"
        ],
        start=1
    ):

        print(
            f"\nEvent {number}"
        )

        print(
            "Timestamp   :",
            event["timestamp"]
        )

        print(
            "Action      :",
            event["action"]
        )

        print(
            "Description :",
            event["description"]
        )

    print("\n" + "=" * 70)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("\n" + "=" * 70)

    print(
        "             CHAIN OF CUSTODY TEST"
    )

    print("=" * 70)

    evidence_id = input(
        "\nEnter evidence ID: "
    ).strip()

    if not evidence_id:

        print(
            "\nEvidence ID cannot be empty."
        )

    else:

        custody_file = add_custody_event(

            evidence_id,

            "TEST_EVENT",

            "Chain of custody module tested successfully."

        )

        print(
            "\n✓ Custody event added."
        )

        print(
            "Saved as:"
        )

        print(
            custody_file
        )

        display_custody_record(
            evidence_id
        )