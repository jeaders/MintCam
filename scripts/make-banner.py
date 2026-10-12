#!/usr/bin/env python3
"""Generate the MintCam banners (repository and AppStream).

The banners were raster images that had to be edited by hand every time the
technology or the version changed, and one of them still advertised PySide6
after the move to PyQt6. This script regenerates them so the content is always
in sync with the code.

Usage: python3 scripts/make-banner.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "assets"

VERSION = "0.2.7"
TECH_LINE = "Open Source · Python · PyQt6 · OpenCV"

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# Palette sampled from the previous banner.
BG_TOP = (16, 28, 44)
BG_MID = (26, 74, 58)
GRID = (255, 255, 255)
TITLE = (255, 255, 255)
SUBTITLE = (176, 209, 196)
TECH = (150, 190, 172)
def _pills():
    return [
        ((58, 108, 168), (235, 242, 250)),   # Live Preview
        ((44, 138, 84), (235, 250, 240)),    # Recording
        ((128, 62, 160), (244, 236, 250)),   # QR Scanner
        ((196, 118, 32), (252, 244, 232)),   # Focus Assist
        ((26, 148, 148), (232, 250, 250)),   # Time-lapse
    ]


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _gradient(size) -> Image.Image:
    """Vertical gradient from navy blue at the top to deep green."""
    w, h = size
    img = Image.new("RGB", (1, h))
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        if t < 0.5:
            k = t / 0.5
            col = tuple(int(BG_TOP[i] + (BG_MID[i] - BG_TOP[i]) * k) for i in range(3))
        else:
            k = (t - 0.5) / 0.5
            col = tuple(int(BG_MID[i] + (BG_TOP[i] - BG_MID[i]) * k * 0.75) for i in range(3))
        px[0, y] = col
    return img.resize((w, h))


def _grid(img: Image.Image, step: int) -> None:
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=(255, 255, 255, 14), width=1)
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=(255, 255, 255, 14), width=1)


def _rings(d: ImageDraw.ImageDraw, cx: int, cy: int, radii, color) -> None:
    for r in radii:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=2)


def _camera_icon(size_px: int) -> Image.Image:
    """A simple camera glyph on a transparent tile."""
    s = size_px
    tile = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    body = [s * 0.10, s * 0.28, s * 0.90, s * 0.74]
    d.rounded_rectangle(body, radius=int(s * 0.10), fill=(15, 30, 44, 255),
                        outline=(96, 150, 210, 255), width=max(2, s // 128))
    d.ellipse([s * 0.30, s * 0.38, s * 0.70, s * 0.78], outline=(120, 200, 235, 255),
              width=max(2, s // 96))
    d.rectangle([s * 0.38, s * 0.20, s * 0.62, s * 0.28], fill=(15, 30, 44, 255),
                outline=(96, 150, 210, 255))
    return tile


def render(width: int, height: int) -> Image.Image:
    img = _gradient((width, height))
    d = ImageDraw.Draw(img, "RGBA")
    _grid(img, width // 32)
    d = ImageDraw.Draw(img, "RGBA")

    # decorative rings, echoing the previous banner
    cx, cy = width * 0.42, height * 0.42
    _rings(d, int(cx), int(cy), [int(width * f) for f in (0.30, 0.38, 0.46, 0.54)],
           (110, 150, 190, 70))
    _rings(d, int(width * 0.80), int(height * 0.78),
           [int(width * f) for f in (0.16, 0.24, 0.32)], (110, 160, 140, 55))
    d.ellipse([width * 0.905, height * 0.10, width * 0.925, height * 0.122],
              fill=(239, 68, 68, 255))

    # camera icon on the left
    icon = _camera_icon(int(width * 0.16))
    img.paste(icon, (int(width * 0.10), int(height * 0.36)), icon)

    # title and subtitle
    title_font = _font(FONT_BOLD, int(height * 0.155))
    sub_font = _font(FONT_REG, int(height * 0.058))
    d.text((width * 0.30, height * 0.60), "MintCam", font=title_font, fill=TITLE)
    d.text((width * 0.305, height * 0.775), "Webcam Studio for Linux Mint",
           font=sub_font, fill=SUBTITLE)

    # feature pills
    pill_font = _font(FONT_REG, int(height * 0.040))
    y = int(height * 0.885)
    labels = ["Live Preview", "Recording", "QR Scanner", "Focus Assist", "Time-lapse"]
    gap = int(width * 0.010)
    # shrink the font until the row fits between the icon column and the edge
    while True:
        widths = [d.textlength(t, font=pill_font) + int(height * 0.022) * 2 for t in labels]
        if sum(widths) + gap * (len(labels) - 1) <= width * 0.62 or pill_font.size <= 10:
            break
        pill_font = _font(FONT_REG, pill_font.size - 1)
        widths = [d.textlength(t, font=pill_font) + int(height * 0.022) * 2 for t in labels]
    x = int(width * 0.30)
    for (fill, text_colour), label, wpx in zip(_pills(), labels, widths):
        _pill(d, label, pill_font, x, y, pad=int(height * 0.022),
              fill=fill, text_colour=text_colour)
        x += wpx + gap

    # technology line and version, along the bottom edge
    tech_font = _font(FONT_REG, int(height * 0.038))
    ver_font = _font(FONT_BOLD, int(height * 0.038))
    ver_text = f"v{VERSION}"
    tw = d.textlength(TECH_LINE, font=tech_font)
    vw = d.textlength(ver_text, font=ver_font)
    total = tw + width * 0.03 + vw
    x = (width - total) / 2
    y = height * 0.945
    d.text((x, y), TECH_LINE, font=tech_font, fill=TECH)
    d.text((x + tw + width * 0.03, y), ver_text, font=ver_font, fill=(92, 217, 98))
    return img


def _pill(d, text, font, x, y, pad, fill, text_colour):
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.rounded_rectangle([x, y, x + tw + pad * 2, y + th + pad * 2],
                        radius=(th + pad * 2) // 2, fill=fill)
    d.text((x + pad, y + pad - bbox[1]), text, font=font, fill=text_colour)
    return tw + pad * 2


def main() -> None:
    render(1600, 900).save(ASSETS / "mintcam-banner-1600x900.png")
    render(885, 524).save(ASSETS / "banner.png")
    print("banner rigenerati: mintcam-banner-1600x900.png, banner.png")


if __name__ == "__main__":
    main()
