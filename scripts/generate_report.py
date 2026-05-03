"""
Daily US Stock Market Report Generator
Fetches real market data and uses Claude API for analysis.
"""
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta
import pytz

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ET = pytz.timezone("America/New_York")
NOW = datetime.now(ET)
DATE_STR = NOW.strftime("%Y-%m-%d")
DATE_DISPLAY = NOW.strftime("%B %d, %Y")


def fetch_yahoo(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"Yahoo fetch error for {symbol}: {e}")
        return None


def get_market_data():
    symbols = {
        "S&P 500": "^GSPC",
        "Nasdaq": "^IXIC",
        "Dow Jones": "^DJI",
        "VIX": "^VIX",
        "10Y Treasury": "^TNX",
        "Gold": "GC=F",
        "Oil (WTI)": "CL=F",
        "USD Index": "DX-Y.NYB",
    }
    results = {}
    for name, sym in symbols.items():
        data = fetch_yahoo(sym)
        if data:
            try:
                closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
                closes = [c for c in closes if c is not None]
                if len(closes) >= 2:
                    prev, curr = closes[-2], closes[-1]
                    chg = ((curr - prev) / prev) * 100
                    results[name] = {"price": curr, "change_pct": chg, "symbol": sym}
                elif closes:
                    results[name] = {"price": closes[-1], "change_pct": 0, "symbol": sym}
            except Exception as e:
                print(f"Parse error {name}: {e}")
    return results


def get_sector_etfs():
    sectors = {
        "Technology (XLK)": "XLK",
        "Financials (XLF)": "XLF",
        "Healthcare (XLV)": "XLV",
        "Energy (XLE)": "XLE",
        "Consumer Disc. (XLY)": "XLY",
        "Industrials (XLI)": "XLI",
        "Utilities (XLU)": "XLU",
        "Real Estate (XLRE)": "XLRE",
        "Materials (XLB)": "XLB",
        "AI/Tech (QQQ)": "QQQ",
        "Semiconductors (SOXX)": "SOXX",
        "Nvidia": "NVDA",
        "Meta": "META",
        "Microsoft": "MSFT",
        "Google": "GOOGL",
    }
    results = {}
    for name, sym in sectors.items():
        data = fetch_yahoo(sym)
        if data:
            try:
                closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
                closes = [c for c in closes if c is not None]
                if len(closes) >= 2:
                    prev, curr = closes[-2], closes[-1]
                    chg = ((curr - prev) / prev) * 100
                    results[name] = {"price": curr, "change_pct": chg}
                elif closes:
                    results[name] = {"price": closes[-1], "change_pct": 0}
            except Exception as e:
                print(f"Parse error {name}: {e}")
    return results


def ask_claude(prompt):
    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read().decode())
            return result["content"][0]["text"]
    except Exception as e:
        print(f"Claude error: {e}")
        return "（分析暂不可用）"


def fetch_news_rss(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            content = r.read().decode("utf-8", errors="ignore")
        items = []
        import re
        titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", content)
        descs = re.findall(r"<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>", content)
        for i, t in enumerate(titles[1:10], 0):
            title = (t[0] or t[1]).strip()
            desc = ""
            if i < len(descs):
                desc = (descs[i][0] or descs[i][1]).strip()[:200]
            if title:
                items.append(f"- {title}: {desc}")
        return "\n".join(items)
    except Exception as e:
        return ""


def get_news_summary():
    feeds = [
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://www.marketwatch.com/rss/topstories",
    ]
    news_text = ""
    for feed in feeds:
        result = fetch_news_rss(feed)
        if result:
            news_text += result + "\n"
    return news_text.strip()


def build_market_context(market_data, sector_data):
    lines = ["市場指數:"]
    for name, d in market_data.items():
        arrow = "▲" if d["change_pct"] >= 0 else "▼"
        lines.append(f"  {name}: {d['price']:.2f} ({arrow}{abs(d['change_pct']):.2f}%)")
    lines.append("\n板塊 ETF / 個股:")
    for name, d in sector_data.items():
        arrow = "▲" if d["change_pct"] >= 0 else "▼"
        lines.append(f"  {name}: {d['price']:.2f} ({arrow}{abs(d['change_pct']):.2f}%)")
    return "\n".join(lines)


def generate_report():
    print(f"Generating report for {DATE_STR}...")

    market_data = get_market_data()
    sector_data = get_sector_etfs()
    news_text = get_news_summary()
    market_ctx = build_market_context(market_data, sector_data)

    # --- Analysis prompts ---
    sector_analysis = ask_claude(f"""
今天是 {DATE_DISPLAY}，以下是美股市場數據：
{market_ctx}

請分析：
1. 今日市場整體走勢（多空判斷）
2. 表現最強的3個板塊及利多原因
3. 表現最弱的3個板塊及利空原因
4. 風險指標（VIX、10Y殖利率）解讀

用繁體中文，條列式，簡潔清楚。每點不超過2句話。
""")

    news_section = ("最新財經新聞：\n" + news_text[:1000]) if news_text else ""
    ai_analysis = ask_claude(f"""
今天是 {DATE_DISPLAY}，AI/科技板塊數據：
{market_ctx}

{news_section}

請分析：
1. AI板塊今日表現（NVDA、MSFT、META、GOOGL、SOXX）
2. 影響AI股的主要消息或催化劑
3. 短期AI板塊展望（利多/利空）

用繁體中文，條列式，重點突出。
""")

    news_section2 = ("相關新聞：\n" + news_text[:800]) if news_text else ""
    macro_analysis = ask_claude(f"""
今天是 {DATE_DISPLAY}，宏觀數據：
{market_ctx}

{news_section2}

請分析：
1. 今日關鍵金融數據解讀（10Y殖利率、VIX、美元指數）
2. 聯準會政策走向及利率預期
3. 今日是否有重要人士發言影響市場（Fed官員/財長等），利多還是利空？
4. 黃金、石油走勢及含義

用繁體中文，條列式，每點不超過2句話。
""")

    return {
        "date": DATE_DISPLAY,
        "date_raw": DATE_STR,
        "market_data": market_data,
        "sector_data": sector_data,
        "sector_analysis": sector_analysis,
        "ai_analysis": ai_analysis,
        "macro_analysis": macro_analysis,
    }


def render_html(report):
    def badge(chg):
        if chg > 1:
            return f'<span class="badge up">▲ {chg:.2f}%</span>'
        elif chg > 0:
            return f'<span class="badge up-sm">▲ {chg:.2f}%</span>'
        elif chg < -1:
            return f'<span class="badge down">▼ {abs(chg):.2f}%</span>'
        elif chg < 0:
            return f'<span class="badge down-sm">▼ {abs(chg):.2f}%</span>'
        else:
            return f'<span class="badge flat">— {chg:.2f}%</span>'

    market_rows = ""
    for name, d in report["market_data"].items():
        market_rows += f"""
        <div class="data-row">
            <span class="label">{name}</span>
            <span class="price">{d['price']:.2f}</span>
            {badge(d['change_pct'])}
        </div>"""

    sector_rows = ""
    sorted_sectors = sorted(report["sector_data"].items(), key=lambda x: x[1]["change_pct"], reverse=True)
    for name, d in sorted_sectors:
        sector_rows += f"""
        <div class="data-row">
            <span class="label">{name}</span>
            <span class="price">{d['price']:.2f}</span>
            {badge(d['change_pct'])}
        </div>"""

    def md_to_html(text):
        import re
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        lines = text.strip().split("\n")
        out = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("- ") or line.startswith("• "):
                out.append(f"<li>{line[2:]}</li>")
            elif line[0].isdigit() and ". " in line[:4]:
                out.append(f"<li>{line[line.index('.')+2:]}</li>")
            else:
                out.append(f"<p>{line}</p>")
        html = "\n".join(out)
        html = re.sub(r'(<li>.*</li>\n?)+', lambda m: f'<ul>{m.group()}</ul>', html)
        return html

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>美股日報 {report['date']}</title>
<style>
  :root {{
    --bg: #0d1117;
    --card: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --up: #3fb950;
    --down: #f85149;
    --accent: #58a6ff;
    --gold: #d29922;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; }}
  .header {{ background: linear-gradient(135deg, #1c2128, #21262d); border-bottom: 1px solid var(--border); padding: 24px; text-align: center; }}
  .header h1 {{ font-size: 1.8rem; color: var(--accent); }}
  .header .date {{ color: var(--muted); margin-top: 4px; font-size: 0.9rem; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 24px 16px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  @media (max-width: 768px) {{ .container {{ grid-template-columns: 1fr; }} }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }}
  .card.full {{ grid-column: 1 / -1; }}
  .card h2 {{ font-size: 1rem; color: var(--accent); margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}
  .data-row {{ display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border); }}
  .data-row:last-child {{ border-bottom: none; }}
  .label {{ color: var(--muted); font-size: 0.85rem; flex: 1; }}
  .price {{ font-weight: 600; margin-right: 12px; min-width: 80px; text-align: right; }}
  .badge {{ padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; min-width: 80px; text-align: center; }}
  .badge.up {{ background: rgba(63,185,80,0.15); color: var(--up); }}
  .badge.up-sm {{ background: rgba(63,185,80,0.08); color: var(--up); }}
  .badge.down {{ background: rgba(248,81,73,0.15); color: var(--down); }}
  .badge.down-sm {{ background: rgba(248,81,73,0.08); color: var(--down); }}
  .badge.flat {{ background: rgba(139,148,158,0.15); color: var(--muted); }}
  .analysis {{ color: var(--text); font-size: 0.9rem; }}
  .analysis p {{ margin-bottom: 8px; }}
  .analysis ul {{ padding-left: 20px; }}
  .analysis li {{ margin-bottom: 6px; }}
  .analysis strong {{ color: var(--gold); }}
  .footer {{ text-align: center; padding: 24px; color: var(--muted); font-size: 0.8rem; }}
  .update-time {{ color: var(--muted); font-size: 0.75rem; margin-top: 4px; }}
</style>
</head>
<body>
<div class="header">
  <h1>📈 美股每日資訊站</h1>
  <div class="date">更新日期：{report['date']} · 美東時間</div>
</div>
<div class="container">

  <div class="card">
    <h2>📊 大盤指數</h2>
    {market_rows}
  </div>

  <div class="card">
    <h2>🔥 板塊 & AI個股</h2>
    {sector_rows}
  </div>

  <div class="card full">
    <h2>📉 板塊波動分析 · 利多 / 利空</h2>
    <div class="analysis">{md_to_html(report['sector_analysis'])}</div>
  </div>

  <div class="card full">
    <h2>🤖 AI 板塊深度分析</h2>
    <div class="analysis">{md_to_html(report['ai_analysis'])}</div>
  </div>

  <div class="card full">
    <h2>🏦 總體經濟 · 金融數據 · 重要言論</h2>
    <div class="analysis">{md_to_html(report['macro_analysis'])}</div>
  </div>

</div>
<div class="footer">
  資料來源：Yahoo Finance · 分析：Claude AI<br>
  每日美東時間開盤後自動更新 · 僅供參考，不構成投資建議
</div>
</body>
</html>"""
    return html


if __name__ == "__main__":
    report = generate_report()
    html = render_html(report)
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report saved to docs/index.html")
