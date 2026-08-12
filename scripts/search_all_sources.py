import csv
import re
import subprocess
import tempfile
import urllib.parse
from pathlib import Path

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUT = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/all_sources_search")
OUT.mkdir(parents=True, exist_ok=True)

QUERIES = [
    "江苏省 动力电池回收量 2025 吨",
    "广东省 动力电池回收量 2025 吨",
    "山东省 动力电池回收量 2025 吨",
    "四川省 动力电池回收量 2025 吨",
    "深圳 动力电池回收 工信局 2025 吨",
    "广州 动力电池回收 工信局 2025 吨",
    "南京 动力电池回收 工信局 2025 吨",
    "济南 动力电池回收 工信局 2025 吨",
    "淄博 动力电池回收 工信局 2025 吨",
    "绵阳 动力电池回收 工信局 2025 吨",
    "深圳 固体废物污染环境防治信息公告 动力电池 2025",
    "广州 固体废物污染环境防治信息公告 动力电池 2025",
    "南京 固体废物污染环境防治信息公告 动力电池 2025",
    "济南 固体废物污染环境防治信息公告 动力电池 2025",
    "淄博 固体废物污染环境防治信息公告 动力电池 2025",
    "绵阳 固体废物污染环境防治信息公告 动力电池 2025",
    "比亚迪 2025 电池回收量 回收量",
    "蔚来 ESG 电池回收量 2025",
    "小鹏 ESG 电池回收量 2025",
    "吉利 动力电池回收 2025 回收量",
    "上汽 动力电池回收 2025 回收量",
    "广汽 动力电池回收 2025 回收量",
    "特斯拉 2025 impact report battery recycling",
    "深圳市政府信息依申请公开 生态环境局",
    "山东政府信息依申请公开 动力电池回收",
    "广州政府信息依申请公开 动力电池回收",
    "南京政府信息依申请公开 动力电池回收",
    "新能源汽车国家监测与动力电池回收利用溯源综合管理平台",
    "动力电池溯源平台 登录",
]


def chrome_dump(url):
    with tempfile.TemporaryDirectory(prefix="chrome-all-") as tmp:
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


def parse(html, query):
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
            rows.append({"query": query, "title": title, "url": url, "desc": desc})
    return rows


rows = []
for q in QUERIES:
    url = "https://www.so.com/s?q=" + urllib.parse.quote(q)
    try:
        res = parse(chrome_dump(url), q)
        rows.extend(res[:8])
        print(q, len(res))
    except Exception as e:
        print("ERR", q, e)

with open(OUT / "all_sources_search_results.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["query", "title", "url", "desc"])
    writer.writeheader()
    writer.writerows(rows)
print("total", len(rows))
