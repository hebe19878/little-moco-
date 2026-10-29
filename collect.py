import feedparser, json, os, re, html, requests
from datetime import datetime, timezone, timedelta

TODAY = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
OUT = "docs/" + TODAY
os.makedirs(OUT, exist_ok=True)

# ===== 你以后只需要改这里：来源列表 =====
FEEDS = {
    "Vogue": "https://www.vogue.com/feed/rss",
    "Harper's Bazaar": "https://www.harpersbazaar.com/rss/all.xml/",
    "Hypebeast": "https://hypebeast.com/feed",
    "Highsnobiety": "https://www.highsnobiety.com/feed/",
    "WWD": "https://wwd.com/feed/",
    "Fashionista": "https://fashionista.com/.rss/full/",
    # Pinterest 公开画板格式（把用户名和画板名换成真实的）：
    # "Pinterest-某画板": "https://www.pinterest.com/用户名/画板名.rss",
}

# 分类：按顺序匹配，命中第一个就归入该文件夹
CATS = {
    "婴童": ["kids", "kidswear", "children", "childrenswear", "baby", "toddler", "mini-me"],
    "奢侈品新品": ["gucci", "prada", "chanel", "dior", "louis vuitton", "hermes", "hermès", "loewe",
                "miu miu", "balenciaga", "bottega veneta", "celine", "saint laurent", "fendi", "burberry", "jacquemus"],
    "秀场发布": ["runway", "fashion week", "ready-to-wear", "collection", "spring/summer", "fall/winter", "resort"],
    "面料工艺": ["fabric", "textile", "material", "wool", "cashmere", "denim", "knit", "linen",
             "corduroy", "velvet", "tweed", "recycled", "organic cotton", "technical"],
    "色彩": ["color", "colour", "colors", "palette", "pantone", "burgundy", "butter yellow", "chocolate brown"],
    "穿搭街拍": ["street style", "outfit", "how to wear", "styling", "layering"],
    "流行单品": ["trend", "must-have", "bag", "shoe", "coat", "jacket", "dress", "skirt",
             "sneaker", "loafer", "trench", "vest", "cardigan", "sweater"],
}
# 禁区过滤：命中即丢弃
BLOCK = ["lingerie", "bikini", "sexy", "thong", "underwear", "topless", "micro mini", "sheer",
         "disney", "licensed", "cartoon", "neon"]


def hit(text, words):
    return any(re.search(r"\b" + re.escape(w) + r"s?\b", text) for w in words)


def get_image(e):
    for m in list(e.get("media_content", [])) + list(e.get("media_thumbnail", [])):
        if m.get("url"):
            return m["url"]
    for l in e.get("links", []):
        if l.get("type", "").startswith("image"):
            return l.get("href", "")
    text = e.get("summary", "") + "".join(c.get("value", "") for c in e.get("content", []))
    m = re.search(r'<img[^>]+src="([^"]+)"', text)
    return m.group(1) if m else ""


SEEN = "docs/seen.json"
seen = set(json.load(open(SEEN, encoding="utf-8"))) if os.path.exists(SEEN) else set()

items = []
for src, url in FEEDS.items():
    try:
        d = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        for e in d.entries[:30]:
            link = e.get("link", "")
            if not link or link in seen:
                continue
            title = html.unescape(e.get("title", ""))
            summ = re.sub("<[^>]+>", "", html.unescape(e.get("summary", "")))[:200]
            blob = (title + " " + summ).lower()
            if hit(blob, BLOCK):
                continue
            cat = next((c for c, ks in CATS.items() if hit(blob, ks)), "话题其他")
            items.append({"source": src, "title": title, "summary": summ,
                          "link": link, "image": get_image(e), "category": cat})
            seen.add(link)
    except Exception as ex:
        print("来源失败，已跳过：", src, ex)

json.dump(sorted(seen), open(SEEN, "w", encoding="utf-8"))

by_cat = {}
for it in items:
    by_cat.setdefault(it["category"], []).append(it)

for cat, lst in by_cat.items():
    os.makedirs(OUT + "/" + cat, exist_ok=True)
    json.dump(lst, open(OUT + "/" + cat + "/items.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

h = ['<html><head><meta charset="utf-8"><meta name="referrer" content="no-referrer">'
     '<meta name="viewport" content="width=device-width,initial-scale=1">'
     '<style>body{font-family:sans-serif;margin:12px}img{width:100%;border-radius:8px}h3{margin-top:24px}</style></head><body>']
h.append("<h2>%s 趋势日报</h2>" % TODAY)
for cat, lst in by_cat.items():
    h.append("<h3>%s（%d）</h3>" % (cat, len(lst)))
    for it in lst:
        if it["image"]:
            h.append('<img src="%s">' % it["image"])
        h.append('<p><a href="%s">%s</a><br><small>%s</small></p>' % (it["link"], it["title"], it["source"]))
h.append("</body></html>")
open(OUT + "/index.html", "w", encoding="utf-8").write("\n".join(h))

owner, repo = os.environ.get("GITHUB_REPOSITORY", "a/b").split("/")
page = "https://%s.github.io/%s/%s/" % (owner, repo, TODAY)
lines = []
for cat, lst in by_cat.items():
    lines.append("<b>%s（%d）</b>" % (cat, len(lst)))
    for it in lst[:3]:
        lines.append("· " + it["title"])
if items:
    content = '<a href="%s">👉 点开看今日完整图文页</a><br><br>' % page + "<br>".join(lines)
else:
    content = "今天没有抓到新内容"
requests.post("https://www.pushplus.plus/send", json={
    "token": os.environ["PUSHPLUS_TOKEN"],
    "title": TODAY + " 童装趋势日报",
    "content": content, "template": "html"})
