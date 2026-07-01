"""Sinh icon brand cho custom component nchmf (Vietnam Weather).

Vẽ bằng Pillow ở độ phân giải cao (supersampling) + gradient + đổ bóng mềm,
rồi thu nhỏ cho cạnh mượt. Xuất (HA >= 2026.3 nhúng icon trực tiếp trong component):
  custom_components/nchmf/brand/icon.png     (256)
  custom_components/nchmf/brand/icon@2x.png  (512)

Chạy:  python scripts/make_icon.py   (cần Pillow)

Thiết kế: mặt trời vàng cam (gradient toả tròn) + tia nắng vàng,
mây xanh có gradient + bóng đổ, hạt mưa bóng loáng.
Đọc rõ trên nền sáng lẫn tối.
"""
from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFilter

S = 1024  # canvas gốc (vẽ lớn rồi thu nhỏ)

# --- Bảng màu ---
SUN_IN = (255, 208, 74)      # vàng sáng ấm (tâm đĩa)
SUN_OUT = (247, 162, 22)     # cam nắng (rìa đĩa)
SUN_RING = (228, 144, 8)     # viền đĩa vàng đậm
RAY = (250, 176, 30)         # tia nắng vàng cam
CLOUD_TOP = (124, 160, 210)  # xanh mây nhạt (trên)
CLOUD_BOT = (58, 92, 146)    # xanh mây đậm (dưới)
CLOUD_HI = (168, 197, 232)   # highlight mép trên mây
SHADOW = (26, 48, 84)        # bóng mây
RAIN_TOP = (120, 206, 240)   # xanh mưa sáng
RAIN_BOT = (44, 150, 210)    # xanh mưa đậm

# --- Hình học mây (toạ độ theo tỉ lệ canvas) ---
CLOUD_PUFFS = [(0.36, 0.50, 0.10), (0.50, 0.45, 0.128), (0.64, 0.50, 0.102)]
CLOUD_BASE = (0.24, 0.52, 0.80, 0.66)  # x0, y0, x1, y1


def _rounded_line(draw, p0, p1, width, fill):
    draw.line([p0, p1], fill=fill, width=width)
    r = width // 2
    for (x, y) in (p0, p1):
        draw.ellipse([x - r, y - r, x + r, y + r], fill=fill)


def _vgrad(size, top, bottom):
    """Gradient dọc (dựng cột 1px rồi kéo giãn — nhanh)."""
    w, h = size
    col = Image.new("RGBA", (1, h))
    cp = col.load()
    for y in range(h):
        t = y / max(1, h - 1)
        cp[0, y] = (
            round(top[0] + (bottom[0] - top[0]) * t),
            round(top[1] + (bottom[1] - top[1]) * t),
            round(top[2] + (bottom[2] - top[2]) * t),
            255,
        )
    return col.resize((w, h))


def _radial(diam, inner, outer, cx=0.42, cy=0.40, scale=1.08):
    """Gradient toả tròn, tâm sáng lệch trên-trái cho có khối."""
    g = Image.new("RGBA", (diam, diam), (0, 0, 0, 0))
    p = g.load()
    ox, oy, maxr = cx * diam, cy * diam, (diam / 2) * scale
    for yy in range(diam):
        for xx in range(diam):
            t = min(1.0, math.hypot(xx - ox, yy - oy) / maxr)
            p[xx, yy] = (
                round(inner[0] + (outer[0] - inner[0]) * t),
                round(inner[1] + (outer[1] - inner[1]) * t),
                round(inner[2] + (outer[2] - inner[2]) * t),
                255,
            )
    return g


def _fill(img, mask, paint):
    """Tô `paint` (RGBA full canvas) vào vùng `mask` (L) của img."""
    img.paste(paint, (0, 0), mask)


def _cloud_mask(dy: float = 0.0) -> Image.Image:
    """Mặt nạ hình mây (L, full canvas), dịch dọc dy (tỉ lệ)."""
    m = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(m)
    off = int(dy * S)
    for px, py, pr in CLOUD_PUFFS:
        x, y, r = int(px * S), int(py * S) + off, int(pr * S)
        md.ellipse([x - r, y - r, x + r, y + r], fill=255)
    x0, y0, x1, y1 = CLOUD_BASE
    md.rounded_rectangle(
        [int(x0 * S), int(y0 * S) + off, int(x1 * S), int(y1 * S) + off],
        radius=int((y1 - y0) * S / 2),
        fill=255,
    )
    return m


def draw_icon() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ---- Bóng đổ mềm dưới mây ----
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow.paste((*SHADOW, 115), (0, 0), _cloud_mask(dy=0.028))
    shadow = shadow.filter(ImageFilter.GaussianBlur(int(S * 0.022)))
    img.alpha_composite(shadow)

    # ---- Mặt trời: tia + đĩa đỏ gradient + viền ----
    cx, cy, r = int(S * 0.36), int(S * 0.335), int(S * 0.155)
    r1, r2 = int(r * 1.28), int(r * 1.74)
    for k in range(8):
        a = math.radians(k * 45)
        p0 = (cx + r1 * math.cos(a), cy + r1 * math.sin(a))
        p1 = (cx + r2 * math.cos(a), cy + r2 * math.sin(a))
        _rounded_line(d, p0, p1, int(r * 0.20), RAY)

    disc = Image.new("L", (S, S), 0)
    ImageDraw.Draw(disc).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    paint = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    paint.paste(_radial(2 * r, SUN_IN, SUN_OUT), (cx - r, cy - r))
    _fill(img, disc, paint)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=SUN_RING,
              width=int(S * 0.007))

    # ---- Mây: gradient dọc + highlight mép trên ----
    _fill(img, _cloud_mask(), _vgrad((S, S), CLOUD_TOP, CLOUD_BOT))
    # highlight: vành sáng mỏng ôm mép trên các cụm mây
    hi = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hi)
    for px, py, pr in CLOUD_PUFFS:
        x, y, rr = int(px * S), int(py * S), int(pr * S)
        hd.arc([x - rr, y - rr, x + rr, y + rr], 200, 340,
               fill=(*CLOUD_HI, 235), width=int(S * 0.012))
    hi = hi.filter(ImageFilter.GaussianBlur(int(S * 0.004)))
    hi.putalpha(hi.getchannel("A").point(lambda v: int(v * 0.8)))
    img.alpha_composite(Image.composite(hi, Image.new("RGBA", (S, S)),
                                        _cloud_mask()))

    # ---- Hạt mưa bóng loáng (gradient) ----
    rain = Image.new("L", (S, S), 0)
    rd = ImageDraw.Draw(rain)
    for i, fx in enumerate((0.38, 0.50, 0.62)):
        x = int(S * fx)
        y0 = int(S * (0.715 + (0.018 if i == 1 else 0)))
        y1 = y0 + int(S * 0.098)
        _rounded_line(rd, (x + int(S * 0.02), y0), (x, y1),
                      int(S * 0.030), 255)
    _fill(img, rain, _vgrad((S, S), RAIN_TOP, RAIN_BOT))

    return img


def _trim_square(img: Image.Image, pad_ratio: float = 0.05) -> Image.Image:
    bbox = img.getbbox()
    content = img.crop(bbox)
    side = int(max(content.size) * (1 + 2 * pad_ratio))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(
        content,
        ((side - content.width) // 2, (side - content.height) // 2),
        content,
    )
    return canvas


def main() -> None:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(here, "custom_components", "nchmf", "brand")
    os.makedirs(out_dir, exist_ok=True)

    master = _trim_square(draw_icon())
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        master.resize((size, size), Image.LANCZOS).save(
            os.path.join(out_dir, name)
        )
        print("wrote", os.path.join(out_dir, name))


if __name__ == "__main__":
    main()
