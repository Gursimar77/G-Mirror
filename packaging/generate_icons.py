"""
G-Mirror Icon Generator.
Creates a G-Mirror .ico file and PNG assets without any Apple artwork.
The icon is a clean, original iPhone silhouette with a mirror/reflection motif.
"""

import os
from pathlib import Path


def generate_icons(output_dir: str) -> None:
    """Generate G-Mirror icons as PNG and ICO files using Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow not available — skipping icon generation")
        return

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    sizes = [16, 32, 48, 128, 256]
    pngs = []

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Scale factors
        s = size / 256.0

        # Background circle (deep navy)
        r = int(120 * s)
        cx, cy = size // 2, size // 2
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(15, 25, 60, 255))

        # Phone body (rounded rectangle)
        pw = int(80 * s)
        ph = int(140 * s)
        px = cx - pw // 2
        py = cy - ph // 2
        corner = max(4, int(12 * s))
        draw.rounded_rectangle([px, py, px + pw, py + ph], radius=corner, fill=(30, 50, 100, 255))

        # Phone screen (slightly lighter)
        sw = pw - int(12 * s)
        sh = ph - int(30 * s)
        sx = px + int(6 * s)
        sy = py + int(12 * s)
        draw.rounded_rectangle([sx, sy, sx + sw, sy + sh], radius=max(2, int(6 * s)), fill=(20, 180, 150, 200))

        # Mirror reflection lines on screen (teal diagonals)
        for i in range(3):
            offset = int((i * 14) * s)
            lx = sx + int(8 * s) + offset
            draw.line([(lx, sy + int(8 * s)), (lx + int(20 * s), sy + int(28 * s))],
                      fill=(255, 255, 255, 180), width=max(1, int(2 * s)))

        # Home indicator bar at bottom
        bar_w = int(40 * s)
        bar_h = max(2, int(4 * s))
        bar_x = cx - bar_w // 2
        bar_y = py + ph - int(10 * s)
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
                                radius=bar_h // 2, fill=(78, 204, 163, 255))

        path = str(Path(output_dir) / f"gmirror_{size}.png")
        img.save(path, "PNG")
        pngs.append((size, size, img))
        print(f"Generated: {path}")

    # Build .ico from all sizes
    ico_path = str(Path(output_dir) / "gmirror.ico")
    images_for_ico = [Image.open(str(Path(output_dir) / f"gmirror_{s}.png")) for s in sizes]
    images_for_ico[0].save(ico_path, format="ICO", sizes=[(s, s) for s in sizes],
                           append_images=images_for_ico[1:])
    print(f"Generated: {ico_path}")


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "assets", "icons")
    generate_icons(out)
