"""Generate the GitHub social preview image (1280×640)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SHOT = ROOT / "docs" / "screenshots" / "reader.png"
OUT = ROOT / "docs" / "social-preview.png"

GREEN = (23, 63, 53)
GREEN_DARK = (13, 42, 34)
CREAM = (247, 241, 226)
CORAL = (194, 94, 63)
GOLD = (190, 156, 95)
MUTED = (185, 200, 186)


def font(path: str, size: int):
    return ImageFont.truetype(path, size)


def main():
    canvas = Image.new("RGB", (1280, 640), GREEN)
    # Soft vertical gradient.
    top = (26, 70, 58)
    bottom = (12, 37, 30)
    for y in range(640):
        ratio = y / 639
        color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        draw = ImageDraw.Draw(canvas)
        draw.line((0, y, 1280, y), fill=color)
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((1090, -190, 1470, 190), fill=(35, 84, 67))
    draw.ellipse((1130, -135, 1400, 135), fill=(29, 74, 59))
    draw.ellipse((1147, 14, 1194, 61), fill=CORAL)
    draw.ellipse((1166, 42, 1188, 64), fill=GOLD)

    # Copy and shadow.
    try:
        shot = Image.open(SHOT).convert("RGB")
        crop = shot.crop((250, 80, 1050, 900))
        crop.thumbnail((450, 500), Image.Resampling.LANCZOS)
        card_w, card_h = 500, 520
        card_x, card_y = 710, 60
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle(
            (card_x + 12, card_y + 18, card_x + card_w + 12, card_y + card_h + 18),
            radius=26,
            fill=(0, 0, 0, 90),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow).convert("RGB")
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((card_x, card_y, card_x + card_w, card_y + card_h), radius=26, fill=CREAM)
        draw.rounded_rectangle((card_x + 24, card_y + 22, card_x + 190, card_y + 46), radius=8, fill=(235, 228, 214))
        for i, color in enumerate([CORAL, (224, 183, 111), (145, 177, 153)]):
            draw.ellipse((card_x + 30 + i * 15, card_y + 30, card_x + 38 + i * 15, card_y + 38), fill=color)
        px = card_x + (card_w - crop.width) // 2
        py = card_y + 60
        canvas.paste(crop, (px, py))
        draw.rounded_rectangle((card_x, card_y, card_x + card_w, card_y + card_h), radius=26, outline=(232, 222, 203), width=2)
    except Exception as exc:
        print("screenshot skipped:", exc)

    # Left copy.
    draw.text((72, 92), "LEXIREAD", font=font("C:/Windows/Fonts/arialbd.ttf", 19), fill=(211, 168, 121))
    draw.text((70, 130), "LexiRead", font=font("C:/Windows/Fonts/georgiab.ttf", 87), fill=CREAM)
    draw.text((74, 235), "精读工坊", font=font("C:/Windows/Fonts/msyh.ttc", 29), fill=(191, 208, 194))
    draw.text((72, 310), "把一张英语题图，", font=font("C:/Windows/Fonts/msyh.ttc", 36), fill=CREAM)
    draw.text((72, 360), "读成一堂课。", font=font("C:/Windows/Fonts/msyh.ttc", 36), fill=(224, 176, 133))

    pills = ["本地 OCR", "点词学习", "生词复习", "AI 可选"]
    x = 72
    for label in pills:
        f = font("C:/Windows/Fonts/msyh.ttc", 17)
        bbox = draw.textbbox((0, 0), label, font=f)
        w = bbox[2] - bbox[0] + 28
        draw.rounded_rectangle((x, 448, x + w, 486), radius=19, outline=(104, 139, 114), width=1)
        draw.text((x + 14, 456), label, font=f, fill=(222, 233, 221))
        x += w + 10

    draw.line((72, 535, 590, 535), fill=(77, 115, 92), width=1)
    draw.text((72, 554), "Windows · Local-first · Source-available", font=font("C:/Windows/Fonts/arial.ttf", 17), fill=(151, 173, 155))
    draw.text((72, 584), "Noncommercial use · no account · no telemetry", font=font("C:/Windows/Fonts/arial.ttf", 15), fill=(119, 148, 125))

    canvas.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
