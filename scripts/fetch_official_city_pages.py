import re
import time
import urllib.request
from pathlib import Path
import pandas as pd

SRC = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/official_city_volumes/baidu_gov_city_volume_search.csv")
df = pd.read_csv(SRC, encoding="utf-8-sig")

# Selected rows by title fragment.
wanted = [
    "2023年无锡市固体废物污染环境防治信息公告",
    "长沙市工业和信息化局对长沙市政协十三届四次会议第167号提案的",
    "长沙市2024年固体废物污染环境防治信息公告",
    "武汉市2024年固体废物污染环境防治信息公告",
    "宜宾入选四川省新能源汽车动力电池回收利用区域中心建设名单",
    "武汉希冀锂能新能源汽车动力蓄电池回收利用项目备案公示",
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

for title in wanted:
    match = df[df["title"].str.contains(title, na=False)]
    if match.empty:
        print("\nNO ROW", title)
        continue
    row = match.iloc[0]
    link = row["url"]
    print("\n=== TITLE:", row["title"][:100])
    print("BAIDU URL:", link[:120])
    try:
        req = urllib.request.Request(link, headers=headers)
        with urllib.request.urlopen(req, timeout=40) as resp:
            final = resp.geturl()
            raw = resp.read()
        print("FINAL:", final[:200])
        text = None
        for enc in ("utf-8", "gbk", "gb18030"):
            try:
                text = raw.decode(enc, errors="ignore")
                break
            except Exception:
                continue
        if text is None:
            text = raw.decode("utf-8", "ignore")
        clean = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
        clean = re.sub(r"<style.*?</style>", " ", clean, flags=re.S | re.I)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = re.sub(r"\s+", " ", clean)
        hits = re.findall(r".{0,80}(?:电池|回收|综合利用).{0,120}", clean)
        for h in hits[:25]:
            print(" *", h.strip())
    except Exception as e:
        print("ERR", e)
    time.sleep(1.0)
