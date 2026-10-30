import json, os, re, sys, requests
from collections import Counter
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
today = datetime.now(TZ).date()
FMT = "%Y-%m-%d"

# ===== 词表：想增加关注的词，照格式往里加就行 =====
# 格式：  "中文名": ["英文写法1", "英文写法2"],
GROUPS = {
    "色彩": {
        "奶油黄": ["butter yellow", "buttery yellow"], "巧克力棕": ["chocolate brown", "espresso brown"],
        "酒红": ["burgundy", "oxblood", "wine red"], "奶油白": ["cream", "ivory", "off-white"],
        "鼠尾草绿": ["sage green", "sage"], "橄榄绿": ["olive"], "藏蓝": ["navy"],
        "粉色": ["pink", "blush"], "薰衣草紫": ["lavender", "lilac"], "钴蓝": ["cobalt"],
        "驼色": ["camel", "tan", "beige"], "灰色": ["grey", "gray", "charcoal"], "银色": ["silver", "metallic"],
        "黄色": ["yellow"], "绿色": ["green"], "蓝色": ["blue"], "棕色": ["brown"], "红色": ["red"],
    },
    "面料": {
        "牛仔": ["denim"], "针织": ["knit", "knitwear", "knitted"], "羊毛": ["wool"], "羊绒": ["cashmere"],
        "灯芯绒": ["corduroy"], "丝绒": ["velvet"], "粗花呢": ["tweed", "bouclé", "boucle"],
        "亚麻": ["linen"], "皮革": ["leather", "suede"], "缎面": ["satin", "silk"], "蕾丝": ["lace"],
        "薄纱": ["tulle", "organza"], "绗缝": ["quilted", "quilting"], "羊羔绒": ["shearling", "fleece", "sherpa"],
        "尼龙/技术面料": ["nylon", "technical fabric"], "有机棉/再生": ["organic cotton", "recycled"],
    },
    "单品廓形": {
        "乐福鞋": ["loafer"], "玛丽珍": ["mary jane"], "芭蕾鞋": ["ballet flat"], "运动鞋": ["sneaker", "trainer"],
        "靴子": ["boot"], "风衣": ["trench"], "大衣": ["overcoat", "coat"], "夹克": ["jacket", "bomber"],
        "西装": ["blazer", "tailoring"], "开衫": ["cardigan"], "针织衫": ["sweater", "jumper"],
        "马甲": ["vest", "gilet"], "羽绒/棉服": ["puffer", "down jacket"], "连衣裙": ["dress"],
        "半裙": ["skirt"], "阔腿裤": ["wide-leg", "wide leg"], "工装口袋": ["cargo", "utility"],
        "褶裥": ["pleat", "pleated"], "蝴蝶结": ["bow"], "条纹": ["stripe", "striped"],
        "格纹": ["plaid", "checked", "gingham", "tartan"], "波点": ["polka dot"], "花卉": ["floral"],
        "围巾": ["scarf"], "包袋": ["handbag", "tote", "bag"], "廓形宽松": ["oversized", "oversize"],
    },
    "风格": {
        "静奢": ["quiet luxury"], "学院风": ["preppy", "ivy"], "山系户外": ["gorpcore", "outdoor"],
        "波西米亚": ["boho", "bohemian"], "极简": ["minimalist", "minimalism", "minimal"],
        "复古": ["vintage", "retro"], "工装风": ["workwear"], "运动风": ["sporty", "athleisure"],
        "浪漫": ["romantic", "romance"], "芭蕾风": ["balletcore"], "无性别": ["gender-neutral", "gender neutral", "genderless"],
        "可持续": ["sustainable", "eco-friendly"], "叠穿": ["layering", "layered"], "西部": ["western"],
        "怀旧": ["nostalgic", "nostalgia"], "舒适": ["cozy", "comfort"], "趣味": ["playful", "whimsical"],
    },
    "品牌": {b: [b.lower()] for b in [
        "Prada", "Miu Miu", "Gucci", "Chanel", "Dior", "Louis Vuitton", "Hermès", "Loewe", "Balenciaga",
        "Bottega Veneta", "Celine", "Saint Laurent", "Fendi", "Burberry", "Jacquemus", "Zara", "Uniqlo"]},
}
GROUPS["品牌"]["Hermès"] = ["hermès", "hermes"]
TREND_GROUPS = ["色彩", "面料", "单品廓形", "风格"]


def month_range(d):
    first = d.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return first, nxt - timedelta(days=1)


def period(mode, todate):
    if mode == "week":
        if todate:
            return today - timedelta(days=today.weekday()), today
        s = today - timedelta(days=today.weekday() + 7)
        return s, s + timedelta(days=6)
    if mode == "month":
        first = today.replace(day=1)
        if todate:
            return first, today
        e = first - timedelta(days=1)
        return e.replace(day=1), e
    qm = (today.month - 1) // 3 * 3 + 1
    first = today.replace(month=qm, day=1)
    if todate:
        return first, today
    e = first - timedelta(days=1)
    return e.replace(month=(e.month - 1) // 3 * 3 + 1, day=1), e


def load(s, e):
    seen, arts = set(), []
    d = s
    while d <= e:
        ds = d.strftime(FMT)
        base = os.path.join("docs", ds)
        if os.path.isdir(base):
            for cat in sorted(os.listdir(base)):
                p = os.path.join(base, cat, "items.json")
                if os.path.isfile(p):
                    try:
                        for it in json.load(open(p, encoding="utf-8")):
                            link = it.get("link")
                            if not link or link in seen:
                                continue
                            seen.add(link)
                            it["date"] = ds
                            it["category"] = it.get("category") or cat
                            arts.append(it)
                    except Exception as ex:
                        print("读取失败", p, ex)
        d += timedelta(days=1)
    return arts


def count(arts):
    res = {g: {} for g in GROUPS}
    for a in arts:
        blob = (a.get("title", "") + " " + a.get("summary", "")).lower()
        blob = blob.replace("red carpet", "").replace("black friday", "")
        for g, terms in GROUPS.items():
            for label, pats in terms.items():
                if any(re.search(r"\b" + re.escape(p) + r"(?:s|es)?\b", blob) for p in pats):
                    res[g].setdefault(label, []).append(a)
    return res


def flat(res):
    return {lab: len(ar) for g in TREND_GROUPS for lab, ar in res[g].items()}


def classify(cur, cn, prev, pn):
    out = {"上升": [], "稳定": [], "衰退": [], "新出现": []}
    for lab in set(cur) | set(prev):
        c, p = cur.get(lab, 0), prev.get(lab, 0)
        if max(c, p) < 3:
            continue
        cs = c / cn * 100 if cn else 0
        ps = p / pn * 100 if pn else 0
        if p == 0:
            out["新出现"].append((lab, ps, cs))
            continue
        r = cs / ps if ps else 99
        key = "上升" if r >= 1.3 else "衰退" if r <= 0.7 else "稳定"
        out[key].append((lab, ps, cs))
    for k in out:
        out[k].sort(key=lambda x: -x[2])
    return out


def analyze(arts):
    res = count(arts)
    tops = {g: sorted(((l, len(a)) for l, a in res[g].items()), key=lambda x: -x[1])[:5] for g in GROUPS}
    overall = sorted(((l, g, len(a), a) for g in TREND_GROUPS for l, a in res[g].items()), key=lambda x: -x[2])
    return {"res": res, "tops": tops, "overall": overall, "cats": Counter(a["category"] for a in arts)}


def clean(t):
    return t.replace("[", "(").replace("]", ")")[:60]


def fmt_trend(trend, basis):
    L = ["### 趋势变化", basis]
    for k in ["上升", "稳定", "衰退", "新出现"]:
        if trend[k]:
            L.append("**%s**：" % k + "、".join("%s(%.0f%%→%.0f%%)" % (l, p, c) for l, p, c in trend[k][:6]))
    return L


def build_md(title, n, days, R, trend, basis, traj):
    L = ["## " + title, "共 %d 篇，覆盖 %d 天" % (n, days), "", "### 🔥 重复出现最多的趋势"]
    for i, (lab, g, c, ar) in enumerate(R["overall"][:3], 1):
        L.append("%d. **%s**（%s）%d 篇" % (i, lab, g, c))
        for a in ar[:2]:
            L.append("   - [%s](%s)" % (clean(a["title"]), a["link"]))
    L += ["", "### 各类别热度"]
    mx = max(R["cats"].values())
    for cat, c in R["cats"].most_common():
        L.append("%s %s %d" % (cat, "█" * max(1, round(c / mx * 10)), c))
    for g in GROUPS:
        if R["tops"][g]:
            L += ["", "### %s TOP5" % g, " · ".join("%s %d" % x for x in R["tops"][g])]
    if trend:
        L.append("")
        L += fmt_trend(trend, basis)
    elif basis:
        L += ["", "### 趋势变化", basis]
    if traj:
        L += ["", "### 三个月走势（占比）"]
        for lab, shares in traj:
            L.append("%s：%s" % (lab, " → ".join("%.0f%%" % x for x in shares)))
    return "\n".join(L)


def build_html(title, n, days, R, trend, basis, traj):
    h = ['<html><head><meta charset="utf-8"><meta name="referrer" content="no-referrer">'
         '<meta name="viewport" content="width=device-width,initial-scale=1">'
         '<style>body{font-family:sans-serif;margin:12px;line-height:1.6}img{width:48%;border-radius:8px;margin:1%}'
         'h3{margin-top:24px}</style></head><body>']
    h.append("<h2>%s</h2><p>共 %d 篇，覆盖 %d 天</p>" % (title, n, days))
    h.append("<h3>重复出现最多的趋势（附图）</h3>")
    for lab, g, c, ar in R["overall"][:8]:
        h.append("<h4>%s（%s）%d 篇</h4>" % (lab, g, c))
        for a in [x for x in ar if x.get("image")][:4]:
            h.append('<a href="%s"><img src="%s"></a>' % (a["link"], a["image"]))
        for a in ar[:3]:
            h.append('<div><a href="%s">%s</a> <small>%s</small></div>' % (a["link"], a["title"], a.get("source", "")))
    h.append("<h3>各类别热度</h3>")
    for cat, c in R["cats"].most_common():
        h.append("<div>%s：%d</div>" % (cat, c))
    for g in GROUPS:
        if R["tops"][g]:
            h.append("<h3>%s TOP5</h3><div>%s</div>" % (g, " · ".join("%s %d" % x for x in R["tops"][g])))
    if trend:
        h.append("<h3>趋势变化</h3><div>%s</div>" % basis)
        for k in ["上升", "稳定", "衰退", "新出现"]:
            if trend[k]:
                h.append("<p><b>%s</b>：%s</p>" % (k, "、".join("%s(%.0f%%→%.0f%%)" % x for x in trend[k][:10])))
    if traj:
        h.append("<h3>三个月走势（占比）</h3>")
        for lab, shares in traj:
            h.append("<div>%s：%s</div>" % (lab, " → ".join("%.0f%%" % x for x in shares)))
    h.append("</body></html>")
    return "\n".join(h)


def push(title, content):
    tok = os.environ.get("PUSHPLUS_TOKEN")
    if not tok:
        print("未设置 PUSHPLUS_TOKEN，跳过推送")
        return
    requests.post("https://www.pushplus.plus/send", json={
        "token": tok, "title": title, "content": content, "template": "markdown"})


def run(mode, todate):
    s, e = period(mode, todate)
    arts = load(s, e)
    name = {"week": "周报", "month": "月报", "quarter": "季报"}[mode]
    if mode == "week":
        iso = s.isocalendar()
        label = "%d-W%02d" % (iso[0], iso[1])
    elif mode == "month":
        label = s.strftime("%Y-%m")
    else:
        label = "%d-Q%d" % (s.year, (s.month - 1) // 3 + 1)
    if todate:
        label += "-至今"
    title = "童装趋势%s %s ~ %s" % (name, s.strftime(FMT), e.strftime(FMT))
    if not arts:
        push(title, "没有找到数据：docs 文件夹下 %s ~ %s 没有 items.json。" % (s, e))
        print("无数据", s, e)
        return
    days = len({a["date"] for a in arts})
    R = analyze(arts)
    trend, basis, traj = None, "", None

    if mode == "month":
        e2 = s - timedelta(days=1)
        parts = load(e2.replace(day=1), e2)
        if len(parts) >= 30:
            trend = classify(flat(R["res"]), len(arts), flat(count(parts)), len(parts))
            basis = "对比基准：上个月（%d 篇），括号内为占该期文章的百分比（上月→本月）" % len(parts)
        else:
            mid = (s + timedelta(days=((e - s).days + 1) // 2)).strftime(FMT)
            a1 = [a for a in arts if a["date"] < mid]
            a2 = [a for a in arts if a["date"] >= mid]
            if len(a1) >= 10 and len(a2) >= 10:
                trend = classify(flat(count(a2)), len(a2), flat(count(a1)), len(a1))
                basis = "上月数据不足，改为本月后半 vs 前半（百分比：前半→后半）"
            else:
                basis = "数据不足，暂无法判断趋势变化（至少需要两周数据）"
    elif mode == "quarter":
        ms, d = [], s
        for _ in range(3):
            a, b = month_range(d)
            ms.append(load(a, min(b, e)))
            d = b + timedelta(days=1)
        if len(ms[0]) >= 10 and len(ms[2]) >= 10:
            trend = classify(flat(count(ms[2])), len(ms[2]), flat(count(ms[0])), len(ms[0]))
            basis = "对比基准：季度第一个月 vs 第三个月（百分比：首月→末月）"
            cnts = [flat(count(m)) for m in ms]
            traj = []
            for lab, g, c, ar in R["overall"][:8]:
                traj.append((lab, [cnts[i].get(lab, 0) / len(ms[i]) * 100 if ms[i] else 0 for i in range(3)]))
        else:
            basis = "数据不足，暂无法判断季度走势（首末月各需至少 10 篇）"

    md = build_md(title, len(arts), days, R, trend, basis, traj)
    page = build_html(title, len(arts), days, R, trend, basis, traj)
    os.makedirs("docs/summaries", exist_ok=True)
    open("docs/summaries/%s.md" % label, "w", encoding="utf-8").write(md)
    open("docs/summaries/%s.html" % label, "w", encoding="utf-8").write(page)
    owner, repo = os.environ.get("GITHUB_REPOSITORY", "a/b").split("/")
    url = "https://%s.github.io/%s/summaries/%s.html" % (owner, repo, label)
    push(title, md + "\n\n[👉 查看带图完整页](%s)" % url)
    print("完成", label, len(arts), "篇")


mode = os.environ.get("MODE", "").strip()
todate = os.environ.get("TODATE", "").strip().lower() == "true"
jobs = []
if mode in ("week", "month", "quarter"):
    jobs.append((mode, todate))
else:
    if today.weekday() == 0:
        jobs.append(("week", False))
    if today.day == 1:
        jobs.append(("month", False))
        if today.month in (1, 4, 7, 10):
            jobs.append(("quarter", False))
if not jobs:
    print("今天不是汇总日，什么都不发")
    sys.exit(0)
for m, t in jobs:
    run(m, t)
