# A股涨停数据 · 连板数据（2021–2026，10 万+ 条，每日自动更新）+ 策略体检样板

这个仓库放两样**真数据跑出来的**东西：一是可以直接下载的 **A股涨停数据 / 连板数据**（含免费样例），
二是几个不好看但真实的复盘/体检样板。先看东西，再决定要不要聊。

> 别人给的是「今天的涨停池」，这里给的是**从 2021 年起 10 万+ 条的全量涨停数据**（含退市股、一字板标记、连板高度、次日表现），每天收盘后自动更新。

## 零、先给你一个免费工具：涨停口径体检器

`tools/caliber_check.py`（单文件、纯 Python 标准库、`--selftest` 自检）—— 拿你自己的日线 CSV 跑一遍，
把六件会让涨停判定悄悄失真的坑逐个照出来（0 量占位行 / 一字板买不进 / 除权日 preclose≠前收 / ST 跨 2026-08 分段 /
涨停价 .5 分级的四舍五入差一分 / 用涨幅≥9.9% 近似判涨停漏判）。说明页：[`caliber-check.html`](caliber-check.html)

```bash
curl -O https://dangnianqin.github.io/astock-sample-library/tools/caliber_check.py
python3 caliber_check.py --selftest
python3 caliber_check.py your_daily.csv
```

## 一、涨停数据集（免费样例就在本仓库）

6 年 / 5,398 只股票（含退市股），每条带连板高度、一字板标记、
次日开盘溢价、次日收盘、次日是否续板。数据源是本机通达信官方日线包（1990 年起，5,900+ 只，含退市股）。
行数、最新交易日这些每天会变的数字一律看下面这块自动生成的表，不要手写。

<!-- LIVE-BEGIN 自动生成：build_pack/update_daily.py 每次运行重写，勿手改 -->

| 指标 | 数值 |
|---|---|
| 最新交易日 | **2026-11-27** |
| 全量涨停记录 | **99,191** 条 |
| 覆盖交易日 | **1,425** 个（2021-01-11 起） |
| 当日涨停 | **437** 家（连板 30 / 一字 6 / 最高 6 板 / ST None） |
| 免费样本 | `limitup_sample_30d.csv` **2,224** 行 · 2026-10-19 → 2026-11-27（30 个交易日） |

以上由构建脚本按 `live/meta.json` 写出，与付费包逐行一致；数字每天变，不要手改这一块。
<!-- LIVE-END -->

口径红线：**只用未复权价判涨停**（`close_raw >= round(前收×(1+涨跌幅限制),2)`，Decimal 四舍五入到分）；
ST 2026-08 前 5%、之后 10%；创业板/科创板 20%、北交所 30%、新股前 5 日不限。

| 免费文件 | 内容 | 行数 |
|---|---|---|
| [`sample/limitup_sample_30d.csv`](sample/limitup_sample_30d.csv) | 最近 30 个交易日的全部涨停记录，14 列全字段 | 见上表 |
| [`sample/sentiment_daily.csv`](sample/sentiment_daily.csv) | 每日涨停家数 / 一字板数 / 最高板 / 次日续板数 | 见图 |
| [`sample/streak_stats.csv`](sample/streak_stats.csv) | 按连板数分组的次日期望与续板率 | 25 |
| [`sample/fields.md`](sample/fields.md) | 字段说明 + 口径边界 + 已知缺陷 | — |

字段（14 列）：`code` / `date` / `board`(MAIN,GEM,STAR,BJ) / `is_st` / `close_raw` / `limit_price` /
`amount` / `turnover`(%) / `is_one_word` / `streak` / `next_open_gap` / `next_high_pct` / `next_close_pct` / `next_is_limit`。

完整包（2021-01-11 起至最新交易日，行数见上方自动块；附示例脚本 + 字段说明，zip 约 2.5 MB，pandas/duckdb 直读）：
**https://dangnianqin.github.io/astock-sample-library/limitup-db.html**

## 二、样板：策略体检报告（37 笔真实成交）

[`sample-case.html`](sample-case.html) — 4 个模拟账户的真实成交按 FIFO 配成 37 笔已了结交易，逐笔重算真实费用
（佣金保底 5 元、印花税、过户费），并列三个口径：资金曲线 / 逐笔均值 / 等权复利，含输家归因与处方。

实测结果（不好看，但真实）：37 笔、胜率 16.2%、资金 −3.35%、逐笔均值 −3.63%、
等权复利 −75.66%、PF(元) 0.218、PF(等权) 0.967。

## 三、样板：涨停统计实证（2 页 PDF）

[`paper-sample-2p.pdf`](paper-sample-2p.pdf) — 2023-01-03 ~ 2026-11-23，941 个交易日，65,951 条涨停记录。

- 次日仍涨停基准 23.2%
- 连板层级：首板 18.0% → 2 板 34.1% → 3 板 47.0% → 6 板+ 58.2%
- 一字板 62.0% 次日仍涨停，但**买不进**（不是收益）
- 成交额最小档 33.8% vs 最大档 18.0%
- 次日高开 ≥3%：仍涨停 42.8% / 收盘 +5.41% / 收阳 79.4%；低开：5.8% / −1.97% / 32.0%
- **反例**：2 板 + 换手板 + 成交额>中位 三条件叠加仅 28.9%，低于其余组 22.4%/+1.97%

## 四、每日复盘样刊

[`day-report.html`](day-report.html) — 指数 / 赚钱效应 / 连板梯队 / 高位股 / 情绪阶段与仓位区间 / 次日观察点。
2026-11-23 实例：上证 3538.95 (+0.15%)、深成 10454.37 (+1.93%)、创业板 2280.20 (+3.08%)；
上涨 4,657 / 下跌 783（83.6%）、涨停 152 / 跌停 7、一字板 4（2.6%）；成交额 15,528 亿（量比 1.10）；
连板梯队 5 板 2 / 3 板 1 / 2 板 14 / 首板 135。三项自检全过才出刊。

## 复算

```
python3 paper_sample.py        # 直连 DuckDB → paper_sample_data.json（含自检）
python3 build_paper_pdf.py     # JSON → A4 PDF
python3 daily_review_sample.py 2026-11-23   # 日报样刊 → day_report_data.json + day-report.html
```

连板递推自检：首板 50,676 → 9,101 → 3,102 → 1,459 → 719 → 374，一致性误差 0.0%；
另有独立 SQL 实现交叉校验，总数与比例一致。

## 边界

不荐股、不代下单、不承诺收益、不碰带未来函数的指标。
能保证的是数字没算错、口径没混用、结论能被复算。

## 联系方式

- 数据集与代做：闲鱼「A股 策略体检 / 公式代写 / 数据分析帮做」
- 落地页：https://dangnianqin.github.io/astock-sample-library/

## 许可

- 代码与静态页（`*.py` / `*.js` / `*.html`）：MIT，见 [LICENSE](LICENSE)
- 免费样例数据（Release 里的 `astock-sample-free.zip`、`sample/` 下的近 40 交易日 CSV）：CC BY 4.0，署名后可自由使用与再分发
- 全量历史数据（2021 起全量，行数/股票数/交易日以 [live/meta.json](live/meta.json) 为准，每日增长）：付费项，不在本仓库分发
- 数据来源：交易所公开日线派生（未复权价与成交量），不含任何付费数据源
