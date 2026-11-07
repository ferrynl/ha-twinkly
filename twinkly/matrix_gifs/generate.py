"""Build original animated LED-matrix previews for the bundled gallery."""
import colorsys
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

COLUMNS, ROWS, SIZE, FRAMES = 12, 10, 96, 24
THEMES = {
    "winter": ("Winter", ((16, 38, 98), (85, 196, 255), (239, 249, 255))),
    "festive": ("Christmas", ((185, 12, 39), (25, 179, 91), (255, 236, 172))),
    "neon": ("Neon", ((83, 21, 191), (250, 26, 179), (20, 232, 235))),
    "ocean": ("Ocean", ((8, 38, 115), (13, 154, 188), (128, 255, 207))),
    "gold": ("Gold", ((88, 26, 13), (228, 109, 27), (255, 235, 152))),
}
EFFECTS = (
    "Snowfall", "Rainbow", "Snake", "Twinkle", "Fireworks",
    "Diagonal", "Sparkles", "Horizontal flag", "Vertical flag", "Scanner",
)


def color_for(effect, x, y, step, palette, theme_index):
    phase = step / FRAMES
    seed = (x * 197 + y * 83 + theme_index * 47) % 127
    dark = (2, 3, 7)
    if effect == 0:
        return palette[2] if (seed + step * 5) % 53 < 4 else palette[0] if y > 7 else dark
    if effect == 1:
        hue = (y / ROWS + phase + theme_index / len(THEMES)) % 1
        return tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(hue, 0.9, 0.93))
    if effect == 2:
        index = y * COLUMNS + (x if y % 2 == 0 else COLUMNS - 1 - x)
        distance = (step * 5 - index) % (ROWS * COLUMNS)
        return palette[2 - min(2, distance // 5)] if distance < 15 else dark
    if effect == 3:
        return palette[1 + seed % 2] if (seed + step * 3) % 37 < 4 else dark
    if effect == 4:
        radius = (step % 12) * 0.65
        center_x = 4 if step < 12 else 8
        distance = math.hypot(x - center_x, y - 4)
        return palette[(x + y) % 3] if abs(distance - radius) < 0.75 else dark
    if effect == 5:
        return palette[2 if ((x + y - step) // 2) % 2 else 0]
    if effect == 6:
        return palette[2] if (seed * 3 + step * 7) % 67 < 5 else palette[0]
    if effect == 7:
        shift = round(math.sin(phase * math.tau + x * 0.45))
        return palette[((y + shift) % ROWS) * 3 // ROWS]
    if effect == 8:
        shift = round(math.sin(phase * math.tau + y * 0.45))
        return palette[((x + shift) % COLUMNS) * 3 // COLUMNS]
    center = (1 - abs(2 * phase - 1)) * (COLUMNS - 1)
    distance = abs(x - center)
    return palette[2] if distance < 0.55 else palette[1] if distance < 1.7 else palette[0] if distance < 3 else dark


def draw_frame(effect, step, palette, theme_index):
    image = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    for y in range(ROWS):
        for x in range(COLUMNS):
            draw.rectangle((x * SIZE // COLUMNS + 1, y * SIZE // ROWS + 1,
                            (x + 1) * SIZE // COLUMNS - 1, (y + 1) * SIZE // ROWS - 1),
                           fill=color_for(effect, x, y, step, palette, theme_index))
    return image.quantize(colors=128)


def main():
    root = Path(__file__).parent
    catalog = []
    for theme_index, (theme, (label, palette)) in enumerate(THEMES.items()):
        for index, effect in enumerate(EFFECTS):
            key = f"{theme}-{index + 1}"
            images = [draw_frame(index, step, palette, theme_index) for step in range(FRAMES)]
            images[0].save(root / (key + ".gif"), save_all=True, append_images=images[1:],
                           duration=100, loop=0, disposal=2)
            catalog.append({"id": key, "name": f"{label} {effect}", "theme": theme})
    (root / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")


if __name__ == "__main__":
    main()
