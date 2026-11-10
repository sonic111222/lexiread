"""Generate the project icon from code (Pillow)."""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

GREEN = (22, 63, 53, 255)
GREEN_DARK = (13, 43, 35, 255)
CREAM = (247, 240, 222, 255)
CORAL = (194, 94, 63, 255)
GOLD = (178, 135, 61, 255)


def draw_icon(size: int = 1024) -> Image.Image:
    scale = size / 1024
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def s(value):
        return int(round(value * scale))

    draw.rounded_rectangle((s(32), s(32), s(992), s(992)), radius=s(218), fill=GREEN)
    draw.rounded_rectangle((s(62), s(62), s(962), s(962)), radius=s(190), outline=(255, 255, 255, 24), width=s(3))

    # Two open pages.
    left = [(s(482), s(380)), (s(388), s(328)), (s(244), s(350)), (s(244), s(682)), (s(388), s(660)), (s(482), s(716))]
    right = [(s(542), s(380)), (s(636), s(328)), (s(780), s(350)), (s(780), s(682)), (s(636), s(660)), (s(542), s(716))]
    draw.polygon(left, fill=CREAM)
    draw.polygon(right, fill=CREAM)
    draw.rounded_rectangle((s(478), s(370), s(546), s(730)), radius=s(16), fill=GREEN_DARK)

    # Page content lines.
    for index in range(4):
        y = s(438 + index * 48)
        draw.rounded_rectangle((s(314), y, s(440 - index * 14), y + s(10)), radius=s(5), fill=(29, 70, 58, 110))
        draw.rounded_rectangle((s(584), y, s(710 + index * 10), y + s(10)), radius=s(5), fill=(29, 70, 58, 110))

    # Coral spark.
    draw.ellipse((s(740), s(178), s(844), s(282)), fill=CORAL)
    draw.ellipse((s(792), s(246), s(838), s(292)), fill=GOLD)
    return image


def main() -> None:
    image = draw_icon(1024)
    image.save(ASSETS / "lexiread.png")
    image.save(
        ASSETS / "lexiread.ico",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"wrote {ASSETS / 'lexiread.ico'}")


if __name__ == "__main__":
    main()
