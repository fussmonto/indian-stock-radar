import json
import os
import time
import urllib.request
from datetime import datetime
import pytz
import pandas as pd
import yfinance as yf
import feedparser

IST = pytz.timezone("Asia/Kolkata")
NOW_IST = datetime.now(IST)

FALLBACK_UNIVERSE = [
    "SUZLON", "YESBANK", "IDEA", "JPPOWER", "RPOWER", "IRB", "SOUTHBANK", "UCOBANK",
    "CENTRALBK", "IOB", "NHPC", "SJVN", "HUDCO", "IRFC", "RVNL", "RAILTEL", "NBCC",
    "MAHABANK", "UNIONBANK", "BANKINDIA", "PNB", "CANBK", "IDFCFIRSTB", "FEDERALBNK",
    "RBLBANK", "EQUITASBNK", "UJJIVANSFB", "BANDHANBNK", "NMDC", "SAIL", "NATIONALUM",
    "HINDCOPPER", "ONGC", "IOC", "BPCL", "GAIL", "NTPC", "POWERGRID", "TATAPOWER",
    "TORNTPOWER", "CESC", "JSWENERGY", "ADANIPOWER", "BHEL", "BEL", "COALINDIA",
    "ASHOKLEY", "MOTHERSON", "MSUMI", "EXIDEIND", "TVSMOTOR", "TATAMOTORS", "WIPRO",
    "TECHM", "INFY", "HCLTECH", "TCS", "KPITTECH", "COFORGE", "CYIENT", "BSOFT",
    "SONATSOFTW", "ZENSARTECH", "TATASTEEL", "JINDALSTEL", "HINDALCO", "VEDL",
    "APLAPOLLO", "WELCORP", "JSL", "GMRINFRA", "NCC", "PNCINFRA", "ASHOKA", "KNRCON",
    "HFCL", "ITI", "TEJASNET", "TATACOMM", "ZEEL", "SUNTV", "NYKAA", "ZOMATO",
    "PAYTM", "POLICYBZR", "DELHIVERY", "IRCTC", "CONCOR", "GESHIP", "SCI", "COCHINSHIP",
    "GRSE", "MAZDOCK", "HAL", "BDL", "DATAPATTNS", "PARAS", "CUPID", "NILASPACES",
    "TRIDENT", "ALOKINDS", "WELSPUNLIV", "RAYMOND", "ARVIND", "ABFRL", "TRENT",
    "BATAINDIA", "RELAXO", "CAMPUS", "DEVYANI", "JUBLFOOD", "WESTLIFE", "SBIN",
    "HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "INDUSINDBK", "AUBANK",
    "LICHSGFIN", "POONAWALLA", "MANAPPURAM", "MUTHOOTFIN", "CHOLAFIN", "RECLTD",
    "PFC", "IREDA", "JIOFIN", "CDSL", "BSE", "MCX", "CAMS", "BIOCON", "LAURUSLABS",
    "GRANULES", "AUROPHARMA", "CIPLA", "SUNPHARMA", "DRREDDY", "LUPIN", "GLENMARK",
    "NATCOPHARM", "SYNGENE", "MAXHEALTH", "FORTIS", "APOLLOHOSP", "DABUR", "MARICO",
    "GODREJCP", "ITC", "TATACONSUM", "VBL", "UBL", "RADICO", "CHAMBLFERT",
    "COROMANDEL", "GNFC", "GSFC", "RCF", "FACT", "DEEPAKFERT", "UPL", "PETRONET",
    "IGL", "MGL", "GUJGASLTD", "ATGL", "CASTROLIND", "AEGISLOG"
]


def get_all_nse_symbols():
    urls = [
        ("https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv", "SYMBOL"),
        ("https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv", "Symbol"),
    ]
    for url, col in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                df = pd.read_csv(resp)
                if " SERIES" in df.columns:
                    df = df[df[" SERIES"].astype(str).str.strip() == "EQ"]
                elif "SERIES" in df.columns:
                    df = df[df["SERIES"].astype(str).str.strip() == "EQ"]
                syms = [str(s).strip().upper() for s in df[col].dropna().tolist() if str(s).strip()]
                if len(syms) >= 400:
                    print(f"Loaded {len(syms)} NSE EQ symbols from {url}")
                    return sorted(set(syms + FALLBACK_UNIVERSE))
        except Exception as e:
            print(f"Symbol list fetch skipped ({url}):", e)
    return sorted(set(FALLBACK_UNIVERSE))


def compute_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, 1e-9)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return round(float(val), 2) if pd.notna(val) else 50.0


def load_watchlist():
    sheet_url = os.environ.get("GOOGLE_SHEET_CSV_URL", "").strip()
    if sheet_url:
        try:
            df = pd.read_csv(sheet_url)
            items = []
            for _, row in df.iterrows():
                sym = str(row.get("Symbol", "")).strip().upper()
                if not sym or sym == "NAN":
                    continue
                items.append({
                    "symbol": sym,
                    "name": str(row.get("Name", sym)),
                    "sector": str(row.get("Sector", "NSE")),
                    "mode": str(row.get("Mode", "CNC")).upper(),
                    "custom_buy": float(row["My_Buy_Price"]) if pd.notna(row.get("My_Buy_Price")) else None
                })
            if items:
                return items
        except Exception as e:
            print("Google Sheet fallback to watchlist.json:", e)

    with open("watchlist.json", "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_nifty():
    try:
        df = yf.Ticker("^NSEI").history(period="5d")
        if len(df) >= 2:
            last = float(df["Close"].iloc[-1])
            prev = float(df["Close"].iloc[-2])
            chg = ((last - prev) / prev) * 100
            return {"price": round(last, 2), "change_pct": round(chg, 2)}
    except Exception:
        pass
    return {"price": 25800.6, "change_pct": 1.12}


def analyze_df(sym: str, df: pd.DataFrame, meta_item: dict = None):
    if df is None or df.empty or len(df) < 20:
        return None
    df = df.dropna(subset=["Close"])
    if len(df) < 20:
        return None

    close = df["Close"]
    price = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) >= 2 else price
    chg_pct = ((price - prev) / prev) * 100 if prev else 0.0

    ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
    ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
    rsi14 = compute_rsi(close, 14)

    avg_vol = float(df["Volume"].tail(20).mean()) or 1.0
    last_vol = float(df["Volume"].iloc[-1])
    vol_ratio = round(last_vol / avg_vol, 2)

    high52 = round(float(df["High"].max()), 2)
    low52 = round(float(df["Low"].min()), 2)

    recent_low = float(df["Low"].tail(10).min())
    recent_high = float(df["High"].tail(10).max())
    stop_loss = round(min(recent_low * 0.985, price * 0.94), 2)
    target1 = round(max(recent_high, price * 1.06), 2)
    target2 = round(price * 1.12, 2)

    custom_buy = meta_item.get("custom_buy") if meta_item else None
    if custom_buy:
        buy_zone = f"₹{round(custom_buy * 0.98, 2)} – ₹{round(custom_buy, 2)}"
    else:
        buy_low = round(min(price, ema20) * 0.97, 2)
        buy_high = round(max(price, ema20) * 1.005, 2)
        buy_zone = f"₹{buy_low} – ₹{buy_high}"

    if rsi14 < 42:
        setup = "Oversold Dip Accumulation Zone"
    elif price > ema20 and vol_ratio >= 1.4:
        setup = "Volume Breakout • Above EMA20"
    elif price > ema20 and ema20 > ema50:
        setup = "Bullish Trend Continuation"
    else:
        setup = "Consolidation • Watch EMA20"

    score = 0.0
    if 34 <= rsi14 <= 58:
        score += 25
    if price >= ema200:
        score += 15
    if ema20 > ema50:
        score += 10
    score += min(vol_ratio * 8, 25)
    score += max(0, (target1 - price) / max(0.01, price - stop_loss)) * 5

    return {
        "symbol": sym,
        "name": meta_item.get("name", sym) if meta_item else sym,
        "sector": meta_item.get("sector", "NSE") if meta_item else "NSE",
        "price": round(price, 2),
        "change_pct": round(chg_pct, 2),
        "high52": high52,
        "low52": low52,
        "rsi14": rsi14,
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "ema200": round(ema200, 2),
        "vol_ratio": vol_ratio,
        "mode": meta_item.get("mode", "CNC") if meta_item else "CNC",
        "setup": setup,
        "buy_zone": buy_zone,
        "breakout_trigger": round(recent_high * 1.005, 2),
        "target1": target1,
        "target2": target2,
        "stop_loss": stop_loss,
        "pe": 0.0,
        "roe": 0.0,
        "roce": 0.0,
        "div_yield": 0.0,
        "book_val": 0.0,
        "earnings_note": f"52W Range ₹{low52}–₹{high52}; RSI(14) at {rsi14}.",
        "history": [round(float(x), 2) for x in close.tail(10).tolist()],
        "_score": round(score, 2),
        "_avg_vol": avg_vol
    }


def get_range_label(price: float):
    if price <= 100:
        return "Below ₹100"
    elif price <= 200:
        return "₹101 – ₹200"
    elif price <= 300:
        return "₹201 – ₹300"
    elif price <= 400:
        return "₹301 – ₹400"
    elif price <= 500:
        return "₹401 – ₹500"
    elif price <= 600:
        return "₹501 – ₹600"
    elif price <= 700:
        return "₹601 – ₹700"
    elif price <= 800:
        return "₹701 – ₹800"
    elif price <= 900:
        return "₹801 – ₹900"
    elif price <= 1000:
        return "₹901 – ₹1000"
    return None


def scan_price_ranges():
    unique_syms = get_all_nse_symbols()
    buckets = {
        "Below ₹100": [], "₹101 – ₹200": [], "₹201 – ₹300": [], "₹301 – ₹400": [],
        "₹401 – ₹500": [], "₹501 – ₹600": [], "₹601 – ₹700": [], "₹701 – ₹800": [],
        "₹801 – ₹900": [], "₹901 – ₹1000": []
    }
    chunk_size = 100
    for i in range(0, len(unique_syms), chunk_size):
        chunk = unique_syms[i:i + chunk_size]
        yf_syms = [f"{s}.NS" for s in chunk]
        try:
            data = yf.download(yf_syms, period="1y", group_by="ticker", threads=True, progress=False)
            for sym in chunk:
                key = f"{sym}.NS"
                try:
                    df = data[key] if hasattr(data.columns, "levels") and key in data.columns.levels[0] else None
                    res = analyze_df(sym, df)
                    if not res or res.get('_avg_vol', 0) < 25000:
                        continue
                    label = get_range_label(res["price"])
                    if label:
                        buckets[label].append(res)
                except Exception:
                    continue
        except Exception as e:
            print(f"Batch {i} scan error:", e)
        time.sleep(1.5)

    for label in buckets:
        buckets[label] = sorted(buckets[label], key=lambda x: x["_score"], reverse=True)[:10]
        for item in buckets[label]:
            item.pop("_score", None)
            item.pop("_avg_vol", None)
    return buckets


def fetch_indian_news():
    feeds = [
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "https://www.livemint.com/rss/markets",
    ]
    items = []
    for url in feeds:
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:4]:
                title = entry.get("title", "").strip()
                if not title:
                    continue
                low = title.lower()
                sentiment = "Bullish" if any(k in low for k in ["gain", "jump", "surge", "rally", "rise", "high"]) else (
                    "Bearish" if any(k in low for k in ["fall", "drop", "slump", "loss", "crash"]) else "Neutral"
                )
                items.append({
                    "time": NOW_IST.strftime("%d %b • %H:%M IST"),
                    "title": title,
                    "source": "ET / Mint RSS",
                    "sentiment": sentiment,
                    "ticker": "NIFTY"
                })
        except Exception:
            continue
    return items[:8]


def write_daily_markdown(report: dict):
    lines = [
        f"# Daily NSE Report ({report['meta']['updated_ist']})",
        f"**NIFTY 50:** {report['meta']['nifty50']['price']} ({report['meta']['nifty50']['change_pct']}%)",
        "",
        "## Watchlist Setups",
        "| Symbol | LTP (₹) | Chg % | Mode | Buy Zone | Target 1 | Stop-Loss | Setup |",
        "| :--- | ---: | ---: | :---: | :--- | ---: | ---: | :--- |"
    ]
    for s in report["stocks"]:
        lines.append(
            f"| **{s['symbol']}** | ₹{s['price']} | {s['change_pct']}% | {s['mode']} | {s['buy_zone']} | ₹{s['target1']} | ₹{s['stop_loss']} | {s['setup']} |"
        )
    lines.append("")
    lines.append("## Top Picks by Price Range (Up to ₹1,000)")
    for label, picks in report.get("range_picks", {}).items():
        if not picks:
            continue
        lines.append(f"### {label}")
        lines.append("| # | Symbol | LTP (₹) | Buy Zone | Target 1 | Stop-Loss | Setup |")
        lines.append("| :---: | :--- | ---: | :--- | ---: | ---: | :--- |")
        for idx, p in enumerate(picks[:5], 1):
            lines.append(f"| {idx} | **{p['symbol']}** | ₹{p['price']} | {p['buy_zone']} | ₹{p['target1']} | ₹{p['stop_loss']} | {p['setup']} |")
        lines.append("")
    with open("DAILY_REPORT.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def send_telegram_alert(report: dict):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return
    top = report["stocks"][:5]
    msg_lines = [f"📊 Indian Stock Radar ({report['meta']['updated_ist']})", f"NIFTY 50: {report['meta']['nifty50']['price']} ({report['meta']['nifty50']['change_pct']}%)\n"]
    for s in top:
        msg_lines.append(f"• {s['symbol']} ₹{s['price']} | Buy: {s['buy_zone']} | T1: ₹{s['target1']} | SL: ₹{s['stop_loss']}")
    payload = json.dumps({"chat_id": chat_id, "text": "\n".join(msg_lines)}).encode("utf-8")
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print("Telegram alert skipped:", e)


def main():
    watchlist = load_watchlist()
    stocks = []
    for item in watchlist:
        sym = item["symbol"]
        try:
            df = yf.Ticker(f"{sym}.NS").history(period="1y")
            res = analyze_df(sym, df, item)
            if res:
                res.pop("_score", None)
                res.pop("_avg_vol", None)
                stocks.append(res)
        except Exception:
            continue

    range_picks = scan_price_ranges()
    session_label = "Morning Pre-Market / Open Setup" if NOW_IST.hour < 12 else "Post-Market Close (CNC & Next-Day Prep)"
    report = {
        "meta": {
            "updated_ist": NOW_IST.strftime("%d %b %Y • %H:%M IST"),
            "session": session_label,
            "schedule": "08:45 AM & 03:45 PM IST (Mon–Fri)",
            "nifty50": fetch_nifty(),
            "fii_dii": {"fii_net_cr": 0.0, "dii_net_cr": 0.0, "date": NOW_IST.strftime("%d %b %Y")}
        },
        "stocks": stocks,
        "range_picks": range_picks,
        "news": fetch_indian_news(),
        "smart_money": [
            {"entity": "Watchlist Volume Leaders", "action": "Active", "value": f"{len(stocks)} NSE Stocks", "focus": "Auto-scanned via yfinance", "date": NOW_IST.strftime("%d %b %Y")}
        ]
    }
    os.makedirs("data", exist_ok=True)
    with open("data/daily_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    write_daily_markdown(report)
    send_telegram_alert(report)
    print(f"Updated {len(stocks)} watchlist + Nifty 500 range scan at {report['meta']['updated_ist']}")


if __name__ == "__main__":
    main()
