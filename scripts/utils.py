"""공용 유틸리티 - 경로, 프로필 I/O, Upstage Solar API, 뉴스 RSS, 기술적 지표"""

import os
import json
import math
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

_default_data = Path.home() / ".stock-briefing" / "data"
DATA_DIR = Path(os.environ.get("STOCK_BRIEFING_DATA_DIR", str(_default_data)))
CACHE_DIR = DATA_DIR / "cache"
PROFILE_FILE = DATA_DIR / "profile.json"

UPSTAGE_API_KEY = os.environ.get("UPSTAGE_API_KEY", "")
UPSTAGE_BASE_URL = "https://api.upstage.ai/v1"
UPSTAGE_MODEL = "solar-pro3"


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_profile() -> dict | None:
    if not PROFILE_FILE.exists():
        return None
    with open(PROFILE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_profile(profile: dict):
    ensure_dirs()
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def call_solar(messages: list, temperature: float = 0.3) -> str:
    """Upstage Solar Pro 3 API 호출"""
    if not UPSTAGE_API_KEY:
        return "⚠️  UPSTAGE_API_KEY 환경변수가 설정되지 않았습니다.\n   https://console.upstage.ai 에서 API 키를 발급받아 설정해주세요."

    headers = {
        "Authorization": f"Bearer {UPSTAGE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": UPSTAGE_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    try:
        resp = requests.post(
            f"{UPSTAGE_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=45,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            return "❌ API 키가 유효하지 않습니다. UPSTAGE_API_KEY를 확인해주세요."
        return f"❌ Solar API 오류: {e}"
    except Exception as e:
        return f"❌ Solar API 연결 실패: {e}"


def fetch_news_rss(query: str, max_items: int = 5) -> list[dict]:
    """Google News RSS에서 뉴스 수집"""
    url = (
        f"https://news.google.com/rss/search"
        f"?q={requests.utils.quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    )
    try:
        resp = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; StockBriefing/1.0)"},
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")[:max_items]
        news = []
        for item in items:
            title = item.findtext("title", "").strip()
            pub_date = item.findtext("pubDate", "").strip()
            source = ""
            source_el = item.find("source")
            if source_el is not None:
                source = source_el.text or ""
            if title:
                news.append({"title": title, "date": pub_date, "source": source})
        return news
    except Exception:
        return []


def format_price(price: float, currency: str) -> str:
    if currency in ("KRW",):
        return f"{price:,.0f}원"
    return f"${price:,.2f}"


def change_emoji(pct: float) -> str:
    if pct >= 3:
        return "🔴📈"
    if pct > 0:
        return "🟢"
    if pct <= -3:
        return "🔵📉"
    return "🔴"


def type_label(investment_type: str) -> str:
    return "공격형" if investment_type == "aggressive" else "안정형"


# ── 기술적 지표 계산 ──────────────────────────────────────────────────────────

def calc_ma(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def calc_bollinger(closes: list[float], period: int = 20, std_mult: float = 2.0) -> dict | None:
    if len(closes) < period:
        return None
    window = closes[-period:]
    mid = sum(window) / period
    variance = sum((x - mid) ** 2 for x in window) / period
    std = math.sqrt(variance)
    return {"upper": mid + std_mult * std, "mid": mid, "lower": mid - std_mult * std}


def calc_disparity(current: float, ma: float | None) -> float | None:
    if ma is None or ma == 0:
        return None
    return (current / ma) * 100


def detect_ma_alignment(ma5: float | None, ma20: float | None, ma60: float | None, ma120: float | None) -> str:
    """정배열/역배열 판단. None인 항목은 건너뜀."""
    vals = [(v, p) for v, p in [(ma5, 5), (ma20, 20), (ma60, 60), (ma120, 120)] if v is not None]
    if len(vals) < 2:
        return "판단불가"
    sorted_asc = sorted(vals, key=lambda x: x[0])
    sorted_desc = sorted(vals, key=lambda x: x[0], reverse=True)
    # 정배열: 단기 > 장기 순
    if [p for _, p in sorted_desc] == [p for _, p in vals]:
        return "정배열"
    if [p for _, p in sorted_asc] == [p for _, p in vals]:
        return "역배열"
    return "혼조"


def detect_cross(closes: list[float]) -> str | None:
    """골든/데드크로스 감지 (5일 vs 20일, 최근 3일 이내)"""
    if len(closes) < 22:
        return None
    results = []
    for i in range(-3, 0):
        idx = i  # -3, -2, -1
        w5_now = closes[idx - 4:idx + 1] if idx != -1 else closes[-5:]
        w20_now = closes[idx - 19:idx + 1] if idx != -1 else closes[-20:]
        w5_prev = closes[idx - 5:idx] if idx != -1 else closes[-6:-1]
        w20_prev = closes[idx - 20:idx] if idx != -1 else closes[-21:-1]
        if len(w5_now) < 5 or len(w20_now) < 20 or len(w5_prev) < 5 or len(w20_prev) < 20:
            continue
        ma5_now = sum(w5_now) / 5
        ma20_now = sum(w20_now) / 20
        ma5_prev = sum(w5_prev) / 5
        ma20_prev = sum(w20_prev) / 20
        if ma5_prev <= ma20_prev and ma5_now > ma20_now:
            results.append("골든크로스")
        elif ma5_prev >= ma20_prev and ma5_now < ma20_now:
            results.append("데드크로스")
    return results[-1] if results else None


def detect_pullback(closes: list[float], ma20: float | None, ma60: float | None) -> bool:
    """눌림목 감지: MA20 근처(±2%) + 이전 상승 추세"""
    if ma20 is None or len(closes) < 10:
        return False
    current = closes[-1]
    near_ma20 = abs(current - ma20) / ma20 < 0.02
    uptrend = closes[-10] < closes[-5] < current if len(closes) >= 10 else False
    return near_ma20 and uptrend


def detect_candle_patterns(ohlcv: list[dict]) -> list[str]:
    """최근 3일 캔들 패턴 감지. ohlcv: [{"open","high","low","close","volume"}, ...]"""
    if len(ohlcv) < 3:
        return []
    recent = ohlcv[-3:]
    patterns = []

    def body(c): return abs(c["close"] - c["open"])
    def upper_shadow(c): return c["high"] - max(c["open"], c["close"])
    def lower_shadow(c): return min(c["open"], c["close"]) - c["low"]
    def is_bull(c): return c["close"] > c["open"]
    def is_bear(c): return c["close"] < c["open"]
    def total_range(c): return c["high"] - c["low"]

    c1, c2, c3 = recent[0], recent[1], recent[2]

    # 도지 (몸통이 전체 범위의 10% 이하)
    for i, c in enumerate(recent):
        rng = total_range(c)
        if rng > 0 and body(c) / rng < 0.1:
            patterns.append(f"도지({i+1}일전)")

    # 장악형
    if is_bear(c2) and is_bull(c3) and c3["open"] < c2["close"] and c3["close"] > c2["open"]:
        patterns.append("상승장악형(매수)")
    if is_bull(c2) and is_bear(c3) and c3["open"] > c2["close"] and c3["close"] < c2["open"]:
        patterns.append("하락장악형(매도)")

    # 망치형 (하락 추세 후 하단 긴 꼬리)
    if body(c3) > 0:
        if lower_shadow(c3) >= 2 * body(c3) and upper_shadow(c3) < body(c3):
            patterns.append("망치형(매수)")
        if upper_shadow(c3) >= 2 * body(c3) and lower_shadow(c3) < body(c3):
            patterns.append("역망치형")

    # 적삼병 (연속 3양봉)
    if all(is_bull(c) for c in recent) and c2["close"] > c1["close"] and c3["close"] > c2["close"]:
        patterns.append("적삼병(강세)")

    # 흑삼병 (연속 3음봉)
    if all(is_bear(c) for c in recent) and c2["close"] < c1["close"] and c3["close"] < c2["close"]:
        patterns.append("흑삼병(약세)")

    # 샛별형: 음봉 + 도지/소형 + 양봉
    if is_bear(c1) and body(c2) < body(c1) * 0.3 and is_bull(c3) and c3["close"] > (c1["open"] + c1["close"]) / 2:
        patterns.append("샛별형(매수)")

    # 저녁별형: 양봉 + 도지/소형 + 음봉
    if is_bull(c1) and body(c2) < body(c1) * 0.3 and is_bear(c3) and c3["close"] < (c1["open"] + c1["close"]) / 2:
        patterns.append("저녁별형(매도)")

    return patterns if patterns else ["패턴없음"]


def calc_support_resistance(highs: list[float], lows: list[float], window: int = 20) -> dict:
    """최근 window 기간 고점/저점 기반 지지선/저항선"""
    recent_highs = highs[-window:]
    recent_lows = lows[-window:]
    resistance = max(recent_highs) if recent_highs else 0.0
    support = min(recent_lows) if recent_lows else 0.0
    return {"support": support, "resistance": resistance}


def detect_volume_surge(volumes: list[float], window: int = 20) -> dict:
    """거래량 분석: 최근 값 vs 평균"""
    if len(volumes) < 2:
        return {"ratio": 1.0, "label": "보통"}
    avg = sum(volumes[-window:]) / min(len(volumes), window)
    current_vol = volumes[-1]
    ratio = current_vol / avg if avg > 0 else 1.0
    if ratio >= 2.0:
        label = "급증🔥"
    elif ratio >= 1.3:
        label = "증가"
    elif ratio <= 0.5:
        label = "감소"
    else:
        label = "보통"
    return {"ratio": ratio, "avg": avg, "current": current_vol, "label": label}


def detect_trend(closes: list[float], window: int = 20) -> str:
    """단순 선형회귀 기울기로 추세 방향 판단"""
    if len(closes) < window:
        return "판단불가"
    data = closes[-window:]
    n = len(data)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(data) / n
    num = sum((xs[i] - mean_x) * (data[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    if den == 0:
        return "횡보"
    slope = num / den
    slope_pct = slope / mean_y * 100
    if slope_pct > 0.3:
        return "상승"
    if slope_pct < -0.3:
        return "하락"
    return "횡보"


def detect_box_range(highs: list[float], lows: list[float], window: int = 20) -> bool:
    """박스권 여부: 고점/저점 범위가 현재가 기준 10% 이내"""
    if len(highs) < window:
        return False
    rh = max(highs[-window:])
    rl = min(lows[-window:])
    mid = (rh + rl) / 2
    return (rh - rl) / mid < 0.10 if mid > 0 else False


def calc_technical(ohlcv_df) -> dict:
    """
    yfinance DataFrame → 기술적 지표 딕셔너리.
    ohlcv_df: yfinance t.history() 결과 (pandas DataFrame)
    """
    closes = [float(x) for x in ohlcv_df["Close"].tolist()]
    opens  = [float(x) for x in ohlcv_df["Open"].tolist()]
    highs  = [float(x) for x in ohlcv_df["High"].tolist()]
    lows   = [float(x) for x in ohlcv_df["Low"].tolist()]
    vols   = [float(x) for x in ohlcv_df["Volume"].tolist()]

    ohlcv_list = [
        {"open": opens[i], "high": highs[i], "low": lows[i], "close": closes[i], "volume": vols[i]}
        for i in range(len(closes))
    ]

    current = closes[-1]
    ma5   = calc_ma(closes, 5)
    ma20  = calc_ma(closes, 20)
    ma60  = calc_ma(closes, 60)
    ma120 = calc_ma(closes, 120)

    bb = calc_bollinger(closes, 20)
    if bb:
        rng = bb["upper"] - bb["lower"]
        if rng > 0:
            bb_pos_pct = (current - bb["lower"]) / rng * 100
        else:
            bb_pos_pct = 50.0
        if current >= bb["upper"] * 0.99:
            bb_position = "상단근접(과매수)"
        elif current <= bb["lower"] * 1.01:
            bb_position = "하단근접(과매도)"
        else:
            bb_position = f"중간({bb_pos_pct:.0f}%)"
    else:
        bb_position = "데이터부족"

    disparity = calc_disparity(current, ma20)
    if disparity is not None:
        if disparity <= 98:
            disp_label = f"{disparity:.1f} → 매수권"
        elif disparity >= 105:
            disp_label = f"{disparity:.1f} → 매도권"
        else:
            disp_label = f"{disparity:.1f} → 보통"
    else:
        disp_label = "데이터부족"

    alignment = detect_ma_alignment(ma5, ma20, ma60, ma120)
    cross = detect_cross(closes)
    pullback = detect_pullback(closes, ma20, ma60)
    candle_patterns = detect_candle_patterns(ohlcv_list)
    sr = calc_support_resistance(highs, lows)
    vol_info = detect_volume_surge(vols)
    trend = detect_trend(closes)
    is_box = detect_box_range(highs, lows)

    return {
        "current": current,
        "ma5": ma5,
        "ma20": ma20,
        "ma60": ma60,
        "ma120": ma120,
        "alignment": alignment,
        "cross": cross,
        "pullback": pullback,
        "bollinger": bb,
        "bb_position": bb_position,
        "disparity": disparity,
        "disparity_label": disp_label,
        "candle_patterns": candle_patterns,
        "support": sr["support"],
        "resistance": sr["resistance"],
        "volume": vol_info,
        "trend": trend,
        "is_box": is_box,
    }


# ── 재무제표 분석 ─────────────────────────────────────────────────────────────

def _safe_get(df, row_names, col_idx: int = 0):
    """DataFrame 인덱스에서 안전하게 float 값 추출. 없으면 None."""
    if df is None:
        return None
    try:
        import pandas as pd
        names = row_names if isinstance(row_names, list) else [row_names]
        for name in names:
            if name in df.index:
                vals = df.loc[name].dropna()
                if len(vals) > col_idx:
                    v = vals.iloc[col_idx]
                    if pd.notna(v):
                        return float(v)
    except Exception:
        pass
    return None


def fetch_financials(ticker: str) -> dict:
    """yfinance 연간 재무제표로 주요 건전성 지표 계산. 데이터 없으면 None."""
    import yfinance as yf

    _empty_keys = [
        "current_ratio", "quick_ratio", "debt_equity",
        "gross_margin", "op_margin", "net_margin", "rev_growth",
        "roa", "roe", "inventory_turnover", "receivable_turnover",
        "receivable_growth", "inventory_growth",
        "ocf", "icf", "fcf",
    ]
    empty = {k: None for k in _empty_keys}

    try:
        t = yf.Ticker(ticker)

        def load(attrs):
            for a in attrs:
                try:
                    df = getattr(t, a, None)
                    if df is not None and not df.empty:
                        return df
                except Exception:
                    pass
            return None

        inc = load(["income_stmt", "financials"])
        bs  = load(["balance_sheet"])
        cf  = load(["cashflow", "cash_flow"])

        g = _safe_get

        # 손익계산서
        rev0  = g(inc, ["Total Revenue", "TotalRevenue"])
        rev1  = g(inc, ["Total Revenue", "TotalRevenue"], 1)
        gross = g(inc, ["Gross Profit", "GrossProfit"])
        ebit  = g(inc, ["Operating Income", "EBIT", "Ebit"])
        net   = g(inc, ["Net Income", "NetIncome", "Net Income Common Stockholders"])

        # 재무상태표
        cur_a  = g(bs, ["Current Assets", "CurrentAssets"])
        cur_l  = g(bs, ["Current Liabilities", "CurrentLiabilities"])
        inv0   = g(bs, ["Inventory"])
        inv1   = g(bs, ["Inventory"], 1)
        rec0   = g(bs, ["Net Receivables", "Receivables",
                         "Accounts Receivable", "AccountsReceivable"])
        rec1   = g(bs, ["Net Receivables", "Receivables",
                         "Accounts Receivable", "AccountsReceivable"], 1)
        t_ast  = g(bs, ["Total Assets", "TotalAssets"])
        t_liab = g(bs, ["Total Liabilities Net Minority Interest",
                         "TotalLiabilitiesNetMinorityInterest",
                         "Total Liabilities", "TotalLiabilities"])
        equity = g(bs, ["Stockholders Equity", "StockholdersEquity",
                         "Common Stock Equity", "Total Stockholders Equity",
                         "TotalStockholdersEquity"])

        # 현금흐름
        ocf = g(cf, ["Operating Cash Flow",
                      "Total Cash From Operating Activities", "Cash From Operations"])
        icf = g(cf, ["Investing Cash Flow",
                      "Total Cash From Investing Activities", "Cash From Investing"])
        fcf = g(cf, ["Financing Cash Flow",
                      "Total Cash From Financing Activities", "Cash From Financing"])

        fin = dict(empty)

        # 안정성
        if cur_a and cur_l and cur_l != 0:
            fin["current_ratio"] = cur_a / cur_l * 100
            fin["quick_ratio"]   = (cur_a - (inv0 or 0)) / cur_l * 100
        if t_liab and equity and equity > 0:
            fin["debt_equity"] = t_liab / equity * 100

        # 수익성/성장성
        if rev0:
            if gross: fin["gross_margin"] = gross / rev0 * 100
            if ebit:  fin["op_margin"]    = ebit  / rev0 * 100
            if net:   fin["net_margin"]   = net   / rev0 * 100
        if rev0 and rev1 and rev1 != 0:
            fin["rev_growth"] = (rev0 - rev1) / abs(rev1) * 100

        # 효율성
        if net:
            if t_ast  and t_ast  != 0: fin["roa"] = net / t_ast  * 100
            if equity and equity >  0: fin["roe"] = net / equity * 100

        cogs    = (rev0 - gross) if rev0 and gross else None
        avg_inv = ((inv0 or 0) + (inv1 or 0)) / 2 if inv0 is not None else None
        if cogs and avg_inv and avg_inv > 0:
            fin["inventory_turnover"] = cogs / avg_inv

        avg_rec = ((rec0 or 0) + (rec1 or 0)) / 2 if rec0 is not None else None
        if rev0 and avg_rec and avg_rec > 0:
            fin["receivable_turnover"] = rev0 / avg_rec

        # 이상신호 감지용 전년 대비 증감률
        if rec0 and rec1 and rec1 != 0:
            fin["receivable_growth"] = (rec0 - rec1) / abs(rec1) * 100
        if inv0 and inv1 and inv1 != 0:
            fin["inventory_growth"]  = (inv0 - inv1) / abs(inv1) * 100

        fin["ocf"] = ocf
        fin["icf"] = icf
        fin["fcf"] = fcf
        return fin

    except Exception:
        return empty


def assess_financial_health(fin: dict, investment_type: str = "aggressive") -> tuple[str, list[str]]:
    """재무 건전성 등급(A~D)과 이상신호 목록 반환"""
    warnings: list[str] = []
    score = 100

    # ── 이상신호 ──
    ocf   = fin.get("ocf")
    net_m = fin.get("net_margin")
    if ocf is not None and net_m is not None and ocf < 0 and net_m > 0:
        warnings.append("영업현금흐름(−)인데 순이익(+) → 가짜이익 가능성")
        score -= 25

    rec_g = fin.get("receivable_growth")
    if rec_g is not None and rec_g > 30:
        warnings.append(f"매출채권 전년대비 +{rec_g:.0f}% 급증 → 부실매출 가능성")
        score -= 15

    inv_g = fin.get("inventory_growth")
    if inv_g is not None and inv_g > 30:
        warnings.append(f"재고자산 전년대비 +{inv_g:.0f}% 급증")
        score -= 15

    # ── 안정성 ──
    cr = fin.get("current_ratio")
    if cr is not None:
        if cr < 50:
            warnings.append(f"유동비율 {cr:.0f}% → 유동성 위기")
            score -= 30
        elif cr < 100:
            warnings.append(f"유동비율 {cr:.0f}% → 100% 미만 주의")
            score -= 10

    qr = fin.get("quick_ratio")
    if qr is not None and qr < 30:
        warnings.append(f"당좌비율 {qr:.0f}% → 유동성 위기")
        score -= 20

    de = fin.get("debt_equity")
    if de is not None and de > 200:
        warnings.append(f"부채비율 {de:.0f}% → 200% 초과")
        score -= 15

    # ── 수익성 ──
    roe = fin.get("roe")
    if roe is not None and roe < 0:
        warnings.append(f"ROE {roe:.1f}% → 자본잠식 가능성")
        score -= 20

    rev_g = fin.get("rev_growth")
    op_m  = fin.get("op_margin")
    if rev_g is not None and op_m is not None and rev_g > 5 and op_m < 0:
        warnings.append("매출 증가에도 영업이익(−) → 원가 압박")
        score -= 15

    # 등급 결정
    if score >= 85:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 50:
        grade = "C"
    else:
        grade = "D"

    # 안정형은 이상신호에 한 단계 더 엄격
    if investment_type != "aggressive" and warnings and grade == "B":
        grade = "C"

    return grade, warnings if warnings else ["이상없음"]


def format_financial_section(fin: dict, grade: str, warnings: list[str]) -> str:
    """재무 건전성 분석 결과를 출력용 문자열로 포맷"""
    def pct(v, d=1):
        return f"{v:.{d}f}%" if v is not None else "N/A"

    cr = fin.get("current_ratio")
    cr_lbl = ("정상" if cr and cr >= 100 else
              "위기경고" if cr is not None and cr < 50 else
              "주의" if cr is not None else "")
    cr_str = f"{pct(cr, 0)} ({cr_lbl})" if cr_lbl else pct(cr, 0)

    de = fin.get("debt_equity")
    de_lbl = ("정상" if de is not None and de <= 200 else
              "위험" if de is not None and de > 300 else
              "주의" if de is not None else "")
    de_str = f"{pct(de, 0)} ({de_lbl})" if de_lbl else pct(de, 0)

    roe = fin.get("roe")
    roe_lbl = ("우량" if roe is not None and roe >= 15 else
               "보통" if roe is not None and roe >= 5 else
               "부진" if roe is not None else "")
    roe_str = f"{pct(roe)} ({roe_lbl})" if roe_lbl else pct(roe)

    rev_g = fin.get("rev_growth")
    op_m  = fin.get("op_margin")
    co_growth = (rev_g is not None and rev_g > 0 and
                 op_m  is not None and op_m  > 0)

    def cf_sign(v):
        if v is None: return "?"
        return "+" if v > 0 else "−"
    ocf_s = cf_sign(fin.get("ocf"))
    icf_s = cf_sign(fin.get("icf"))
    fcf_s = cf_sign(fin.get("fcf"))
    good_cf = (ocf_s == "+" and icf_s == "−" and fcf_s == "−")

    grade_map = {"A": "A (우량)", "B": "B (보통)", "C": "C (주의)", "D": "D (위험)"}

    lines = [
        "  💰 재무 건전성 분석",
        "  [안정성]",
        f"  유동비율    {cr_str}",
        f"  부채비율    {de_str}",
        "  [수익성]",
        f"  ROE         {roe_str}",
        f"  영업이익률  {pct(op_m)} / 매출성장률 {pct(rev_g)}",
        f"  매출·이익 동반성장: {'O' if co_growth else 'X'}",
        "  [현금흐름]",
        f"  영업({ocf_s}) / 투자({icf_s}) / 재무({fcf_s})",
        f"  우량패턴(+/−/−): {'O' if good_cf else 'X'}",
        "  [이상신호]",
    ]
    for w in warnings:
        prefix = "  ⚠️  " if w != "이상없음" else "  ✅  "
        lines.append(f"{prefix}{w}")
    lines.append(f"  [재무종합등급]  {grade_map.get(grade, grade)}")

    return "\n".join(lines)


def format_technical_section(ta: dict, currency: str) -> str:
    """기술적 분석 결과를 출력용 문자열로 포맷"""
    def fp(v): return format_price(v, currency) if v else "N/A"

    cross_str = f" | {ta['cross']}" if ta.get("cross") else ""
    pullback_str = " | 눌림목 구간" if ta.get("pullback") else ""
    ma_line = f"이동평균선: {ta['alignment']}{cross_str}{pullback_str}"

    patterns_str = ", ".join(ta["candle_patterns"])
    vol = ta["volume"]
    vol_str = f"평균 대비 {vol['ratio']:.1f}배 ({vol['label']})"

    lines = [
        "📊 기술적 분석",
        f"이동평균선: {ma_line}",
        f"볼린저밴드: {ta['bb_position']}",
        f"이격도:     {ta['disparity_label']}",
        f"캔들패턴:   {patterns_str}",
        f"지지/저항:  지지선 {fp(ta['support'])} / 저항선 {fp(ta['resistance'])}",
        f"거래량:     {vol_str}",
        f"추세:       {ta['trend']}{'  (박스권)' if ta['is_box'] else ''}",
    ]
    return "\n".join(lines)
