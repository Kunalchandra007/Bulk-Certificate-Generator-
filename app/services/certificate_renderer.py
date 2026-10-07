"""Generates PDF certificates using ReportLab.

Uses atomic writes (render to temp file, then rename) so a crash mid-render
never leaves a corrupt PDF on disk.
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# Register Unicode fonts
FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"
pdfmetrics.registerFont(TTFont("Roboto", FONTS_DIR / "Roboto-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Roboto-Bold", FONTS_DIR / "Roboto-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Roboto-Italic", FONTS_DIR / "Roboto-Italic.ttf"))


@dataclass
class CertificateData:
    recipient_name: str
    job_title: str
    issuer_name: str
    issue_date: str
    certificate_number: str
    extra: str | None


def _split_name(name: str, font: str, font_size: float, max_width: float) -> tuple[str, str]:
    """Split a name into two lines that each fit within max_width.

    Prefers splitting on spaces. Falls back to splitting by character width
    when the name has no spaces (e.g. "AAAA...").
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth

    words = name.split()

    if len(words) >= 2:
        # Try every space-boundary and pick the split closest to half-width
        best_idx = len(words) // 2
        for i in range(1, len(words)):
            line1 = " ".join(words[:i])
            if stringWidth(line1, font, font_size) > max_width:
                best_idx = max(i - 1, 1)
                break
            best_idx = i
        return " ".join(words[:best_idx]), " ".join(words[best_idx:])

    # No spaces — split by character width at the midpoint
    half = max_width
    acc = 0.0
    split_pos = len(name) // 2  # fallback
    for i, ch in enumerate(name):
        acc += stringWidth(ch, font, font_size)
        if acc > half:
            split_pos = i
            break
    return name[:split_pos], name[split_pos:]


def render_certificate(data: CertificateData, output_path: Path) -> None:
    """Render a certificate to the given path atomically."""
    # Ensure parent dir exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Render to a temporary file first
    fd, temp_path_str = tempfile.mkstemp(dir=output_path.parent, suffix=".pdf")
    os.close(fd)
    temp_path = Path(temp_path_str)

    try:
        c = canvas.Canvas(str(temp_path), pagesize=landscape(A4))
        width, height = landscape(A4)

        # Draw double border
        c.setStrokeColorRGB(0.2, 0.4, 0.6)  # colored accent
        c.setLineWidth(4)
        c.rect(30, 30, width - 60, height - 60)
        c.setLineWidth(1)
        c.rect(35, 35, width - 70, height - 70)

        # Title
        c.setFont("Roboto-Bold", 36)
        c.drawCentredString(width / 2.0, height - 120, "Certificate of Completion")

        # Static text
        c.setFont("Roboto", 16)
        c.drawCentredString(width / 2.0, height - 180, "This is to certify that")

        # Recipient name — shrink to fit, wrap to two lines if needed
        name = data.recipient_name
        max_width = 700  # points available between borders
        min_font = 14

        name_y = height - 250  # baseline for single-line name
        completed_y = height - 310  # baseline for "has successfully completed"

        font_size = 48
        from reportlab.pdfbase.pdfmetrics import stringWidth

        # Step 1: shrink font until it fits or we hit the floor
        while font_size > min_font and stringWidth(name, "Roboto-Bold", font_size) > max_width:
            font_size -= 2

        if stringWidth(name, "Roboto-Bold", font_size) <= max_width:
            # Single line — fits fine
            c.setFont("Roboto-Bold", font_size)
            c.drawCentredString(width / 2.0, name_y, name)
        else:
            # Still too wide at min_font — split into two lines
            line1, line2 = _split_name(name, "Roboto-Bold", font_size, max_width)
            line_gap = font_size + 4  # vertical spacing between lines
            # Shift the two-line block up so it stays centred between
            # "This is to certify that" (y = height-180) and
            # "has successfully completed" (y = height-310)
            top_y = name_y + line_gap / 2
            c.setFont("Roboto-Bold", font_size)
            c.drawCentredString(width / 2.0, top_y, line1)
            c.drawCentredString(width / 2.0, top_y - line_gap, line2)

        # Static text
        c.setFont("Roboto", 16)
        c.drawCentredString(width / 2.0, completed_y, "has successfully completed")

        # Job title
        c.setFont("Roboto-Italic", 24)
        c.drawCentredString(width / 2.0, height - 360, data.job_title)

        # Extra
        if data.extra:
            c.setFont("Roboto", 14)
            c.drawCentredString(width / 2.0, height - 400, data.extra)

        # Footer
        c.setFont("Roboto", 12)
        # Date (left)
        c.drawString(100, 100, f"Date: {data.issue_date}")

        # Issuer (right)
        c.drawRightString(width - 100, 120, data.issuer_name)
        c.setLineWidth(1)
        c.line(width - 250, 115, width - 100, 115)  # Signature line

        # Certificate number (bottom center)
        c.setFont("Helvetica", 10)
        c.drawCentredString(width / 2.0, 60, f"Certificate No: {data.certificate_number}")

        c.save()

        # Atomically rename temp file to final destination
        temp_path.replace(output_path)

    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise e
