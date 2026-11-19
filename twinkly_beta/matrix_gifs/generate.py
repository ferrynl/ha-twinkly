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
    "cosmic": ("Cosmic", ((17, 9, 63), (116, 54, 238), (128, 240, 255))),
    "tropical": ("Tropical", ((8, 69, 41), (250, 83, 85), (255, 220, 92))),
    "retro": ("Retro", ((21, 12, 70), (255, 42, 145), (25, 219, 255))),
    "pastel": ("Pastel", ((72, 52, 104), (243, 150, 201), (170, 243, 225))),
    "midnight": ("Midnight", ((8, 16, 40), (24, 95, 206), (209, 222, 255))),
}
EFFECTS = (
    "Snowfall", "Rainbow", "Snake", "Twinkle", "Fireworks",
    "Diagonal", "Sparkles", "Horizontal flag", "Vertical flag", "Scanner",
)

NEW_EFFECTS = (
    "Spiral", "Comets", "Ripple", "Checker flow", "Pixel rain",
    "Diamond sweep", "Orbit", "Equalizer", "Cross sweep", "Pixel tide",
)


def color_for(effect, x, y, step, palette, theme_index):
    phase = step / FRAMES
    seed = (x * 197 + y * 83 + theme_index * 47) % 127
    dark = (2, 3, 7)
    if effect == 0:
        return palette[2] if (seed + step * 5) % 53 < 4 else palette[0] if y > 7 else dark
    if effect == 1:
        hue = (y / ROWS + phase + theme_index / 5) % 1
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
    if effect >= len(EFFECTS):
        return alternate_color(effect - len(EFFECTS), x, y, step, palette, dark)
    center = (1 - abs(2 * phase - 1)) * (COLUMNS - 1)
    distance = abs(x - center)
    return palette[2] if distance < 0.55 else palette[1] if distance < 1.7 else palette[0] if distance < 3 else dark


def alternate_color(effect, x, y, step, palette, dark):
    phase = step / FRAMES
    angle = phase * math.tau
    dx, dy = x - (COLUMNS - 1) / 2, y - (ROWS - 1) / 2
    radius = math.hypot(dx, dy)
    if effect == 0:
        arm = (math.atan2(dy, dx) / math.tau + radius * 0.14 - phase) % 1
        return palette[2] if arm < 0.12 else palette[1] if arm < 0.25 else dark
    if effect == 1:
        tail = (step - x * 2 - y * 7) % FRAMES
        return palette[2 - tail // 2] if tail < 6 else dark
    if effect == 2:
        band = (radius - phase * 6) % 3
        return palette[2] if band < 0.4 else palette[1] if band < 0.9 else palette[0]
    if effect == 3:
        return palette[((x // 2) + (y // 2) + step // 3) % 3]
    if effect == 4:
        tail = (step - y * 2 + x * 11) % FRAMES
        return palette[2 - tail // 3] if tail < 9 else dark
    if effect == 5:
        sweep = abs((abs(dx) + abs(dy)) - 10 * (1 - abs(2 * phase - 1)))
        return palette[2] if sweep < 0.5 else palette[1] if sweep < 1.5 else dark
    if effect == 6:
        distance = min(math.hypot(dx - direction * math.cos(angle) * 4,
                                  dy - direction * math.sin(angle) * 3)
                       for direction in (-1, 1))
        return palette[2] if distance < 0.8 else palette[1] if distance < 1.7 else palette[0]
    if effect == 7:
        height = 2 + round(7 * (0.5 + 0.5 * math.sin(angle * (1 + x % 3) + x * 1.7)))
        level = ROWS - y
        return palette[min(2, (level - 1) // 3)] if level <= height else dark
    if effect == 8:
        distance = min(abs(dx - 5 * math.sin(angle)), abs(dy - 4 * math.cos(angle)))
        return palette[2] if distance < 0.55 else palette[1] if distance < 1.25 else dark
    height = 4.5 + 2 * math.sin(x * 0.58 + angle) + math.sin(x * 1.03 - angle)
    return palette[2] if abs(y - height) < 0.6 else palette[1] if y > height else palette[0]


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
        effects = EFFECTS if theme_index < 5 else NEW_EFFECTS
        offset = 0 if theme_index < 5 else len(EFFECTS)
        for index, effect in enumerate(effects):
            key = f"{theme}-{index + 1}"
            images = [draw_frame(index + offset, step, palette, theme_index) for step in range(FRAMES)]
            images[0].save(root / (key + ".gif"), save_all=True, append_images=images[1:],
                           duration=100, loop=0, disposal=2)
            catalog.append({"id": key, "name": f"{label} {effect}", "theme": theme})
    (root / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")


if __name__ == "__main__":
    main()
