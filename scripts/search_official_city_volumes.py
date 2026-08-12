import re
import time
import urllib.parse
import urllib.request
import csv
from pathlib import Path

OUT = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/official_city_volumes")
OUT.mkdir(parents=True, exist_ok=True)

QUERIES = [
    "苏州 废旧动力电池 综合利用量 2025",
    "常州 废旧动力电池 综合利用量 2025",
    "南京 废旧动力电池 综合利用量 2025",
    "宁波 动力电池回收量 2025 官方",
    "宜宾 动力电池回收量 2025 官方",
    "深圳 废旧动力电池 回收量 2025 官方",
    "长沙 动力电池回收量 2025 官方",
    "武汉 动力电池回收量 2025 官方",
    "成都 动力电池回收量 2025 官方",
    "西安 动力电池回收量 2025 官方",
    "郑州 动力电池回收量 2025 官方",
    "合肥 动力电池回收量 2025 官方",
    "site:gov.cn 城市 废旧动力电池综合利用量 2025",
    "site:gov.cn 市工信局 动力电池回收量 吨",
]


def search(query):
    url = "https://www.so.com/s?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse(html, query):
    results = []
    blocks = re.findall(r'<li class="res-list".*?</li>', html, flags=re.S)
    for b in blocks:
        title_m = re.search(r"<h3[^>]*>.*?<a[^>]*>(.*?)</a>", b, flags=re.S)
        url_m = re.search(r'data-mdurl="([^"]+)"', b)
        desc_m = re.search(r'<p class="res-desc">(.*?)</p>', b, flags=re.S)
        if title_m:
            title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
            url = url_m.group(1) if url_m else ""
            desc = re.sub(r"<[^>]+>", "", desc_m.group(1)).strip() if desc_m else ""
            results.append({"query": query, "title": title, "url": url, "desc": desc})
    return results


rows = []
for q in QUERIES:
    try:
        html = search(q)
        res = parse(html, q)
        rows.extend(res[:10])
        print(q, len(res))
        for r in res[:5]:
            print(" -", r["title"][:100])
    except Exception as e:
        print("ERR", q, e)
    time.sleep(0.4)

with open(OUT / "official_city_volume_search.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["query", "title", "url", "desc"])
    writer.writeheader()
    writer.writerows(rows)
print("total", len(rows))
