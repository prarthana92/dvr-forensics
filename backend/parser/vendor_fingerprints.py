# ============================================================
# TRACE X - VENDOR FINGERPRINT DATABASE
# ============================================================

"""
Central database of vendor fingerprints.

IMPORTANT:
A fingerprint is only marked as validated when it has been
confirmed against a known reference sample from that vendor.

Unvalidated fingerprints are NOT used as forensic proof.
"""

VENDOR_FINGERPRINTS = {

    "HIKVISION": {
        "validated": False,

        "strong": [
            "HIKVISION",
            "HCNETSDK"
        ],

        "medium": [
            "DS-76",
            "DS-72",
            "DS-77"
        ]
    },

    "DAHUA": {
        "validated": False,

        "strong": [
            "DAHUA",
            "DHAV"
        ],

        "medium": [
            "DAHUA TECHNOLOGY"
        ]
    },

    "CP_PLUS": {
        "validated": False,

        "strong": [
            "CP PLUS",
            "CPPLUS",
            "CP-PLUS"
        ],

        "medium": [
            "CPPLUSINDIA"
        ]
    },

    "HONEYWELL": {
        "validated": False,

        "strong": [
            "HONEYWELL"
        ],

        "medium": [
            "HONEYWELL SECURITY"
        ]
    },

    "TP_LINK": {
        "validated": False,

        "strong": [
            "TP-LINK",
            "TP LINK"
        ],

        "medium": [
            "TP-LINK TECHNOLOGIES"
        ]
    },

    "GODREJ": {
        "validated": False,

        "strong": [
            "GODREJ"
        ],

        "medium": [
            "GODREJ SECURITY"
        ]
    },

    "UNIVIEW": {
        "validated": False,

        "strong": [
            "UNIVIEW"
        ],

        "medium": [
            "UNV NVR",
            "EZVIEW"
        ]
    },

    "MATRIX": {
        "validated": False,

        "strong": [
            "MATRIX"
        ],

        "medium": [
            "MATRIX COMSEC"
        ]
    }
}


# ============================================================
# SUPPORTED VENDORS
# ============================================================

SUPPORTED_VENDORS = list(
    VENDOR_FINGERPRINTS.keys()
)


# ============================================================
# VALIDATION HELPERS
# ============================================================

def get_validated_vendors():
    """
    Returns vendors whose fingerprints have been validated.
    """

    return [
        vendor
        for vendor, data in VENDOR_FINGERPRINTS.items()
        if data.get("validated", False)
    ]


def get_unvalidated_vendors():
    """
    Returns vendors whose fingerprints still require
    validation against reference evidence.
    """

    return [
        vendor
        for vendor, data in VENDOR_FINGERPRINTS.items()
        if not data.get("validated", False)
    ]


def is_vendor_validated(vendor):
    """
    Checks whether a vendor's fingerprint database
    has been validated.
    """

    vendor_data = VENDOR_FINGERPRINTS.get(vendor)

    if vendor_data is None:
        return False

    return vendor_data.get(
        "validated",
        False
    )


# ============================================================
# DATABASE TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("       TRACE X VENDOR FINGERPRINT DATABASE")
    print("=" * 60)

    for vendor in SUPPORTED_VENDORS:

        status = is_vendor_validated(
            vendor
        )

        print(
            f"{vendor:20} | "
            f"Validated: {status}"
        )

    validated = get_validated_vendors()
    unvalidated = get_unvalidated_vendors()

    print()
    print(
        f"Total supported vendors: "
        f"{len(SUPPORTED_VENDORS)}"
    )

    print()
    print(
        f"Validated vendors: "
        f"{validated}"
    )

    print(
        f"Unvalidated vendors: "
        f"{unvalidated}"
    )

    print()
    print("=" * 60)
    print("              DATABASE READY")
    print("=" * 60)