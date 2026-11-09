"""
BNF 25일선 이격도 역추세 신호 알림 시스템
* 단계1 관찰: 종가가 25EMA 대비 기준 이격도 이하
* 단계2 대기: + 최근 RSI(14) 과매도(<=30)
* 매수 신호: 최근 N일 내 이격도·RSI 조건 충족 + 오늘 MACD 히스토그램이 0선 아래→위 전환
* 청산 추적: 손절(직전 저점) / 익절(25EMA 도달) / 2R 도달 / 보유기간 만료
사용법: python bnf_signal.py KR 또는 python bnf_signal.py US
"""

import json
import os
import sys
import time
import datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parent
config_path = ROOT / "config.json"

if config_path.exists():
    CFG = json.loads(config_path.read_text(encoding="utf-8"))
else:
    # 기본 설정 폴백 (config.json이 없을 경우 대비)
    CFG = {
        "rules": {
            "ma_period": 25,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "lookback_days": 5
        },
        "thresholds": {
            "dev": {"large": -8.0, "volatile": -12.0}
        },
        "KR": {"kospi_top_n": 50, "kosdaq_top_n": 30, "extra": {}},
        "US": {"nasdaq100": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"], "large": [], "volatile": []}
    }

STATE_DIR = ROOT / "state"
DATA_DIR = ROOT / "docs" / "data"
STATE_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

R = CFG["rules"]
KST = dt.timezone(dt.timedelta(hours=9))

def send_telegram(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[텔레그램 미설정] 토큰 또는 챗 ID가 없습니다.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        res = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
        if not res.ok:
            print(f"텔레그램 발송 실패: {res.text}")
    except Exception as e:
        print(f"텔레그램 발송 중 에러 발생: {e}")

def kr_universe():
    cache = STATE_DIR / "kr_universe.json"
    try:
        import FinanceDataReader as fdr
        out = {}
        for mkt, n, grp, sfx in (("KOSPI", CFG["KR"]["kospi_top_n"], "large", ".KS"),
                                 ("KOSDAQ", CFG["KR"]["kosdaq_top_n"], "volatile", ".KQ")):
            df = fdr.StockListing(mkt)
            df = df[df["Code"].astype(str).str.fullmatch(r"\d{6}")]
            df = df.sort_values("Marcap", ascending=False).head(n)
            for _, r in df.iterrows():
                out[r["Code"] + sfx] = {"name": r["Name"], "group": grp}
        for t, v in CFG["KR"].get("extra", {}).items():
            out[t] = v
        if len(out) > 20:
            cache.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
            return out
    except Exception as e:
        print("KR 종목목록 조회 실패, 캐시 사용:", e)
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    return {"005930.KS": {"name": "삼성전자", "group": "large"}, "000660.KS": {"name": "SK하이닉스", "group": "large"}}

def us_universe():
    u = CFG["US"]
    out = {}
    for t in u.get("nasdaq100", []) + u.get("large", []):
        out[t] = {"name": t, "group": "large"}
    for t in u.get("volatile", []):
        out[t] = {"name": t, "group": "volatile"}
    if not out:
        out = {"AAPL": {"name": "AAPL", "group": "large"}, "TSLA": {"name": "TSLA", "group": "volatile"}}
    return out

def calc_indicators(df: pd.DataFrame):
    close = df["Close"]
    ema25 = close.ewm(span=R["ma_period"], adjust=False).mean()
    dev = (close - ema25) / ema25 * 100

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/R["rsi_period"], adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/R["rsi_period"], adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))

    exp12 = close.ewm(span=12, adjust=False).mean()
    exp26 = close.ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal

    df["EMA25"] = ema25
    df["Dev"] = dev
    df["RSI"] = rsi
    df["MACD_Hist"] = hist
    return df

def run(market: str):
    print(f"[{market}] BNF Signal 분석 시작...")
    universe = kr_universe() if market == "KR" else us_universe()
    
    asof_s = dt.datetime.now(KST).strftime("%Y-%m-%d")
    buys = []
    watch = []
    rows = []

    for ticker, info in universe.items():
        try:
            df = yf.download(ticker, period="6mo", progress=False)
            if df.empty or len(df) < 40:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            df = calc_indicators(df)
            latest = df.iloc[-1]
            prev = df.iloc[-2]

            group = info["group"]
            th_dev = CFG["thresholds"]["dev"][group]

            dev_val = latest["Dev"]
            rsi_val = latest["RSI"]
            hist_cur = latest["MACD_Hist"]
            hist_prev = prev["MACD_Hist"]

            # 조건 판단
            is_stage1 = dev_val <= th_dev
            recent_rsi = df["RSI"].tail(R["lookback_days"]) <= R["rsi_oversold"]
            is_stage2 = recent_rsi.any()

            # 매수 신호: 이격도/RSI 충족 상태에서 MACD 히스토그램이 0선 상향 돌파
            is_buy = is_stage2 and (hist_prev < 0 and hist_cur >= 0)

            item = {
                "ticker": ticker,
                "name": info["name"],
                "price": float(latest["Close"]),
                "dev": round(float(dev_val), 2),
                "rsi": round(float(rsi_val), 1),
                "stage": 2 if is_stage2 else (1 if is_stage1 else 0)
            }

            rows.append(item)
            if is_buy:
                buys.append(item)
            elif is_stage1 or is_stage2:
                watch.append(item)

            time.sleep(0.2)
        except Exception as e:
            print(f"티커 {ticker} 처리 중 에러: {e}")

    # 결과 메시지 구성 및 텔레그램 발송
    msg = f"📊 *BNF 신호 리포트 ({market})* - {asof_s}\n\n"
    if buys:
        msg += "🚨 *[매수 신호 발생]*\n"
        for b in buys:
            msg += f"- {b['name']} ({b['ticker']}): 가격 {b['price']}, 이격도 {b['dev']}%, RSI {b['rsi']}\n"
        msg += "\n"
    else:
        msg += "💤 오늘 발생한 매수 신호는 없습니다.\n\n"

    if watch:
        msg += "👀 *[관찰 및 대기 종목]*\n"
        for w in watch[:10]: # 최대 10개 표시
            msg += f"- {w['name']} ({w['ticker']}): 이격도 {w['dev']}%, RSI {w['rsi']}\n"
    
    send_telegram(msg)
    print(f"[{market}] 분석 및 텔레그램 발송 완료 (매수={len(buys)}, 대기={len(watch)})")

if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["KR", "US"]
    for m in targets:
        run(m.upper())
