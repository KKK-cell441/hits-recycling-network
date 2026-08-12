import csv
import re
import subprocess
import tempfile
import urllib.parse
from pathlib import Path

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUT = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/browser_store_ledger_search")
OUT.mkdir(parents=True, exist_ok=True)

QUERIES = [
    "4S店 动力电池回收 台账",
    "动力电池回收 服务网点 台账",
    "新能源汽车动力电池回收 门店 回收量",
    "动力电池回收利用网点 台账",
    "4S店 废旧动力电池 回收记录",
    "动力电池回收 经销商 台账",
    "动力电池回收试点 门店 台账",
    "无锡 动力电池回收 台账",
    "深圳 动力电池回收 台账",
    "淄博 动力电池回收 台账",
    "宜宾 动力电池回收 台账",
]


def chrome_dump(url):
    with tempfile.TemporaryDirectory(prefix="chrome-ledger-") as tmp:
        cmd = [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--dump-dom",
            "--virtual-time-budget=9000",
            "--user-agent=Mozilla/5.0",
            f"--user-data-dir={tmp}",
            url,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=60)
        return res.stdout or res.stderr


def parse(html):
    rows = []
    blocks = re.findall(r'<li class="res-list".*?</li>', html, flags=re.S)
    for b in blocks:
        title_m = re.search(r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>', b, flags=re.S)
        url_m = re.search(r'data-mdurl="([^"]+)"', b)
        desc_m = re.search(r'<p class="res-desc">(.*?)</p>', b, flags=re.S)
        if title_m:
            title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
            url = url_m.group(1) if url_m else ""
            desc = re.sub(r"<[^>]+>", "", desc_m.group(1)).strip() if desc_m else ""
            rows.append({"query": "", "title": title, "url": url, "desc": desc})
    return rows


all_rows = []
for q in QUERIES:
    url = "https://www.so.com/s?q=" + urllib.parse.quote(q)
    try:
        html = chrome_dump(url)
        res = parse(html)
        for r in res[:10]:
            r["query"] = q
            all_rows.append(r)
        print(q, len(res))
    except Exception as e:
        print("ERR", q, e)

with open(OUT / "browser_store_ledger_results.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["query", "title", "url", "desc"])
    writer.writeheader()
    writer.writerows(all_rows)

print("total", len(all_rows))
