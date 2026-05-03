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
    lines = ["市场指数:"]
    for name, d in market_data.items():
        arrow = "▲" if d["change_pct"] >= 0 else "▼"
        lines.append(f"  {name}: {d['price']:.2f} ({arrow}{abs(d['change_pct']):.2f}%)")
    lines.append("\n板块 ETF / 个股:")
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
    has_data = len(market_data) > 0

    sector_analysis = ask_claude(f"""
今天是 {DATE_DISPLAY}，以下是美股市场实时数据：
{market_ctx}

{"注意：以上是真实市场数据，请基于数据进行分析。" if has_data else "注意：今日市场数据暂时无法获取，请根据近期市场趋势给出分析参考。"}

请用简体中文分析以下内容（条列式，每点1-2句话）：
1. 今日大盘整体走势判断（多/空/震荡），给出核心理由
2. 今日表现最强的3个板块，说明利好原因
3. 今日表现最弱的3个板块，说明利空原因
4. VIX恐慌指数和10年期美债收益率的市场信号解读
""")

    news_section = ("最新财经新闻：\n" + news_text[:1000]) if news_text else ""
    ai_analysis = ask_claude(f"""
今天是 {DATE_DISPLAY}，AI/科技板块数据：
{market_ctx}

{news_section}

{"注意：以上是真实市场数据。" if has_data else "注意：今日数据暂时无法获取，请根据近期AI板块趋势给出参考分析。"}

请用简体中文分析以下内容（条列式）：
1. 今日AI板块整体表现（NVDA、MSFT、META、GOOGL、SOXX），哪些涨哪些跌
2. 今日影响AI股的主要消息或催化剂（产品发布、财报、政策、竞争动态等）
3. AI板块短期展望：利多因素 vs 利空因素
4. 重点关注个股提示
""")

    news_section2 = ("相关新闻：\n" + news_text[:800]) if news_text else ""
    macro_analysis = ask_claude(f"""
今天是 {DATE_DISPLAY}，宏观金融数据：
{market_ctx}

{news_section2}

{"注意：以上是真实市场数据。" if has_data else "注意：今日数据暂时无法获取，请根据近期宏观趋势给出参考分析。"}

请用简体中文分析以下内容（条列式，每点1-2句话）：
1. 今日10年期美债收益率走势及对股市影响（利多/利空）
2. 美联储政策动向：当前利率预期，近期官员表态
3. 今日是否有重要人物发表影响市场的言论（Fed主席/财长/知名投资人等），利多还是利空？具体说明
4. 美元指数、黄金、原油走势及含义
5. 今日整体宏观环境对股市的综合评分（偏多/中性/偏空）
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

    no_data_banner = "" if report["market_data"] else '<div class="no-data-banner">⚠️ 今日市场数据获取中，以下分析基于近期趋势参考，数据将在交易日收盘后自动更新</div>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>美股日报 {report['date']}</title>
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
  .no-data-banner {{ grid-column: 1/-1; background: rgba(210,153,34,0.12); border: 1px solid var(--gold); border-radius: 8px; padding: 12px 16px; color: var(--gold); font-size: 0.85rem; text-align: center; }}
</style>
</head>
<body>
<div class="header">
  <h1>📈 美股每日资讯站</h1>
  <div class="date">更新日期：{report['date']} · 美东时间</div>
</div>
<div class="container">

  {no_data_banner}

  <div class="card">
    <h2>📊 大盘指数</h2>
    {market_rows if market_rows else '<p style="color:var(--muted);font-size:0.85rem">数据加载中，请稍后刷新</p>'}
  </div>

  <div class="card">
    <h2>🔥 板块 & AI 个股</h2>
    {sector_rows if sector_rows else '<p style="color:var(--muted);font-size:0.85rem">数据加载中，请稍后刷新</p>'}
  </div>

  <div class="card full">
    <h2>📉 板块波动分析 · 利多 / 利空</h2>
    <div class="analysis">{md_to_html(report['sector_analysis'])}</div>
  </div>

  <div class="card full">
    <h2>🤖 AI 板块深度分析</h2>
    <div class="analysis">{md_to_html(report['ai_analysis'])}</div>
  </div>

  <div class="card full">
    <h2>🏦 宏观经济 · 金融数据 · 重要言论</h2>
    <div class="analysis">{md_to_html(report['macro_analysis'])}</div>
  </div>

</div>
<div class="footer">
  数据来源：Yahoo Finance · 分析：Claude AI<br>
  每日美东时间收盘后自动更新 · 仅供参考，不构成投资建议
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
