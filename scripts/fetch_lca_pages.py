import re
import time
import urllib.request
from pathlib import Path
import pandas as pd

SRC = Path(r"C:/Users/17302/Documents/Codex/2026-07-31/yi/work/lca_search/lca_search_results.csv")
df = pd.read_csv(SRC, encoding="utf-8-sig")
wanted = [
    "Impact of electric vehicle battery recycling on reducing raw",
    "易碳大咖说",
    "Nature Communications | 基于LCA辅助的层次化设计",
    "深圳国际研究生院张璇",
    "动力蓄电池碳减排分析",
]
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}

for title in wanted:
    match = df[df["title"].str.contains(title, na=False)]
    if match.empty:
        print("\nNO ROW", title)
        continue
    row = match.iloc[0]
    link = row["url"]
    print("\n=== TITLE:", row["title"][:100])
    try:
        req = urllib.request.Request(link, headers=headers)
        with urllib.request.urlopen(req, timeout=40) as resp:
            raw = resp.read()
        text = raw.decode("utf-8", "ignore")
        clean = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
        clean = re.sub(r"<style.*?</style>", " ", clean, flags=re.S | re.I)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = re.sub(r"\s+", " ", clean)
        hits = re.findall(r".{0,100}(?:CO2|GWP|kg CO|减排|碳足迹|回收).{0,180}", clean)
        for h in hits[:30]:
            print(" *", h.strip())
    except Exception as e:
        print("ERR", e)
    time.sleep(1.0)
