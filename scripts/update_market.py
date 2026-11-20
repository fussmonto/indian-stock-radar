import json
import os
import urllib.request
from datetime import datetime
import pytz
import pandas as pd
import yfinance as yf
import feedparser

IST = pytz.timezone("Asia/Kolkata")
NOW_IST = datetime.now(IST)


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
    return {"price": 25729.35, "change_pct": 0.0}


def fetch_stock(item: dict):
    sym = item["symbol"]
    ticker = yf.Ticker(f"{sym}.NS")
    df = ticker.history(period="1y")
    if df.empty or len(df) < 20:
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

    custom_buy = item.get("custom_buy")
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

    info = {}
    try:
        info = ticker.info or {}
    except Exception:
        info = {}

    return {
        "symbol": sym,
        "name": item.get("name", sym),
        "sector": item.get("sector", "NSE"),
        "price": round(price, 2),
        "change_pct": round(chg_pct, 2),
        "high52": high52,
        "low52": low52,
        "rsi14": rsi14,
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "ema200": round(ema200, 2),
        "vol_ratio": vol_ratio,
        "mode": item.get("mode", "CNC"),
        "setup": setup,
        "buy_zone": buy_zone,
        "breakout_trigger": round(recent_high * 1.005, 2),
        "target1": target1,
        "target2": target2,
        "stop_loss": stop_loss,
        "pe": round(float(info.get("trailingPE") or 0), 2),
        "roe": round(float((info.get("returnOnEquity") or 0) * 100), 2),
        "roce": 0.0,
        "div_yield": round(float((info.get("dividendYield") or 0) * 100), 2),
        "book_val": round(float(info.get("bookValue") or 0), 2),
        "earnings_note": f"52W Range ₹{low52}–₹{high52}; RSI(14) at {rsi14}.",
        "history": [round(float(x), 2) for x in close.tail(10).tolist()],
    }


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
        "| Symbol | LTP (₹) | Chg % | Mode | Buy Zone | Target 1 | Stop-Loss | Setup |",
        "| :--- | ---: | ---: | :---: | :--- | ---: | ---: | :--- |"
    ]
    for s in report["stocks"]:
        lines.append(
            f"| **{s['symbol']}** | ₹{s['price']} | {s['change_pct']}% | {s['mode']} | {s['buy_zone']} | ₹{s['target1']} | ₹{s['stop_loss']} | {s['setup']} |"
        )
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
    stocks = [res for item in watchlist if (res := fetch_stock(item))]
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
    print(f"Updated {len(stocks)} stocks at {report['meta']['updated_ist']}")


if __name__ == "__main__":
    main()
    
