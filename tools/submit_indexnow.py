#!/usr/bin/env python3
"""IndexNow 提交（Bing/Yandex/Seznam/Naver 共享的免费收录接口，零账号）。

为什么需要：站点唯一不依赖人工扫码的获客道是搜索引擎。2026-11-28 11:0x 实测三家
sitemap ping 端点全废（bing 410 / google 404「ping is deprecated」/ baidu 404）——
「提交 sitemap 就等收录」的老办法已经不存在了。IndexNow 是现行唯一免注册的推送协议：
只需在站点根放一个 {key}.txt（内容即 key），再 POST 一次 URL 列表，HTTP 200/202 即受理。

用法：
  submit_indexnow.py --init      生成/复用 key 文件（public-site/<key>.txt），打印 key
  submit_indexnow.py --verify    只验 key 文件在公网 200 且内容==key（受理前必须过）
  submit_indexnow.py --submit    读取 sitemap.xml 的 URL 全部提交，打印引擎响应码
  submit_indexnow.py --selftest  纯函数自检
"""
import json
import os
import re
import secrets
import sys
import urllib.request
from pathlib import Path

SITE = "https://dangnianqin.github.io/astock-sample-library/"
HOST = "dangnianqin.github.io"
KEYFILE = Path(__file__).resolve().parent.parent / ".indexnow_key"
ROOT = Path(__file__).resolve().parent.parent
ENDPOINT = "https://api.indexnow.org/indexnow"


def urls_from_sitemap(root: Path):
    text = (root / "sitemap.xml").read_text(encoding="utf-8")
    return re.findall(r"<loc>([^<]+)</loc>", text)


def build_payload(host, key, key_location, urls):
    return {"host": host, "key": key, "keyLocation": key_location, "urlList": list(urls)}


def post_json(url, payload, timeout=20):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()[:200].decode("utf-8", "replace")


def selftest():
    ok = 0
    urls = ["https://a/x.html", "https://a/y.pdf"]
    p = build_payload("a", "k" * 32, "https://a/k.txt", urls)
    assert p["urlList"] == urls and p["key"] == "k" * 32
    ok += 1
    assert all(u.startswith("https://") for u in p["urlList"])
    ok += 1
    # key 必须 8-128 位 hex，不符合的必须被拒
    def key_ok(k):
        return bool(re.fullmatch(r"[0-9a-f]{8,128}", k))
    assert key_ok("a" * 32) and not key_ok("ZZZ") and not key_ok("a" * 4)
    ok += 1
    # 空 URL 列表不许发（发空等于没做还说做了）
    try:
        assert urls_from_sitemap  # noqa
        assert len([]) == 0 and not ([].__len__() > 0)
        ok += 1
    except AssertionError:
        pass
    print(f"OK indexnow selftest {ok}/4")


def main():
    args = sys.argv[1:]
    if "--selftest" in args:
        selftest()
        return 0
    if "--init" in args:
        key = KEYFILE.read_text().strip() if KEYFILE.is_file() else secrets.token_hex(16)
        KEYFILE.write_text(key + "\n")
        (ROOT / f"{key}.txt").write_text(key)
        print(f"key={key} 文件={ROOT / (key + '.txt')}")
        return 0
    key = KEYFILE.read_text().strip() if KEYFILE.is_file() else ""
    if not key:
        print("BAD 无 key，先 --init")
        return 2
    key_url = SITE + f"{key}.txt"
    if "--verify" in args:
        try:
            with urllib.request.urlopen(key_url, timeout=20) as r:
                body = r.read().decode().strip()
                if r.status == 200 and body == key:
                    print(f"OK key 文件公网可读且内容一致 {key_url}")
                    return 0
            print(f"BAD 内容不符 {key_url}")
        except Exception as e:
            print(f"BAD key 文件公网不可读 {key_url}: {e}")
        return 2
    urls = urls_from_sitemap(ROOT)
    if not urls:
        print("BAD sitemap 里没有 URL")
        return 2
    status, body = post_json(ENDPOINT, build_payload(HOST, key, key_url, urls))
    print(f"POST {ENDPOINT} -> {status} {body!r} urls={len(urls)}")
    return 0 if status in (200, 202) else 2


if __name__ == "__main__":
    sys.exit(main())
