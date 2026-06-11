"""Render the phantom_ video advertisement.

18 seconds, 1280x720, 24fps. Ken Burns drifts over the HD atmosphere
photography with the brand's quiet typography. Run once:

    python make_ad.py
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

W, H, FPS = 1280, 720, 24


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


MONO_XL = font("C:/Windows/Fonts/consola.ttf", 110)
MONO_MD = font("C:/Windows/Fonts/consola.ttf", 30)
MONO_SM = font("C:/Windows/Fonts/consola.ttf", 20)
DISP_LG = font("C:/Windows/Fonts/segoeuib.ttf", 84)
DISP_MD = font("C:/Windows/Fonts/segoeuib.ttf", 46)


def load(name, brightness=0.85):
    img = Image.open(f"static/img/web/{name}.jpg").convert("L").convert("RGB")
    img = ImageEnhance.Brightness(img).enhance(brightness)
    # cover-fit to a canvas 15% larger than the frame so we can drift
    scale = max(W * 1.18 / img.width, H * 1.18 / img.height)
    return img.resize((int(img.width * scale), int(img.height * scale)))


def ken_burns(img, t, zoom_from=1.0, zoom_to=1.1, dx=0.0, dy=0.0):
    """t in [0,1] — crop a drifting, zooming window and return a WxH frame."""
    z = zoom_from + (zoom_to - zoom_from) * t
    cw, ch = int(W / z * 1.0), int(H / z * 1.0)
    max_x, max_y = img.width - cw, img.height - ch
    x = int(max_x * (0.5 + dx * (t - 0.5)))
    y = int(max_y * (0.5 + dy * (t - 0.5)))
    x, y = max(0, min(x, max_x)), max(0, min(y, max_y))
    return img.crop((x, y, x + cw, y + ch)).resize((W, H), Image.BILINEAR)


def center(d, text, y, f, fill):
    tw = d.textlength(text, font=f)
    d.text(((W - tw) // 2, y), text, font=f, fill=fill)


def vignette():
    g = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(g)
    gd.rectangle([0, 0, W, int(H * 0.2)], fill=90)
    gd.rectangle([0, int(H * 0.75), W, H], fill=130)
    return g.filter_args if False else g


VIG = Image.new("L", (W, H), 0)
_vd = ImageDraw.Draw(VIG)
for i in range(160):
    _vd.rectangle([0, i, W, i + 1], fill=int(120 * (1 - i / 160)))
    _vd.rectangle([0, H - i - 1, W, H - i], fill=int(150 * (1 - i / 160)))
BLACK = Image.new("RGB", (W, H), (5, 5, 6))

rng = np.random.default_rng(7)


def grain(frame):
    arr = np.asarray(frame, dtype=np.int16)
    noise = rng.integers(-4, 5, size=(H, W, 1), dtype=np.int16)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


def fade(alpha_t):
    """ease in/out alpha for text: fade in first 20%, out last 20%."""
    if alpha_t < 0.2:
        return alpha_t / 0.2
    if alpha_t > 0.8:
        return max(0.0, (1 - alpha_t) / 0.2)
    return 1.0


def text_layer(draw_fn, alpha):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    if alpha < 1.0:
        a = layer.getchannel("A").point(lambda p: int(p * alpha))
        layer.putalpha(a)
    return layer


SCENES = [
    # (image, seconds, headline draw fn)
    ("moon", 4.0, lambda d: (
        center(d, "phantom_", 295, MONO_XL, (255, 255, 255, 255)),
        center(d, "A QUIET PLACE TO TALK", 445, MONO_SM, (185, 185, 190, 255)))),
    ("stars", 3.5, lambda d: (
        center(d, "Fast.", 280, DISP_LG, (255, 255, 255, 255)),
        center(d, "Instant launch. Real-time delivery.", 400, MONO_MD, (200, 200, 205, 255)))),
    ("ridge", 3.5, lambda d: (
        center(d, "Private.", 280, DISP_LG, (255, 255, 255, 255)),
        center(d, "End-to-end encrypted. Zero trackers.", 400, MONO_MD, (200, 200, 205, 255)))),
    ("valley", 3.5, lambda d: (
        center(d, "Lightweight.", 280, DISP_LG, (255, 255, 255, 255)),
        center(d, "No clutter. No noise. No feeds.", 400, MONO_MD, (200, 200, 205, 255)))),
    (None, 3.5, lambda d: (
        center(d, "Private conversations.", 250, DISP_MD, (255, 255, 255, 255)),
        center(d, "Nothing else.", 315, DISP_MD, (255, 255, 255, 255)),
        center(d, "phantom.chat", 460, MONO_MD, (170, 170, 176, 255)))),
]

XFADE = 0.6  # seconds of crossfade between scenes


def scene_frame(idx, t):
    """Render scene idx at progress t in [0,1] — background + text + cube."""
    name, dur, draw_fn = SCENES[idx]
    if name:
        bg = ken_burns(IMAGES[name], t, 1.0, 1.12, dx=0.3 if idx % 2 else -0.3, dy=0.12)
        bg = Image.composite(BLACK, bg, VIG)
    else:
        bg = BLACK.copy()
        # end card: the frosted cube
        s = 46
        cube = Image.new("RGBA", (s * 3, s * 3), (0, 0, 0, 0))
        cd = ImageDraw.Draw(cube)
        cd.rounded_rectangle([s, s, s * 2, s * 2], 10, fill=(255, 255, 255, 30),
                             outline=(255, 255, 255, 130), width=3)
        cube = cube.rotate(45 + t * 18, expand=False, resample=Image.BICUBIC)
        bg.paste(cube, (W // 2 - s * 3 // 2, 96), cube)
    layer = text_layer(draw_fn, fade(t))
    bg = bg.convert("RGBA")
    bg.alpha_composite(layer)
    return bg.convert("RGB")


print("loading HD plates…")
IMAGES = {name: load(name) for name, _, _ in SCENES if name}

import imageio.v2 as imageio

writer = imageio.get_writer(
    "static/video/phantom-ad.mp4", fps=FPS, codec="libx264",
    bitrate="2200k", pixelformat="yuv420p", macro_block_size=16,
)

total_scenes = len(SCENES)
print("rendering…")
for idx, (name, dur, _) in enumerate(SCENES):
    frames = int(dur * FPS)
    for f in range(frames):
        t = f / frames
        frame = scene_frame(idx, t)
        # crossfade into the next scene over the final XFADE seconds
        remaining = dur * (1 - t)
        if remaining < XFADE and idx + 1 < total_scenes:
            nxt = scene_frame(idx + 1, 0.0)
            frame = Image.blend(frame, nxt, 1 - remaining / XFADE)
        writer.append_data(np.asarray(grain(frame)))
    print(f"  scene {idx + 1}/{total_scenes} done")

writer.close()
print("phantom-ad.mp4 written")
