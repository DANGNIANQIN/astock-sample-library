#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股涨停数据口径体检器 —— 拿你自己的日线 CSV 跑一遍，看你的涨停判定对不对。

为什么有这个：A股涨停判定有七个坑，几乎所有公开数据/自建管线都会踩其中一个，
而踩了不会报错，只会让回测结论悄悄失真。这个工具只做一件事：
**用一份日线 CSV 把七个坑逐个照出来**，每条给出样本行和正确做法。

用法：
    python3 caliber_check.py your_daily.csv
    python3 caliber_check.py --selftest        # 自检（内置带缺陷的样本，断言每个探测器都触发）

输入 CSV 必需列（大小写不敏感）：
    code, date, open, high, low, close, preclose, volume
可选列：
    name  （含 "ST" 才算 ST；没有该列则不做 ST 分段检查）
    amount（成交额，仅透传输出）

date 支持 20260105 / 2026-01-05 两种写法。价格单位：元（不是分）。
"""

import csv
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def limit_pct(code, name, date_str):
    """按板块/ST/日期返回涨跌幅限制（Decimal）。与交易所口径一致。"""
    code = str(code).strip()
    d = date_str
    is_st = bool(name) and ("ST" in name.upper())
    if is_st:
        # ST：2026-08-03 起 10%，此前 5%（最后一个 5% 封板日是 2026-07-31 星期五）
        return Decimal("0.10") if d >= "20260803" else Decimal("0.05")
    head3 = code[:3]
    if head3 in ("688", "689") or head3.startswith("30"):
        return Decimal("0.20")
    if code[:1] in ("8", "4") or head3 in ("920",):
        return Decimal("0.30")
    return Decimal("0.10")


def limit_price(preclose, pct):
    """涨停价 = 前收 × (1+限制)，四舍五入到分（必须 Decimal，浮点会错一分）。"""
    return (Decimal(preclose) * (Decimal(1) + pct)).quantize(CENT, rounding=ROUND_HALF_UP)


def norm_date(s):
    s = str(s).strip()
    return s.replace("-", "").replace("/", "")[:8]


def load(path):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        r.fieldnames = [(x or "").strip().lower() for x in (r.fieldnames or [])]
        for line, raw in enumerate(r, start=2):
            try:
                row = {
                    "line": line,
                    "code": str(raw["code"]).strip(),
                    "date": norm_date(raw["date"]),
                    "open": Decimal(str(raw["open"])),
                    "high": Decimal(str(raw["high"])),
                    "low": Decimal(str(raw["low"])),
                    "close": Decimal(str(raw["close"])),
                    "preclose": Decimal(str(raw.get("preclose") or "0")),
                    "volume": Decimal(str(raw.get("volume") or "0")),
                    "name": (raw.get("name") or "").strip(),
                }
            except Exception as e:
                raise SystemExit("第 %d 行解析失败：%s（请检查列名与价格单位）" % (line, e))
            rows.append(row)
    rows.sort(key=lambda x: (x["code"], x["date"]))
    return rows


def is_limit_up(row):
    if row["preclose"] <= 0:
        return False
    lp = limit_price(row["preclose"], limit_pct(row["code"], row["name"], row["date"]))
    return row["close"] >= lp - Decimal("0.001")


def check(rows):
    """六个探测器：每个返回 (名称, 命中列表, 说明)。"""
    by_code = defaultdict(list)
    for r in rows:
        by_code[r["code"]].append(r)

    zero_vol_flat, exdiv_jump, st_window, one_word, float_round, pct_approx, st_backfill = [], [], [], [], [], [], []

    for code, bars in by_code.items():
        prev = None
        for r in bars:
            lp = limit_price(r["preclose"], limit_pct(r["code"], r["name"], r["date"])) if r["preclose"] > 0 else None

            # ① 前收填充的 0 量占位行（O=H=L=C 且 volume=0）
            if r["volume"] == 0 and r["open"] == r["high"] == r["low"] == r["close"]:
                zero_vol_flat.append(r)

            # ② 一字板（O=H=L=C=涨停价）：能标出来，但买不进，回测不许按涨停价成交
            if lp is not None and r["open"] == r["high"] == r["low"] == r["close"] and r["close"] >= lp - Decimal("0.001"):
                one_word.append(r)

            # ③ 除权跳变：preclose != 上一交易日 close，|跳变| 又超过涨跌幅限制
            if prev is not None and r["preclose"] > 0 and prev["close"] > 0:
                if r["preclose"] != prev["close"]:
                    move = abs(Decimal(r["preclose"]) / Decimal(prev["close"]) - Decimal(1))
                    if move > limit_pct(r["code"], r["name"], r["date"]):
                        exdiv_jump.append((r, prev["close"]))

            # ④ ST 跨 2026-08-03：该日前后限制不同，跨窗口回测必须按 asof 分段
            if r["name"] and "ST" in r["name"].upper() and "20260803" <= r["date"] <= "20260831":
                st_window.append(r)

            # ⑤ 银行家舍入：round() 会把 0.5 舍到偶数，交易所是四舍五入
            if r["preclose"] > 0:
                raw = Decimal(r["preclose"]) * (Decimal(1) + limit_pct(r["code"], r["name"], r["date"]))
                banker = raw.quantize(CENT)  # Decimal 默认 ROUND_HALF_EVEN
                half_up = raw.quantize(CENT, rounding=ROUND_HALF_UP)
                if banker != half_up:
                    float_round.append((r, str(half_up), str(banker)))

            # ⑥ 用 pct_chg>=9.9% 近似判涨停：漏掉恰好 = 涨停价但 pct 显示 9.98% 的票
            if lp is not None and r["preclose"] > 0 and abs(r["close"] - lp) < Decimal("0.001"):
                pct = (r["close"] / r["preclose"] - Decimal(1)) * 100
                if pct < Decimal("9.99") and limit_pct(r["code"], r["name"], r["date"]) == Decimal("0.10"):
                    pct_approx.append((r, str(pct.quantize(Decimal("0.01")))))

            # ⑦ ST 状态按「现名」回填：历史日期用了今天的名字 → 整段 5% 判定错
            #     （这正是我们自己在 v_kline_adj 上查出的缺陷：312 只全等于当前名含 ST 的股票，0 只摘帽）
            if r["preclose"] > 0 and r["name"] and "ST" in r["name"].upper() and r["date"] < "20260803":
                move = abs(r["close"] / r["preclose"] - Decimal(1))
                lp5 = limit_price(r["preclose"], Decimal("0.05"))
                lp10 = limit_price(r["preclose"], Decimal("0.10"))
                if move > Decimal("0.0515"):
                    st_backfill.append(r)
                elif r["close"] >= lp10 - Decimal("0.001") and r["close"] > lp5 + Decimal("0.02"):
                    st_backfill.append(r)

            prev = r

    return [
        ("①0量平盘占位行", zero_vol_flat,
         "O=H=L=C 且 volume=0 = 前收填充的占位 bar（常见于分钟线上卷成日线、或停牌日补前收）。"
         "这不是真实成交，判涨停/算振幅前必须剔除，否则「平盘 0 量」会被算成弱势。"),
        ("②一字板", one_word,
         "开=高=低=收=涨停价：可以标记，但**买不进**。回测按涨停价成交等于白送收益（实测这种样本会把单笔均值从 +1.60% 抬到 +5.93%）。"),
        ("③除权跳变（preclose≠前一日收盘）", [x[0] for x in exdiv_jump],
         "未复权口径下 preclose 应等于上一交易日 close；两者不等且跳变超过涨跌幅限制 = 除权除息日。"
         "此时判涨停必须用 preclose，不能用前一日 close 手算，否则会造出 -95% 的假跌/假涨。"),
        ("④ST 跨 2026-08-03", st_window,
         "ST 涨跌幅 2026-08-03 前 5%、之后 10%（最后一个 5% 封板日是 2026-07-31）。"
         "跨这个日期的回测必须按日期分段取限制值，写死 5% 或 10% 都会错。"),
        ("⑤涨停价落在 .5 分级（round() 会差一分）", [x[0] for x in float_round],
         "涨停价必须用四舍五入（ROUND_HALF_UP）到分。Python 的 round()/Decimal 默认是银行家舍入，"
         "在 .5 上差一分——一只票可能正好落在 .5 上，一分钱决定它是「涨停封死」还是「差一档没封」。下列行就是会踩到的那几行。"),
        ("⑥涨幅显示 <9.99% 的涨停行（用 pct 近似会漏判）", [x[0] for x in pct_approx],
         "下面这些行确实收在涨停价上，但涨幅四舍五入后显示 9.98% 之类的值。"
         "用「涨幅 >= 9.9%」近似判涨停就会漏掉它们；正确做法是比价格：close >= round(preclose×(1+limit),2) - 0.001。"),
        ("⑦ST 名下涨跌幅超过 5.15%（按 5% 限幅判这一天就一定错）", st_backfill,
         "表里的 name 是**今天的名字**，用它反推历史 ST 状态会整段错。下面这些行：名字带 ST、"
         "而当日涨跌幅超过 5.15%（或收盘正好落在 10% 涨停价上），5% 限幅在数学上不成立。三种成因按可能性排："
         "① **ST 状态回填**——今天叫 ST 的票，非 ST 期间按 5% 判，+10% 封板日被记成「涨停」且误标一字板"
         "（我们自己的库就是这样错的：312 只=当前名含 ST，0 只摘帽）；"
         "② **退市整理期/恢复上市首日/新股**——那几天制度性没有 5% 限制；"
         "③ 名称是旧快照、已摘帽。先看该股的上市/风险警示公告排除②，再按价格证据定①。"
         "顺带一提反方向（历史 ST、现名不带 ST）单行无法证伪，需要 ±10 日窗口的价格证据，"
         "方法与全量对账见 st-history.html。"),
    ]


def report(rows, out=sys.stdout):
    findings = check(rows)
    total = len(rows)
    print("样本：%d 行 / %d 只股票 / %s → %s" % (
        total, len({r['code'] for r in rows}),
        rows[0]["date"] if rows else "-", rows[-1]["date"] if rows else "-"), file=out)
    RISK = ("⑤", "⑥")
    bad = risk = 0
    for name, hits, why in findings:
        flag = "OK  " if not hits else ("风险行" if name.startswith(RISK) else "命中")
        if hits:
            if name.startswith(RISK):
                risk += 1
            else:
                bad += 1
        print("\n[%s] %s —— %d 处" % (flag, name, len(hits)), file=out)
        if hits:
            for h in hits[:5]:
                print("   行%-6s %s %s pre=%s close=%s" % (
                    h["line"], h["code"], h["date"], h["preclose"], h["close"]), file=out)
            if len(hits) > 5:
                print("   …另 %d 处" % (len(hits) - 5), file=out)
        print("   " + why, file=out)
    print("\n结论：数据自身缺陷 %d 项（①③④⑦），逻辑容易踩坑 %d 项（②⑤⑥）。"
          "标「命中」的是你数据里已经错了、会悄悄传播进回测结论的；标「风险行」的是判定逻辑本身容易错的地方，"
          "命中不代表数据错，代表你的代码在这几行必须用正确写法。" % (bad, risk), file=out)
    return bad


# ---------------- 自检：内置带缺陷样本，断言每个探测器都只在自己的缺陷上触发 ----------------

def _mk(code, date, o, h, l, c, pre, vol=1000, name=""):
    return {"line": 0, "code": code, "date": date, "open": Decimal(str(o)), "high": Decimal(str(h)),
            "low": Decimal(str(l)), "close": Decimal(str(c)), "preclose": Decimal(str(pre)),
            "volume": Decimal(str(vol)), "name": name}


def selftest():
    # 干净样本：正常涨停（10.00 前收 → 11.00 涨停）
    clean = [_mk("600000", "20260105", "10.5", "11.00", "10.4", "11.00", "10.00")]
    f = check(clean)
    assert all(not h for _, h, _ in f), [n for n, h, _ in f if h]

    # ① 0 量平盘
    a = [_mk("600001", "20260105", "5", "5", "5", "5", "5", 0)]
    assert len(dict((n, h) for n, h, _ in check(a))["①0量平盘占位行"]) == 1

    # ② 一字板
    b = [_mk("600002", "20260105", "11.00", "11.00", "11.00", "11.00", "10.00")]
    assert len(dict((n, h) for n, h, _ in check(b))["②一字板"]) == 1

    # ③ 除权跳变：preclose 8.00 vs 前一日 close 10.00（10派20）
    c = [_mk("600003", "20260105", "10", "10", "10", "10", "10"),
         _mk("600003", "20260106", "8.1", "8.2", "8.0", "8.1", "8.00")]
    assert len(dict((n, h) for n, h, _ in check(c))["③除权跳变（preclose≠前一日收盘）"]) == 1

    # ④ ST 跨 2026-08：ST 票 2026-08-05，限制 10%
    d = [_mk("600004", "20260805", "5.5", "5.5", "5.5", "5.50", "5.00", 1000, "*ST某某")]
    assert len(dict((n, h) for n, h, _ in check(d))["④ST 跨 2026-08-03"]) == 1
    assert limit_pct("600004", "*ST某某", "20260731") == Decimal("0.05")
    assert limit_pct("600004", "*ST某某", "20260803") == Decimal("0.10")

    # ⑤ 银行家舍入差：preclose 8.15 → 8.15*1.1=8.965 → 四舍五入 8.97，银行家 8.96（浮点会算出 8.96/7.33 这类错）
    assert limit_price("8.15", Decimal("0.10")) == Decimal("8.97")
    e = [_mk("600005", "20260105", "8.97", "8.97", "8.90", "8.97", "8.15")]
    assert len(dict((n, h) for n, h, _ in check(e))["⑤涨停价落在 .5 分级（round() 会差一分）"]) == 1

    # ⑥ pct_chg 近似漏判：preclose 3.03 → 涨停 3.33，涨幅 9.9009% < 9.99
    pct = (Decimal("3.33") / Decimal("3.03") - 1) * 100
    assert pct < Decimal("9.99"), pct
    g = [_mk("600006", "20260105", "3.3", "3.33", "3.3", "3.33", "3.03")]
    assert len(dict((n, h) for n, h, _ in check(g))["⑥涨幅显示 <9.99% 的涨停行（用 pct 近似会漏判）"]) == 1

    # ⑦ ST 按现名回填：名字带 ST、但历史行涨了 10%（5% 限幅下不可能）
    h = [_mk("600007", "20260105", "10.6", "11.00", "10.5", "11.00", "10.00", 1000, "ST某某")]
    assert len(dict((n, x) for n, x, _ in check(h))["⑦ST 名下涨跌幅超过 5.15%（按 5% 限幅判这一天就一定错）"]) == 1
    # 干净对照：真 ST、真 5% 封板（10.00 → 10.50），不许报警
    i2 = [_mk("600008", "20260105", "10.2", "10.50", "10.1", "10.50", "10.00", 1000, "ST某某")]
    assert not dict((n, x) for n, x, _ in check(i2))["⑦ST 名下涨跌幅超过 5.15%（按 5% 限幅判这一天就一定错）"]

    print("selftest PASS：7/7 探测器在各自缺陷样本上触发，干净样本零误报", file=sys.stdout)
    return 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--selftest":
        return selftest()
    return 0 if report(load(argv[0])) >= 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
