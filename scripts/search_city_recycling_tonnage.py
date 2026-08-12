import re
import time
import urllib.parse
import urllib.request
import csv
from pathlib import Path

OUT = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/public_city_search")
QUERIES = [
    "深圳 动力电池回收 万吨 2025",
    "无锡 动力电池回收 万吨 2025",
    "淄博 动力电池回收 万吨 2025",
    "宜宾 动力电池回收 万吨 2025",
    "深圳 废旧动力电池 回收量",
    "无锡 废旧动力电池 回收量",
    "淄博 废旧动力电池 回收量",
    "宜宾 废旧动力电池 回收量",
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
            results.append({"query": query, "title": title, "url": url, "desc": desc})
    return results


rows = []
for q in QUERIES:
    try:
        res = parse(search(q))
        rows.extend(res[:10])
        print(q, len(res))
    except Exception as e:
        print("ERR", q, e)
    time.sleep(0.4)

with open(OUT / "city_recycling_tonnage_search.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["query", "title", "url", "desc"])
    writer.writeheader()
    writer.writerows(rows)
print("total", len(rows))
