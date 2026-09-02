from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER


# --------------------------------------------------
# PATHS
# --------------------------------------------------

BACKEND_FOLDER = Path(__file__).resolve().parent.parent

REPORT_FOLDER = (
    BACKEND_FOLDER
    / "reports"
)


# --------------------------------------------------
# FIND LATEST TEXT REPORT
# --------------------------------------------------

def find_latest_report():

    reports = sorted(
        REPORT_FOLDER.glob(
            "*_forensic_report.txt"
        ),
        key=lambda file: file.stat().st_mtime,
        reverse=True
    )

    if not reports:

        raise FileNotFoundError(
            "No forensic text report found."
        )

    return reports[0]


# --------------------------------------------------
# CREATE PDF
# --------------------------------------------------

def create_pdf(text_report):

    evidence_id = (
        text_report.stem
        .replace(
            "_forensic_report",
            ""
        )
    )

    pdf_path = (
        REPORT_FOLDER
        / f"{evidence_id}_forensic_report.pdf"
    )

    document = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    title_style.alignment = TA_CENTER

    heading_style = styles["Heading2"]

    normal_style = styles["BodyText"]

    story = []

    # --------------------------------------------------
    # READ TEXT REPORT
    # --------------------------------------------------

    with open(
        text_report,
        "r",
        encoding="utf-8"
    ) as file:

        lines = file.readlines()

    # --------------------------------------------------
    # CONVERT TEXT INTO PDF
    # --------------------------------------------------

    for line in lines:

        line = line.strip()

        if not line:

            story.append(
                Spacer(1, 8)
            )

            continue

        if (
            "DVR FORENSIC ANALYSIS REPORT"
            in line
        ):

            story.append(
                Paragraph(
                    "DVR FORENSIC ANALYSIS REPORT",
                    title_style
                )
            )

            story.append(
                Spacer(1, 15)
            )

            continue

        if (
            line.isupper()
            and len(line) < 60
            and not line.startswith("=")
            and not line.startswith("-")
        ):

            story.append(
                Paragraph(
                    line,
                    heading_style
                )
            )

            continue

        if (
            line.startswith("=")
            or line.startswith("-")
        ):

            continue

        # Escape special HTML characters

        line = (
            line
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        story.append(
            Paragraph(
                line,
                normal_style
            )
        )

    # --------------------------------------------------
    # BUILD PDF
    # --------------------------------------------------

    document.build(story)

    return pdf_path


# --------------------------------------------------
# MAIN
# --------------------------------------------------

if __name__ == "__main__":

    print("\n" + "=" * 70)
    print("             PDF FORENSIC REPORT GENERATOR")
    print("=" * 70)

    try:

        text_report = find_latest_report()

        print(
            "\nUsing report:"
        )

        print(
            text_report
        )

        pdf_file = create_pdf(
            text_report
        )

        print(
            "\n✓ PDF forensic report generated."
        )

        print(
            "Saved as:"
        )

        print(
            pdf_file
        )

        print("\n" + "=" * 70)

    except Exception as error:

        print(
            "\n❌ Error:",
            error
        )