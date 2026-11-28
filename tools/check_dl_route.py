#!/usr/bin/env python3
"""dl.html 路由契约检查（买家的「永久下载入口」到底通不通）。

为什么不用无头浏览器：2026-11-29 实测 chromium --headless --dump-dom 同一 URL
连跑 3 次有 1-2 次返回空 DOM ⇒ 闸门会把抖动报成红、把真故障淹掉。
这里改成用 node 真跑页面里那段 JS（页面自己的代码，不是复述），输入/输出都确定。

契约（交付卡文案写的是 dl.html?p=lupack）：
  ?p=lupack            -> https://<tunnel>/?p=lupack   （服务端只认根路径带查询）
  ?p=/download?code=x  -> https://<tunnel>/download?code=x
  无 p                 -> https://<tunnel>/

用法：
  check_dl_route.py                 # 本地 dl.html + 线上隧道，逐条验
  check_dl_route.py --json          # 机读
  check_dl_route.py --selftest      # 用一个已知有病的实现证明本检查真会红
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)                      # public-site/
LOCAL_DL = os.path.join(SITE, "dl.html")
HOST_FILE = os.path.join(SITE, "tunnel-host.txt")

HARNESS = r"""
const fs = require('fs');
const code = fs.readFileSync(process.argv[2], 'utf8');
const search = process.argv[3];
let replaced = null;
global.location = {
  search: search, pathname: '/dl.html', origin: 'https://page.example', href: '',
  replace: function (u) { replaced = u; },
};
global.document = { getElementById: function () { return { innerHTML: '' }; } };
global.fetch = function () { return Promise.resolve({ text: function () { return Promise.resolve('TUNNEL.HOST'); } }); };
global.Image = function () {};
try { eval(code); } catch (e) { console.log('JS_ERROR:' + e.message); process.exit(0); }
setTimeout(function () { console.log(replaced === null ? 'NO_REPLACE' : replaced); }, 300);
"""


def extract_script(html):
    """取页面里那段做转发跳转的 inline script（不是 hit.js 外链）。"""
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    for b in blocks:
        if "location.replace" in b:
            return b
    raise ValueError("dl.html 里找不到含 location.replace 的 inline script")


def run_case(js, search):
    with tempfile.TemporaryDirectory() as td:
        p_js = os.path.join(td, "page.js")
        p_h = os.path.join(td, "harness.js")
        open(p_js, "w", encoding="utf-8").write(js)
        open(p_h, "w", encoding="utf-8").write(HARNESS)
        out = subprocess.run(["node", p_h, p_js, search], capture_output=True, text=True, timeout=30)
        return (out.stdout or "").strip().splitlines()[-1] if out.stdout.strip() else ""


def expected(search, host="TUNNEL.HOST"):
    from urllib.parse import parse_qs
    q = parse_qs(search.lstrip("?")) if search.startswith("?") else {}
    p = (q.get("p") or [""])[0].strip()
    if p.startswith("/"):
        return "https://%s%s" % (host, p)
    if p:
        from urllib.parse import quote
        return "https://%s/?p=%s" % (host, quote(p, safe=""))
    return "https://%s/" % host


CASES = ["", "?p=lupack", "?p=/download?code=abc", "?p=%2Fdownload%3Fcode%3Dabc"]


def check_html(html):
    """纯函数：返回 (ok, problems)。可被自检拿去跑有病的 fixture。"""
    problems = []
    try:
        js = extract_script(html)
    except ValueError as e:
        return False, [str(e)]
    for c in CASES:
        got = run_case(js, c)
        want = expected(c)
        if got != want:
            problems.append("search=%-34r 得到 %-42r 期望 %r" % (c, got, want))
    return (not problems), problems


def live(host):
    """线上两跳：/?p=lupack 必须是兑换页；/<key> 必须 404（证明为什么不能拼路径）。"""
    probs = []
    try:
        with urllib.request.urlopen("https://%s/?p=lupack" % host, timeout=15) as r:
            body = r.read().decode("utf-8", "ignore")
            if r.status != 200:
                probs.append("/?p=lupack http=%s" % r.status)
            if 'name="code"' not in body:
                probs.append("/?p=lupack 不是兑换页（没有卡密输入框）")
    except Exception as e:
        probs.append("/?p=lupack 拉不到：%s" % e)
    try:
        req = urllib.request.Request("https://%s/lupack" % host)
        urllib.request.urlopen(req, timeout=15)
        probs.append("/lupack 竟然 200（服务端改成认路径了，本检查的契约需要跟着改）")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            probs.append("/lupack http=%s（期望 404）" % e.code)
    except Exception as e:
        probs.append("/lupack 拉不到：%s" % e)
    return (not probs), probs


SELFTEST_BAD = """<!doctype html><html><body><p id=s></p><script>
(function(){
  var s=document.getElementById('s');
  var q=new URLSearchParams(location.search);
  var p=q.get('p')||'/';
  if(p.charAt(0)!=='/')p='/'+p;                     // 旧版：产品键被当路径
  fetch('tunnel-host.txt').then(function(r){return r.text()}).then(function(h){
    location.replace('https://'+h.trim()+p);
  });
})();
</script></body></html>"""


def main():
    args = sys.argv[1:]
    if "--selftest" in args:
        html = open(LOCAL_DL, encoding="utf-8").read()
        ok_good, p_good = check_html(html)
        ok_bad, p_bad = check_html(SELFTEST_BAD)
        # 上线版必须过；旧版必须被判红（否则这个检查是哑的）
        passed = ok_good and (not ok_bad)
        print("selftest: 现版 %s / 旧病版被抓到 %s" % ("OK" if ok_good else "FAIL " + "; ".join(p_good),
                                                  "OK" if not ok_bad else "FAIL（没抓到）"))
        return 0 if passed else 1

    html = open(LOCAL_DL, encoding="utf-8").read()
    ok_html, p_html = check_html(html)
    res = {"local": {"ok": ok_html, "problems": p_html}}
    host = ""
    if os.path.exists(HOST_FILE):
        host = open(HOST_FILE, encoding="utf-8").read().strip()
    if host:
        ok_live, p_live = live(host)
        res["live"] = {"ok": ok_live, "problems": p_live, "host": host}
    else:
        res["live"] = {"ok": False, "problems": ["tunnel-host.txt 为空，线上未核（未核不算绿）"]}

    if "--json" in args:
        print(json.dumps(res, ensure_ascii=False))
    else:
        if ok_html:
            print("OK 本地 dl.html 路由契约 %d/%d（产品键→/?p=、路径原样转发）" % (len(CASES), len(CASES)))
        else:
            print("ACTION 本地 dl.html 路由契约不成立：" + "；".join(p_html))
        if res["live"]["ok"]:
            print("OK 线上隧道 /?p=lupack 是兑换页、/lupack 是 404（%s）" % host)
        else:
            print("ACTION 线上未通过：" + "；".join(res["live"]["problems"]))
    ok = ok_html and res["live"]["ok"]
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
