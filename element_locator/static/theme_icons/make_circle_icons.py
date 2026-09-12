# -*- coding: utf-8 -*-
"""把豆包生成的日/月方图处理成圆形透明 PNG：
1. 沿中心行/列扫描，定位圆角卡片（非背景）包围盒
2. 取卡片内切圆（略内缩，避开圆角/描边/棋盘格）
3. 4x 超采样圆形蒙版抗锯齿，输出指定尺寸透明 PNG
"""
import sys
from PIL import Image, ImageDraw


def tile_bounds(im):
    """沿中心行/列扫描，找卡片的左右上下边界。背景=棋盘格/白色（亮且低饱和）。"""
    w, h = im.size
    px = im.load()
    cy, cx = h // 2, w // 2

    def is_bg(p):
        r, g, b = p[:3]
        return min(r, g, b) > 200 and (max(r, g, b) - min(r, g, b)) < 28

    def scan(fixed, axis):
        first = last = None
        n = w if axis == 'x' else h
        for i in range(n):
            p = px[i, fixed] if axis == 'x' else px[fixed, i]
            if not is_bg(p):
                if first is None:
                    first = i
                last = i
        return first, last

    x1, x2 = scan(cy, 'x')
    y1, y2 = scan(cx, 'y')
    return x1, y1, x2, y2


def process(src, out, size=256, inset=10):
    im = Image.open(src).convert('RGB')
    x1, y1, x2, y2 = tile_bounds(im)
    side = min(x2 - x1, y2 - y1) - inset * 2
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    box = (cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side)
    tile = im.crop(box)

    # 4x 超采样圆形蒙版 → 缩小得到抗锯齿圆边
    big = side * 4
    mask = Image.new('L', (big, big), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, big - 1, big - 1), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)

    tile = tile.resize((size, size), Image.LANCZOS).convert('RGBA')
    tile.putalpha(mask)
    tile.save(out)
    print('%s: 卡片边界=%s 内切圆边长=%d → %s (%dx%d RGBA)' % (src.split("/")[-1], (x1, y1, x2, y2), side, out, size, size))


if __name__ == '__main__':
    base = 'element_locator/static/theme_icons/'
    process(base + 'src/sun_src.jpg', base + 'theme_sun.png')
    process(base + 'src/moon_src.jpg', base + 'theme_moon.png')
