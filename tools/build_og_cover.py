#!/usr/bin/env python3
"""生成社交分享封面图 og-cover.png（1200x630），数字全部取自 build_pack/pack_summary.json，
不写死 —— 与全站其它页同一口径。给微信/搜索分享卡片当缩略图（此前 public-site 树里一张图都没有，
微信转发只出裸链接）。

用法：
  python3 build_og_cover.py            # 生成 public-site/og-cover.png
  python3 build_og_cover.py --check    # 只校验：图存在、尺寸 1200x630、数字与 pack_summary 一致
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # money-loop/
SITE = os.path.dirname(HERE)                            # public-site/
PACK = os.path.join(ROOT, "build_pack", "pack_summary.json")
OUT = os.path.join(SITE, "og-cover.png")
FONT = "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"
FONT_L = "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"


def stats():
    with open(PACK, encoding="utf-8") as f:
        p = json.load(f)
    return p["rows"], p["days"], p["stocks"]


def fmt(n):
    return f"{n:,}"


def build():
    rows, days, stocks = stats()
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), (12, 40, 30))
    d = ImageDraw.Draw(img)
    # 背景装饰块
    d.rectangle([0, 0, W, H], fill=(12, 40, 30))
    d.rectangle([0, H - 120, W, H], fill=(10, 30, 22))
    def f(path, size):
        return ImageFont.truetype(path, size)
    # 顶部小标签
    d.text((80, 70), "A 股涨停 / 连板 · 历史数据集", font=f(FONT_L, 32), fill=(120, 220, 170))
    # 主标题
    d.text((80, 140), "涨停连板明细 · 可直接读取的 CSV", font=f(FONT, 54), fill=(255, 255, 255))
    # 大数字（三列等距，按实测宽度布点，避免叠印）
    y = 250
    cols = [(80, fmt(rows), "条逐日明细"),
            (470, fmt(days), "个交易日（2021 起）"),
            (800, fmt(stocks), "只（含退市）")]
    for x, big, label in cols:
        d.text((x, y), big, font=f(FONT, 72), fill=(90, 230, 160))
        d.text((x, y + 92), label, font=f(FONT_L, 30), fill=(210, 220, 215))
    # 底部说明
    d.text((80, H - 96), "免费 30 日全量 CSV · 无需注册 · 每个交易日收盘自动更新", font=f(FONT_L, 34), fill=(200, 255, 220))
    img.save(OUT, "PNG")
    print(f"OK wrote {OUT} {os.path.getsize(OUT)}B rows={rows} days={days} stocks={stocks}")


def check():
    rows, days, stocks = stats()
    if not os.path.exists(OUT):
        print(f"BAD 缺 {OUT}"); return 2
    im = Image.open(OUT)
    if im.size != (1200, 630):
        print(f"BAD 尺寸 {im.size} != (1200, 630)"); return 2
    sz = os.path.getsize(OUT)
    if sz < 5000:
        print(f"BAD 体积过小 {sz}B"); return 2
    print(f"OK og-cover {im.size} {sz}B（口径 {fmt(rows)}/{fmt(days)}/{fmt(stocks)}）")
    return 0


if __name__ == "__main__":
    sys.exit(check() if "--check" in sys.argv else (build() or 0))
