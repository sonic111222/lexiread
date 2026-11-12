"""Generate the Xiaohongshu carousel for the first LexiRead note."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "xiaohongshu"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1080, 1440
M = 72
INK = (29, 41, 34)
GREEN = (23, 63, 53)
GREEN_2 = (44, 91, 75)
CORAL = (194, 94, 63)
GOLD = (178, 135, 61)
MUTED = (111, 123, 114)
PAPER = (255, 253, 248)
CREAM = (247, 241, 229)
LINE = (226, 217, 201)
FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
SERIF = "C:/Windows/Fonts/georgia.ttf"
SERIF_BOLD = "C:/Windows/Fonts/georgiab.ttf"
ICON = ROOT / "assets" / "lexiread.png"
READER = ROOT / "docs" / "screenshots" / "reader.png"
WORD_DRAWER = ROOT / "docs" / "screenshots" / "word-drawer.png"
ARTIFACTS = Path(r"C:/Users/86191/.zcode/cli/artifacts/sess_de2f7516-a5a6-4859-a7cf-cfd5fa252aaf")
EVIDENCE = ARTIFACTS / "call_00_mhbxoq90haxnj77ua286tmj3-tool-result-64aedd98-ae1c-42ae-87e3-d198df2522f4.png"


def f(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def wrap(text: str, draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            candidate = current + char
            if text_width(draw, candidate, font) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill,
    max_width: int,
    line_height: int,
    max_lines: int | None = None,
) -> int:
    lines = wrap(text, draw, font, max_width)
    if max_lines:
        lines = lines[:max_lines]
    for index, line in enumerate(lines):
        draw.text((x, y + index * line_height), line, font=font, fill=fill)
    return y + len(lines) * line_height


def background() -> Image.Image:
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    top = (250, 246, 237)
    bottom = (237, 230, 218)
    for y in range(H):
        ratio = y / (H - 1)
        color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3)) + (255,)
        ImageDraw.Draw(canvas).line((0, y, W, y), fill=color)
    draw = ImageDraw.Draw(canvas, "RGBA")
    # Quiet editorial texture.
    for y in range(138, H, 82):
        draw.line((M, y, W - M, y), fill=(110, 101, 84, 12), width=1)
    draw.ellipse((W - 140, 152, W + 120, 412), fill=(23, 63, 53, 18))
    draw.ellipse((W - 120, 172, W + 92, 392), outline=(23, 63, 53, 22), width=2)
    draw.ellipse((-150, H - 140, 150, H + 160), outline=(178, 135, 61, 28), width=2)
    draw.ellipse((W - 128, 142, W - 100, 170), fill=(194, 94, 63, 145))
    return canvas


def header(canvas: Image.Image, page: int, total: int = 8, kicker: str = "英语精读笔记") -> None:
    draw = ImageDraw.Draw(canvas)
    icon = Image.open(ICON).convert("RGBA").resize((48, 48), Image.Resampling.LANCZOS)
    canvas.alpha_composite(icon, (M, 47))
    draw.text((M + 60, 52), "LexiRead", font=f(SERIF_BOLD, 28), fill=INK)
    draw.text((M + 60, 85), "精读工坊", font=f(FONT, 13), fill=MUTED)
    draw.text((W - M - 2, 61), f"{page:02d} / {total:02d}", font=f(SERIF, 19), fill=MUTED, anchor="ra")
    draw.text((W - M - 2, 87), kicker, font=f(FONT, 13), fill=(154, 145, 128), anchor="ra")
    draw.line((M, 122, W - M, 122), fill=(*LINE, 255), width=1)


def footer(canvas: Image.Image, page: int, total: int = 8) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.line((M, 1330, W - M, 1330), fill=(*LINE, 255), width=1)
    draw.text((M, 1353), "Windows 10/11 · 本机 OCR · 免费非商业使用", font=f(FONT, 17), fill=(133, 126, 112))
    draw.text((W - M, 1353), f"LexiRead · {page:02d}/{total:02d}", font=f(FONT, 17), fill=(161, 151, 132), anchor="ra")


def kicker(draw: ImageDraw.ImageDraw, text: str, y: int = 170) -> None:
    draw.line((M, y + 11, M + 30, y + 11), fill=CORAL, width=2)
    draw.text((M + 42, y), text, font=f(FONT_BOLD, 18), fill=CORAL)


def title(draw: ImageDraw.ImageDraw, lines: list[str], y: int = 208, size: int = 64, color=INK) -> int:
    font = f(FONT_BOLD, size)
    for index, line in enumerate(lines):
        draw.text((M, y + index * int(size * 1.35)), line, font=font, fill=color)
    return y + len(lines) * int(size * 1.35)


def pill(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, *, fill=PAPER, fg=MUTED, border=LINE, size=18) -> int:
    font = f(FONT, size)
    width = text_width(draw, text, font) + 30
    draw.rounded_rectangle((x, y, x + width, y + 38), radius=19, fill=fill, outline=border, width=1)
    draw.text((x + 15, y + 8), text, font=font, fill=fg)
    return x + width


def shadow_panel(canvas: Image.Image, box: tuple[int, int, int, int], radius: int = 28, fill=PAPER, border=LINE) -> None:
    x1, y1, x2, y2 = box
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((x1 + 9, y1 + 14, x2 + 9, y2 + 14), radius=radius, fill=(32, 40, 31, 35))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas.alpha_composite(shadow)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=border, width=1)


def pasted_screenshot(
    canvas: Image.Image,
    source: Image.Image,
    crop: tuple[int, int, int, int] | None,
    box: tuple[int, int, int, int],
    radius: int = 18,
    border=True,
) -> None:
    src = source.crop(crop) if crop else source
    x1, y1, x2, y2 = box
    target = ImageOps.fit(src.convert("RGB"), (x2 - x1, y2 - y1), Image.Resampling.LANCZOS)
    target = target.convert("RGBA")
    mask = Image.new("L", target.size, 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, target.width, target.height), radius=radius, fill=255)
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sp = Image.new("RGBA", target.size, (0, 0, 0, 55))
    shadow.paste(sp, (x1 + 10, y1 + 16), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    canvas.alpha_composite(shadow)
    target.putalpha(mask)
    canvas.alpha_composite(target, (x1, y1))
    if border:
        ImageDraw.Draw(canvas).rounded_rectangle(box, radius=radius, outline=LINE, width=1)


def make_exam_paper() -> Image.Image:
    img = Image.new("RGB", (720, 1000), (255, 253, 247))
    draw = ImageDraw.Draw(img)
    draw.rectangle((25, 25, 695, 975), outline=(220, 211, 195), width=1)
    draw.text((58, 52), "READING COMPREHENSION", font=f(SERIF_BOLD, 25), fill=(34, 45, 37))
    draw.line((58, 92, 662, 92), fill=(205, 196, 180), width=1)
    draw.text((58, 112), "Read the passage and choose the best answer.", font=f(SERIF, 17), fill=(100, 107, 99))
    body = [
        "In a world that rewards speed, reading slowly",
        "can feel almost rebellious. We skim headlines,",
        "scroll through captions, and measure our progress",
        "by the number of books we finish. Yet a growing",
        "number of researchers argue that the most valuable",
        "reading is not fast or efficient at all. It is",
        "deliberate, unhurried, and willing to linger.",
        "",
        "Consider what happens when you read a difficult",
        "poem slowly. You notice how a single word echoes",
        "another, how a comma changes the rhythm, and how",
        "an image returns three lines later. These",
        "connections do not appear to the eye that races",
        "ahead. They emerge only when attention has time",
        "to settle.",
    ]
    y = 160
    for line in body:
        draw.text((58, y), line, font=f(SERIF, 19), fill=(35, 46, 39))
        y += 28
    y += 26
    draw.text((58, y), "1. What is the main idea of the passage?", font=f(SERIF_BOLD, 19), fill=(35, 46, 39))
    y += 36
    for option in [
        "A. Reading quickly is always less useful.",
        "B. Slow reading helps us understand more deeply.",
        "C. Researchers disagree about how many books to read.",
        "D. Literature should be read more often.",
    ]:
        draw.text((64, y), option, font=f(SERIF, 17), fill=(55, 65, 56))
        y += 28
    draw.text((560, 935), "示意图", font=f(FONT, 13), fill=(183, 173, 154))
    return img


def rotated_paper(canvas: Image.Image, paper: Image.Image, x: int, y: int, width: int, height: int) -> None:
    target = ImageOps.fit(paper.convert("RGB"), (width, height), Image.Resampling.LANCZOS).convert("RGBA")
    rotated = target.rotate(-5, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0))
    mask = rotated.split()[-1]
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shp = Image.new("RGBA", rotated.size, (0, 0, 0, 70))
    shadow.paste(shp, (x - 5, y + 18), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(17))
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(rotated, (x, y))


def slide_01() -> Image.Image:
    canvas = background()
    draw = ImageDraw.Draw(canvas)
    header(canvas, 1)
    kicker(draw, "ENGLISH READING · 精读工具")
    title(draw, ["把一张题图，", "读成一堂课。"], 208, 78)
    draw.rounded_rectangle((M, 432, M + 374, 440), radius=4, fill=(194, 94, 63, 120))
    draw.text((M, 464), "本机 OCR × 点词精读 × 生词复习", font=f(FONT_BOLD, 28), fill=GREEN_2)
    draw.text((M, 506), "Windows 10/11 · 免费非商业使用", font=f(FONT, 22), fill=MUTED)

    paper = make_exam_paper()
    rotated_paper(canvas, paper, 60, 720, 330, 460)
    reader = Image.open(READER).convert("RGB")
    pasted_screenshot(canvas, reader, (250, 160, 900, 760), (330, 590, 1010, 1150), radius=22)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((76, 675, 196, 711), radius=18, fill=(23, 63, 53, 238))
    draw.text((89, 682), "原始题图", font=f(FONT, 16), fill=(255, 250, 238))
    draw.rounded_rectangle((330, 556, 453, 592), radius=18, fill=(255, 253, 248, 245), outline=(226, 217, 201))
    draw.text((343, 563), "精读页", font=f(FONT_BOLD, 16), fill=GREEN)
    x = 72
    for label, color in [("本地 OCR", GREEN), ("点词学习", CORAL), ("生词复习", GOLD), ("AI 可选", MUTED)]:
        x = pill(draw, x, 1172, label, fill=(255, 253, 248, 230), fg=color, border=(225, 216, 200, 255), size=18) + 10
    draw.text((W - M, 1183), "源码公开", font=f(FONT_BOLD, 17), fill=CORAL, anchor="ra")
    footer(canvas, 1)
    return canvas.convert("RGB")


def slide_01_strong() -> Image.Image:
    canvas = background()
    draw = ImageDraw.Draw(canvas)
    header(canvas, 1)
    kicker(draw, "ENGLISH READING · 精读工具")
    title(draw, ["帮你提升", "英语阅读能力"], 208, 82)
    draw.rounded_rectangle((M, 440, M + 430, 448), radius=4, fill=(194, 94, 63, 120))
    draw.text((M, 474), "一张图读透一篇，点词就有解释", font=f(FONT_BOLD, 27), fill=GREEN_2)
    draw.text((M, 518), "Windows 10/11 · 免费非商业使用", font=f(FONT, 22), fill=MUTED)

    paper = make_exam_paper()
    rotated_paper(canvas, paper, 60, 720, 330, 460)
    reader = Image.open(READER).convert("RGB")
    pasted_screenshot(canvas, reader, (250, 160, 900, 760), (330, 590, 1010, 1150), radius=22)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((76, 675, 196, 711), radius=18, fill=(23, 63, 53, 238))
    draw.text((89, 682), "原始题图", font=f(FONT, 16), fill=(255, 250, 238))
    draw.rounded_rectangle((330, 556, 453, 592), radius=18, fill=(255, 253, 248, 245), outline=(226, 217, 201))
    draw.text((343, 563), "精读页", font=f(FONT_BOLD, 16), fill=GREEN)
    x = 72
    for label, color in [("本地 OCR", GREEN), ("点词学习", CORAL), ("生词复习", GOLD), ("AI 可选", MUTED)]:
        x = pill(draw, x, 1172, label, fill=(255, 253, 248, 230), fg=color, border=(225, 216, 200, 255), size=18) + 10
    draw.text((W - M, 1183), "源码公开", font=f(FONT_BOLD, 17), fill=CORAL, anchor="ra")
    footer(canvas, 1)
    return canvas.convert("RGB")


def slide_02() -> Image.Image:
    canvas = background()
    draw = ImageDraw.Draw(canvas)
    header(canvas, 2)
    kicker(draw, "01 / WHY I BUILT IT")
    title(draw, ["读一篇英语阅读，", "为什么要开三个窗口？"], 208, 60)
    draw_wrapped(draw, "文章、词典、题目被拆在不同地方，注意力也跟着碎了。", M, 390, f(FONT, 27), MUTED, 900, 44)
    items = [
        ("01", "查词要切窗口", "刚看到的意思，回文又忘了。"),
        ("02", "长难句没人拆", "每个词都认识，却拼不出句子结构。"),
        ("03", "生词收藏后不再看", "收藏夹越来越长，真正复习的没几个。"),
    ]
    y = 486
    for num, heading, body in items:
        shadow_panel(canvas, (M, y, W - M, y + 128), radius=18)
        draw = ImageDraw.Draw(canvas)
        draw.text((M + 28, y + 30), num, font=f(SERIF, 42), fill=(205, 194, 174))
        draw.text((M + 104, y + 27), heading, font=f(FONT_BOLD, 30), fill=INK)
        draw.text((M + 104, y + 73), body, font=f(FONT, 21), fill=MUTED)
        y += 146
    draw.line((M, 997, W - M, 997), fill=LINE, width=1)
    draw_wrapped(draw, "我想把「查词—做题—复习」\n放回同一个页面。", M, 1036, f(FONT_BOLD, 40), GREEN, 820, 61)
    footer(canvas, 2)
    return canvas.convert("RGB")


def slide_03() -> Image.Image:
    canvas = background()
    draw = ImageDraw.Draw(canvas)
    header(canvas, 3)
    kicker(draw, "02 / HOW IT WORKS")
    title(draw, ["拖进一张题图，", "先校对，再精读"], 208, 62)
    draw_wrapped(draw, "图片只在本机识别。识别错字可以直接改，确认后再进入精读。", M, 390, f(FONT, 26), MUTED, 900, 42)
    x = 72
    for label, color in [("01 上传题图", GREEN), ("02 校对 OCR", CORAL), ("03 进入精读", GOLD)]:
        x = pill(draw, x, 456, label, fill=(255, 253, 248, 235), fg=color, size=17) + 12
    reader = Image.open(READER).convert("RGB")
    pasted_screenshot(canvas, reader, (250, 85, 1015, 865), (M, 524, W - M, 1260), radius=23)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((100, 550, 410, 590), radius=20, fill=(23, 63, 53, 238))
    draw.text((117, 558), "阅读页 · 文章和题目在一张纸上", font=f(FONT_BOLD, 17), fill=(250, 246, 233))
    draw.text((M, 1284), "所有单词都可以点；题目和选项也自动拆开。", font=f(FONT, 22), fill=MUTED)
    footer(canvas, 3)
    return canvas.convert("RGB")


def slide_04() -> Image.Image:
    canvas = background()
    draw = ImageDraw.Draw(canvas)
    header(canvas, 4)
    kicker(draw, "03 / POINT A WORD")
    title(draw, ["点开一个词，", "不只看到中文意思"], 208, 62)
    draw_wrapped(draw, "音标、真人发音、中文释义、词形变化，\n还有它在原文里的那一句。", M, 390, f(FONT, 25), MUTED, 760, 41)
    word = Image.open(WORD_DRAWER).convert("RGB")
    pasted_screenshot(canvas, word, (888, 25, 1280, 790), (570, 510, 1008, 1288), radius=20)
    draw = ImageDraw.Draw(canvas)
    labels = [
        ("1", "音标 + 美音/英音", 610, 592),
        ("2", "原文语境", 730, 712),
        ("3", "中文释义 / 词形", 840, 822),
    ]
    for number, text, target_y, label_y in labels:
        draw.line((504, target_y, 552, target_y), fill=(194, 94, 63, 110), width=2)
        draw.ellipse((M + 8, label_y + 10, M + 24, label_y + 26), fill=CORAL)
        draw.text((M + 13, label_y + 9), number, font=f(SERIF_BOLD, 13), fill="white", anchor="ma")
        draw_wrapped(draw, text, M + 38, label_y, f(FONT_BOLD, 22), GREEN, 430, 33)
    draw.text((M, 1000), "离线词库收录 26,000 词条；\n本地没收录时再查 Wiktionary。", font=f(FONT, 21), fill=MUTED, spacing=12)
    draw.rounded_rectangle((M, 1160, 546, 1220), radius=14, fill=(232, 239, 231, 150), outline=(205, 221, 207, 255), width=1)
    draw.text((M + 18, 1177), "点击单词即可学习\n也可以直接加入生词本", font=f(FONT_BOLD, 18), fill=GREEN_2, spacing=6)
    footer(canvas, 4)
    return canvas.convert("RGB")


def slide_05() -> Image.Image:
    canvas = background()
    draw = ImageDraw.Draw(canvas)
    header(canvas, 5)
    kicker(draw, "04 / PRACTICE")
    title(draw, ["先自己选，", "再看原文线索"], 208, 62)
    draw_wrapped(draw, "本地模式不直接替你选答案；\n它先把定位词和相关原文句找出来。", M, 390, f(FONT, 25), MUTED, 760, 41)
    evidence = Image.open(EVIDENCE).convert("RGB")
    pasted_screenshot(canvas, evidence, (330, 230, 960, 880), (108, 500, 972, 1248), radius=24)
    draw = ImageDraw.Draw(canvas)
    draw.text((M, 1278), "配置 AI 后，才会生成参考答案和逐题依据。", font=f(FONT, 20), fill=(147, 137, 119))
    footer(canvas, 5)
    return canvas.convert("RGB")


def slide_06() -> Image.Image:
    canvas = background()
    draw = ImageDraw.Draw(canvas)
    header(canvas, 6)
    kicker(draw, "05 / REVIEW")
    title(draw, ["收藏不是终点，", "复习才是"], 208, 62)
    draw_wrapped(draw, "每个词都带着原文语境，复习时不只是一个孤立的中文释义。", M, 390, f(FONT, 25), MUTED, 850, 40)
    shadow_panel(canvas, (M, 500, W - M, 1200), radius=24)
    draw = ImageDraw.Draw(canvas)
    draw.text((M + 42, 538), "WORD REVIEW / 生词复习", font=f(FONT_BOLD, 17), fill=CORAL)
    draw.text((W - M - 42, 538), "复习卡片示意", font=f(FONT, 15), fill=(174, 164, 146), anchor="ra")
    draw.text((W // 2, 616), "deliberate", font=f(SERIF, 76), fill=INK, anchor="ma")
    draw.text((W // 2, 718), "/dɪˈlɪbərət/", font=f("C:/Windows/Fonts/segoeui.ttf", 25), fill=GREEN_2, anchor="ma")
    draw.rounded_rectangle((W // 2 - 116, 782, W // 2 + 116, 842), radius=12, fill=GREEN)
    draw.text((W // 2, 802), "显示释义", font=f(FONT_BOLD, 21), fill=(255, 250, 239), anchor="ma")
    draw.text((W // 2, 875), "“It is deliberate, unhurried, and willing to linger.”", font=f(SERIF, 20), fill=(100, 110, 101), anchor="ma")
    draw.line((M + 50, 934, W - M - 50, 934), fill=LINE, width=1)
    stats = [("ALL", "12"), ("学习中", "7"), ("已掌握", "5")]
    for index, (label, value) in enumerate(stats):
        cx = M + 190 + index * 355
        draw.text((cx, 975), value, font=f(SERIF_BOLD, 42), fill=GREEN, anchor="ma")
        draw.text((cx, 1030), label, font=f(FONT, 18), fill=MUTED, anchor="ma")
    draw.rounded_rectangle((M + 48, 1122, W - M - 48, 1172), radius=12, fill=(232, 239, 231, 150), outline=(205, 221, 207, 255), width=1)
    draw.text((W // 2, 1137), "本地 SQLite 保存 · 标记掌握 · 导出 CSV", font=f(FONT, 19), fill=GREEN_2, anchor="ma")
    footer(canvas, 6)
    return canvas.convert("RGB")


def slide_07() -> Image.Image:
    canvas = background()
    draw = ImageDraw.Draw(canvas)
    header(canvas, 7)
    kicker(draw, "06 / WHO IT IS FOR")
    title(draw, ["它适合谁？", "又不适合谁？"], 208, 62)
    # Fit card
    shadow_panel(canvas, (M, 420, 500, 1080), radius=22, fill=(241, 247, 239), border=(205, 221, 207))
    draw = ImageDraw.Draw(canvas)
    draw.text((M + 30, 452), "适合", font=f(FONT_BOLD, 34), fill=GREEN)
    draw.line((M + 30, 510, 470, 510), fill=(205, 221, 207), width=1)
    fits = [
        ("Windows 10/11 用户", "本机 OCR，不需要把题图传到云端"),
        ("考研 / 四六级 / 雅思托福", "阅读、完形都能排成精读页"),
        ("愿意先自己做题的人", "先看线索，再看解析，不直接抄答案"),
        ("愿意自己配 AI 的人", "AI 可选，不配置也能查词和复习"),
    ]
    y = 544
    for head, body in fits:
        draw.rounded_rectangle((M + 30, y + 1, M + 51, y + 22), radius=5, outline=(70, 139, 92), width=2)
        draw.line((M + 36, y + 11, M + 41, y + 16), fill=(70, 139, 92), width=2)
        draw.line((M + 41, y + 16, M + 48, y + 7), fill=(70, 139, 92), width=2)
        draw.text((M + 66, y + 1), head, font=f(FONT_BOLD, 21), fill=INK)
        draw_wrapped(draw, body, M + 66, y + 34, f(FONT, 18), MUTED, 330, 27, 2)
        y += 120
    # Not fit card
    shadow_panel(canvas, (566, 420, W - M, 1080), radius=22, fill=(251, 244, 239), border=(237, 216, 204))
    draw = ImageDraw.Draw(canvas)
    draw.text((596, 452), "可能不适合", font=f(FONT_BOLD, 34), fill=CORAL)
    draw.line((596, 510, 1008, 510), fill=(237, 216, 204), width=1)
    not_fits = [
        ("只用 iPad / 手机", "当前只有 Windows 版本"),
        ("想拍照直接得作业答案", "这是精读工具，不是搜题答案器"),
        ("期待保分 / 提分承诺", "我不做效果保证，只提供阅读工具"),
        ("现在就需要云同步", "当前是本地优先，账号和云同步还没做"),
    ]
    y = 544
    for head, body in not_fits:
        draw.rounded_rectangle((596, y + 1, 617, y + 22), radius=5, outline=(194, 94, 63), width=2)
        draw.line((602, y + 7, 611, y + 16), fill=CORAL, width=2)
        draw.line((611, y + 7, 602, y + 16), fill=CORAL, width=2)
        draw.text((632, y + 1), head, font=f(FONT_BOLD, 21), fill=INK)
        draw_wrapped(draw, body, 632, y + 34, f(FONT, 18), MUTED, 330, 27, 2)
        y += 120
    draw_wrapped(draw, "AI 不是必选项；不配置 Key，也能用本地 OCR、离线词典、生词本。", M, 1120, f(FONT, 20), MUTED, 900, 32)
    draw_wrapped(draw, "源码公开 · 免费非商业使用 · 商业使用需单独授权", M, 1190, f(FONT_BOLD, 20), CORAL, 900, 32)
    footer(canvas, 7)
    return canvas.convert("RGB")


def slide_08() -> Image.Image:
    canvas = background()
    draw = ImageDraw.Draw(canvas)
    header(canvas, 8)
    kicker(draw, "07 / TRY IT")
    draw.text((M, 200), "LexiRead", font=f(SERIF_BOLD, 76), fill=INK)
    draw.text((M, 290), "英语精读工坊", font=f(FONT_BOLD, 32), fill=GREEN)
    draw.text((M, 354), "把一张题图，读成一堂课。", font=f(FONT, 28), fill=MUTED)
    x = 72
    for label in ["本地 OCR", "点词学习", "生词复习", "AI 可选"]:
        x = pill(draw, x, 438, label, fill=(255, 253, 248, 240), fg=GREEN_2, size=18) + 10
    shadow_panel(canvas, (M, 548, W - M, 880), radius=22, fill=(23, 63, 53), border=(23, 63, 53))
    draw = ImageDraw.Draw(canvas)
    draw.text((M + 38, 580), "GITHUB", font=f(FONT_BOLD, 16), fill=(181, 205, 188))
    draw.text((M + 38, 622), "sonic111222 / lexiread", font=f("C:/Windows/Fonts/consola.ttf", 29), fill=(250, 246, 233))
    draw.text((M + 38, 690), "Windows 10/11 · 源码公开 · 免费非商业使用", font=f(FONT, 19), fill=(183, 205, 188))
    draw.line((M + 38, 738, W - M - 38, 738), fill=(74, 111, 92), width=1)
    draw.text((M + 38, 763), "AI 需要自己的 Key；不配置也能使用本地功能。", font=f(FONT, 18), fill=(174, 198, 180))
    draw.text((M, 948), "最近在练什么题？", font=f(FONT_BOLD, 46), fill=GREEN)
    draw.text((M, 1018), "评论区告诉我，我按题型继续改。", font=f(FONT, 27), fill=MUTED)
    draw.text((M, 1114), "如果你想先看适不适合自己：", font=f(FONT, 20), fill=MUTED)
    draw.text((M, 1154), "GitHub 搜「LexiRead」或「sonic111222」", font=f(FONT_BOLD, 22), fill=CORAL)
    draw.line((M, 1235, W - M, 1235), fill=LINE, width=1)
    draw.text((M, 1260), "无账号 · 无广告 · 本地优先", font=f(FONT, 20), fill=(137, 129, 114))
    draw.text((W - M, 1260), "v0.1.0", font=f(SERIF, 20), fill=(137, 129, 114), anchor="ra")
    footer(canvas, 8)
    return canvas.convert("RGB")


def main() -> None:
    poetic = slide_01()
    poetic.save(OUT / "01-cover-poetic.png", "PNG", optimize=True)
    slides = [
        ("01-cover", slide_01_strong),
        ("02-why", slide_02),
        ("03-flow", slide_03),
        ("04-word", slide_04),
        ("05-question", slide_05),
        ("06-review", slide_06),
        ("07-fit", slide_07),
        ("08-download", slide_08),
    ]
    for name, fn in slides:
        image = fn()
        path = OUT / f"{name}.png"
        image.save(path, "PNG", optimize=True)
        print(path, image.size)
    # Contact sheet for quick visual review.
    thumb_w, thumb_h = 270, 360
    sheet = Image.new("RGB", (thumb_w * 4 + 50, thumb_h * 2 + 50), (238, 232, 221))
    for i, (name, _) in enumerate(slides):
        im = Image.open(OUT / f"{name}.png").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        x = 10 + (i % 4) * (thumb_w + 10)
        y = 10 + (i // 4) * (thumb_h + 10)
        sheet.paste(im, (x, y))
    sheet.save(OUT / "contact-sheet.png", "PNG", optimize=True)
    print(OUT / "contact-sheet.png")


if __name__ == "__main__":
    main()
