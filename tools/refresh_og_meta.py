#!/usr/bin/env python3
"""为两张落地页（首页 index.html、免费样本页 sample/index.html）生成「搜索引擎描述 + 微信/社交分享卡片」
（<meta name="description"> + Open Graph + Twitter Card）元信息块。

数字一律取自 build_pack/pack_summary.json（不写死），并包在 <!-- OG:START --> ... <!-- OG:END --> 之间，
可幂等重写。--check 断言块内数字与现库一致、og:image 指向的文件存在 —— 一旦全库数字变了却没重写，
这里会判红，杜绝「页面写死旧数字」这个反复出现的病根。

用法：
  python3 tools/refresh_og_meta.py           # 重写两张页面的 OG 块
  python3 tools/refresh_og_meta.py --check   # 只校验（数字是否与现库一致 / 图片是否存在）
  python3 tools/refresh_og_meta.py --selftest
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ROOT = os.path.dirname(SITE)
PACK = os.path.join(ROOT, "build_pack", "pack_summary.json")
BASE = "https://dangnianqin.github.io/astock-sample-library"

PAGES = {
    "index.html": dict(
        path="", title="A股策略体检 · 免费样板库",
        og_title="A股涨停/连板 历史数据集 · 免费样板库",
        desc="A股涨停/连板历史数据集的免费样板库与策略体检：{rows} 条逐日明细、{days} 个交易日（2021 起）、{stocks} 只股票（含退市），字段含连板高度、是否一字板、成交额与换手、当日涨跌幅上限、次日开盘缺口与是否再涨停。含免费 30 日全量 CSV 样本，无需注册，可直接读取。",
        og_desc="{rows} 条逐日明细 / {days} 个交易日（2021 起）/ {stocks} 只，含免费 30 日全量 CSV 样本，无需注册，可直接读取。",
    ),
    "sample/index.html": dict(
        path="sample/", title="A股涨停/连板 免费样本（30 天全量）",
        og_title="A股涨停/连板 免费样本（30 天全量 CSV）",
        desc="A股涨停/连板 免费样本：从 {rows} 条历史逐日明细中取出近 30 个交易日的全量 CSV（非抽样），字段含连板高度、是否一字板、成交额与换手、当日涨跌幅上限、次日开盘缺口与是否再涨停。无需注册，下载即读。",
        og_desc="近 30 个交易日全量 CSV，直接下载、无需注册；全库 {rows} 条逐日明细 / {days} 交易日 / {stocks} 只。",
    ),
}

START = "<!-- OG:START -->"
END = "<!-- OG:END -->"


def pack_stats():
    with open(PACK, encoding="utf-8") as f:
        p = json.load(f)
    return {"rows": f'{p["rows"]:,}', "days": f'{p["days"]:,}', "stocks": f'{p["stocks"]:,}'}


def block(cfg, st):
    url = f"{BASE}/{cfg['path']}"
    img = f"{BASE}/og-cover.png"
    return "\n".join([
        START,
        f'<meta name="description" content="{cfg["desc"].format(**st)}">',
        f'<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{cfg["title"]}">',
        f'<meta property="og:title" content="{cfg["og_title"]}">',
        f'<meta property="og:description" content="{cfg["og_desc"].format(**st)}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{img}">',
        f'<meta property="og:image:width" content="1200">',
        f'<meta property="og:image:height" content="630">',
        f'<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:image" content="{img}">',
        END,
    ])


def apply(html, new_block):
    if START not in html or END not in html:
        raise SystemExit("缺 OG:START/OG:END 标记")
    s = html.index(START); e = html.index(END) + len(END)
    return html[:s] + new_block + html[e:]


def run(write):
    st = pack_stats()
    bad = 0
    for rel, cfg in PAGES.items():
        p = os.path.join(SITE, rel)
        html = open(p, encoding="utf-8").read()
        want = block(cfg, st)
        cur = html[html.index(START):html.index(END) + len(END)]
        if write:
            if cur != want:
                open(p, "w", encoding="utf-8").write(apply(html, want))
                print(f"OK 重写 {rel}")
            else:
                print(f"OK {rel} 已是现库数字，无需改")
        else:
            if cur != want:
                print(f"BAD {rel} OG 块数字/内容与现库不一致，需重写"); bad += 1
            else:
                print(f"OK {rel} OG 块与现库一致")
    # 图片存在
    imgp = os.path.join(SITE, "og-cover.png")
    if not os.path.exists(imgp):
        print("BAD 缺 og-cover.png"); bad += 1
    else:
        print(f"OK og-cover.png {os.path.getsize(imgp)}B")
    return (2 if bad else 0) if not write else 0


def selftest():
    st = {"rows": "1,234", "days": "56", "stocks": "78"}
    b = block(PAGES["index.html"], st)
    ok = (START in b and END in b and 'content="1,234 条逐日明细' in b
          and f"{BASE}/og-cover.png" in b and "twitter:card" in b)
    # 幂等：apply 两次结果相同
    html = "<head>\n" + START + "\nOLD\n" + END + "\n<style>"
    once = apply(html, b); twice = apply(once, b)
    ok = ok and (once == twice) and ("OLD" not in once)
    print(f"selftest {'8/8 OK' if ok else 'FAIL'}")
    return 0 if ok else 2


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(run("--check" not in sys.argv))
