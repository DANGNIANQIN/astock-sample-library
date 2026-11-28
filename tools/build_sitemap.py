#!/usr/bin/env python3
"""sitemap.xml 生成器 —— 从真实文件清单 + git 提交日期生成，禁止手写日期。

病根：sitemap.xml 是手写的，15 条 URL 的 lastmod 全部停在 2026-11-25/26/27，
而 index.html 等页面此后天天在变（数据窗口、复盘表、体检报告）。搜索引擎看到
的「最后修改日」是假的，等于告诉爬虫这些页不再更新 —— 与「复盘表冻在 11-25」
「paper 样例旧库」是同一类「数字不会自己变」。另外手写清单天然漏页（
paper-sample-2p.pdf 从未进过 sitemap），新增页面也没有任何闸门拦住。

用法：
  build_sitemap.py --write     重新生成 sitemap.xml
  build_sitemap.py --check     与磁盘上的 sitemap.xml 逐字节比对；不一致 rc=2
  build_sitemap.py --selftest  用临时 fixture 自检（含排除规则、缺 title 报错）
"""
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = "https://dangnianqin.github.io/astock-sample-library/"
ROOT = Path(__file__).resolve().parent.parent

# dl.html 是卡密/下载跳转页（含免费样本兜底），不属内容页，不入索引。
EXCLUDE_HTML = {"dl.html"}
# 目录型落地页：只有存在 index.html 才收录
DIR_INDEXES = ("sample", "live")


def collect_paths(root: Path):
    """返回相对路径清单（'' 表示站点根）。只收真实存在的文件。"""
    out = []
    for p in sorted(root.glob("*.html")):
        if p.name in EXCLUDE_HTML:
            continue
        out.append("" if p.name == "index.html" else p.name)
    for d in DIR_INDEXES:
        if (root / d / "index.html").is_file():
            out.append(f"{d}/")
    for p in sorted(root.glob("*.pdf")):
        out.append(p.name)
    return out


def git_lastmods(root: Path):
    """每个文件取 git 最后提交日期（%cs），不手写、不取 mtime（mtime 会被 checkout 打乱）。"""
    try:
        res = subprocess.run(
            ["git", "-C", str(root), "log", "--format=COMMIT %cs", "--name-only", "--", "."],
            capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return {}
    dates, cur = {}, None
    for line in res.splitlines():
        if line.startswith("COMMIT "):
            cur = line.split(" ", 1)[1].strip()
        elif line.strip() and cur:
            dates.setdefault(line.strip(), cur)  # 首次出现=最新提交
    return dates


def local_file_for(root: Path, rel: str) -> Path:
    if rel == "":
        return root / "index.html"
    if rel.endswith("/"):
        return root / rel / "index.html"
    return root / rel


def render(root: Path, paths, dates) -> str:
    bad = []
    rows = []
    for rel in paths:
        f = local_file_for(root, rel)
        if not f.is_file():
            bad.append(f"{rel}: 本地无此文件")
            continue
        if f.suffix == ".html":
            body = f.read_text(encoding="utf-8", errors="replace")
            if "<title" not in body:
                bad.append(f"{rel}: 无 <title>，不该进索引")
                continue
            if 'name="robots"' in body and "noindex" in body:
                continue
        lm = dates.get(f.relative_to(root).as_posix())
        if not lm:
            bad.append(f"{rel}: git 无提交日期 ⇒ 不写假的 lastmod")
            continue
        rows.append((BASE + rel, lm))
    if bad:
        print("BAD:\n  " + "\n  ".join(bad))
        print("（新增页面请先 git add/commit，再 --write；不填 DATE=今天 这种假 lastmod）")
        raise SystemExit(2)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lm in rows:
        lines.append(f"  <url><loc>{loc}</loc><lastmod>{lm}</lastmod></url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def selftest():
    ok = 0
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        (r / "index.html").write_text("<title>a</title>", encoding="utf-8")
        (r / "x.html").write_text("<title>b</title>", encoding="utf-8")
        (r / "dl.html").write_text("<title>c</title>", encoding="utf-8")
        (r / "doc.pdf").write_bytes(b"%PDF-1.4")
        (r / "sample").mkdir()
        (r / "sample" / "index.html").write_text("<title>d</title>", encoding="utf-8")
        paths = collect_paths(r)
        assert "" in paths and "x.html" in paths, paths
        assert "dl.html" not in paths, "排除规则失效"
        assert "sample/" in paths and "doc.pdf" in paths, paths
        ok += 1
        dates = {k: "2026-11-28" for k in ["index.html", "x.html", "sample/index.html", "doc.pdf"]}
        out = render(r, paths, dates)
        assert "<loc>" + BASE + "</loc>" in out
        assert "2026-11-28" in out and "dl.html" not in out
        ok += 1
        # 缺日期 → 必须报错，不许填假日期
        try:
            render(r, ["x.html"], {})
            raise AssertionError("缺 lastmod 未报错")
        except SystemExit:
            ok += 1
        # 缺 title → 报错
        (r / "no_title.html").write_text("<p>x</p>", encoding="utf-8")
        try:
            render(r, ["no_title.html"], {"no_title.html": "2026-11-28"})
            raise AssertionError("无 title 未报错")
        except SystemExit:
            ok += 1
        # 文件不存在 → 报错
        try:
            render(r, ["ghost.html"], {"ghost.html": "2026-11-28"})
            raise AssertionError("幽灵 URL 未报错")
        except SystemExit:
            ok += 1
    print(f"OK sitemap 生成器自检 {ok}/5")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return 0
    paths = collect_paths(ROOT)
    text = render(ROOT, paths, git_lastmods(ROOT))
    target = ROOT / "sitemap.xml"
    if "--check" in sys.argv:
        cur = target.read_text(encoding="utf-8") if target.is_file() else ""
        if cur != text:
            print(f"BAD sitemap.xml 与现况不符（{len(paths)} 个页面）；应运行 --write")
            return 2
        print(f"OK sitemap.xml = {len(paths)} 个页面，lastmod 全部取自 git 提交日期")
        return 0
    target.write_text(text, encoding="utf-8")
    print(f"WROTE sitemap.xml {len(paths)} 个页面 / {target.stat().st_size}B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
