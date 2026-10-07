"""Verify PDF layout math for all name scenarios."""
from app.services.certificate_renderer import _split_name  # triggers font registration
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.pagesizes import A4, landscape

width, height = landscape(A4)
max_name_width = 700
border_inner = 35
usable_width = width - 2 * border_inner

print(f"Page: {width:.0f} x {height:.0f} pts")
print(f"Usable width (inside inner border): {usable_width:.0f} pts")
print(f"Max name width: {max_name_width} pts")
print()

# 1. Normal name
name = "Asha Rao"
w = stringWidth(name, "Roboto-Bold", 48)
print(f"Normal ({name}): {w:.0f}pt wide at 48pt font => FITS? {w <= max_name_width}")

# 2. Unicode
name = "Zoë Müller"
w = stringWidth(name, "Roboto-Bold", 48)
print(f"Unicode ({name}): {w:.0f}pt wide at 48pt font => FITS? {w <= max_name_width}")

# 3. 90 chars no spaces
name = "A" * 90
from app.services.certificate_renderer import _split_name
l1, l2 = _split_name(name, "Roboto-Bold", 14, max_name_width)
w1 = stringWidth(l1, "Roboto-Bold", 14)
w2 = stringWidth(l2, "Roboto-Bold", 14)
print(f"Long no-spaces (90 A): _split_name => [{len(l1)}] + [{len(l2)}] chars")
print(f"  Widths: {w1:.0f} + {w2:.0f} pts => Both fit? {w1 <= max_name_width and w2 <= max_name_width}")

# 4. 90 chars with spaces
name = "Bartholomew Alexander Maximilian Christopherson Worthington III Esquire of Canterbury Town"
font_size = 48
while font_size > 14 and stringWidth(name, "Roboto-Bold", font_size) > max_name_width:
    font_size -= 2
w = stringWidth(name, "Roboto-Bold", font_size)
if w <= max_name_width:
    print(f"Long with spaces: {w:.0f}pt at {font_size}pt => single line fits")
else:
    l1, l2 = _split_name(name, "Roboto-Bold", font_size, max_name_width)
    w1 = stringWidth(l1, "Roboto-Bold", font_size)
    w2 = stringWidth(l2, "Roboto-Bold", font_size)
    print(f"Long with spaces: needs wrap at {font_size}pt")
    print(f'  Line 1: "{l1}" ({w1:.0f}pt)')
    print(f'  Line 2: "{l2}" ({w2:.0f}pt)')
    print(f"  Both fit? {w1 <= max_name_width and w2 <= max_name_width}")

# Check Y positions don't overlap
name_y = height - 250
completed_y = height - 310
line_gap = 14 + 4
top_y = name_y + line_gap / 2
bottom_y = top_y - line_gap
print()
print(f"Two-line name Y positions: top={top_y:.0f}, bottom={bottom_y:.0f}")
print(f"Completed text at: {completed_y:.0f}")
print(f"Gap between bottom name line and completed text: {bottom_y - completed_y:.0f}pt")
print(f"Overlap? {bottom_y < completed_y + 16}")
