import re
import time
import urllib.parse
import urllib.request
import csv
from pathlib import Path

OUT = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/public_city_search")
OUT.mkdir(parents=True, exist_ok=True)

QUERIES = [
    "深圳市 动力电池回收 处理量 生态环境局",
    "无锡市 动力电池回收 处理量",
    "淄博市 动力电池回收 处理量",
    "宜宾市 动力电池回收 处理量",
    "site:gov.cn 深圳市 动力电池回收 处理量",
    "site:gov.cn 无锡市 动力电池回收 处理量",
    "site:gov.cn 淄博市 动力电池回收 处理量",
    "site:gov.cn 宜宾市 动力电池回收 处理量",
]


def search(query):
    url = "https://www.so.com/s?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse(html):
    results = []
    blocks = re.findall(r'<li class="res-list".*?</li>', html, flags=re.S)
    for b in blocks:
        title_m = re.search(r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>', b, flags=re.S)
        url_m = re.search(r'data-mdurl="([^"]+)"', b)
        desc_m = re.search(r'<p class="res-desc">(.*?)</p>', b, flags=re.S)
        if title_m:
            title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
            url = url_m.group(1) if url_m else ""
            desc = re.sub(r"<[^>]+>", "", desc_m.group(1)).strip() if desc_m else ""
            results.append({"query": "", "title": title, "url": url, "desc": desc})
    return results


rows = []
for q in QUERIES:
    try:
        html = search(q)
        res = parse(html)
        for r in res[:10]:
            r["query"] = q
            rows.append(r)
        print(q, len(res))
    except Exception as e:
        print("ERR", q, e)
    time.sleep(0.5)

with open(OUT / "city_recycling_search_results.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["query", "title", "url", "desc"])
    writer.writeheader()
    writer.writerows(rows)

print("total", len(rows))
