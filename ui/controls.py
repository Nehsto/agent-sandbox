"""Shared shortcut legend with a distinct color and bold key per action."""
from PIL import ImageFont

FONT = ImageFont.load_default(size=11)
try:
    BOLD = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 11)
except OSError:
    BOLD = FONT
COLORS = {'m': '#61ead4', 'f': '#61ead4', 'h': '#ffd580',
          'c': '#61ead4', 'r': '#ffd580', 'b': '#96baff', 'n': '#d6a3ff', 'q': '#ff9ca8'}


def shortcuts(draw, y, items):
    x = 10
    for key, label in items:
        color = COLORS[key]
        draw.text((x, y), key.upper(), font=BOLD, fill=color,
                  stroke_width=1 if BOLD is FONT else 0)
        x += int(draw.textlength(key.upper(), font=BOLD)) + 4
        draw.text((x, y), label, font=FONT, fill=color)
        x += int(draw.textlength(label, font=FONT)) + 13
