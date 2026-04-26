"""일일 주식 브리핑 — 기술적 분석 + 재무 분석 + 뉴스 + Solar AI 시그널"""

import sys
import subprocess
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_profile,
    save_profile,
    call_solar,
    fetch_news_rss,
    format_price,
    change_emoji,
    type_label,
    calc_technical,
    fetch_financials,
    assess_financial_health,
    format_financial_section,
    UPSTAGE_API_KEY,
)

W = 62  # 출력 너비


def _ensure_yfinance():
    try:
        import yfinance  # noqa: F401
    except ImportError:
        print("yfinance 설치 중...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "yfinance", "-q"],
            check=True,
        )


# ── 주가 + 기술적 + 재무 지표 조회 ──────────────────────────────────────────

def fetch_stock(ticker: str, investment_type: str = "aggressive") -> dict | None:
    import yfinance as yf

    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="6mo")
        if len(hist) < 2:
            return None

        current    = float(hist["Close"].iloc[-1])
        prev       = float(hist["Close"].iloc[-2])
        change_pct = (current - prev) / prev * 100
        volume     = int(hist["Volume"].iloc[-1])

        info = {}
        try:
            info = t.info
        except Exception:
            pass

        currency = info.get("currency") or (
            "KRW" if (".KS" in ticker or ".KQ" in ticker) else "USD"
        )

        ta  = calc_technical(hist)
        fin = fetch_financials(ticker)
        fin_grade, fin_warnings = assess_financial_health(fin, investment_type)

        return {
            "ticker": ticker,
            "current": current,
            "prev": prev,
            "change_pct": change_pct,
            "volume": volume,
            "currency": currency,
            "ta": ta,
            "financials": fin,
            "fin_grade": fin_grade,
            "fin_warnings": fin_warnings,
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


# ── 리포트 출력 ───────────────────────────────────────────────────────────────

def _divider(char="─"): return char * W

def _header(title: str) -> str:
    pad = W - len(title) - 6
    return f"{'━' * 3}  {title}  {'━' * max(pad, 2)}"


def print_stock_section(s: dict, name: str, news: list[dict]):
    """종목 1개 전체 분석 섹션 출력 (기술적 + 재무 + 뉴스)"""
    ta  = s.get("ta", {})
    cur = s["currency"]

    sign      = "▲" if s["change_pct"] >= 0 else "▼"
    emoji     = change_emoji(s["change_pct"])
    price_str = format_price(s["current"], cur)

    print(_header(f"{s['ticker']}  {name}"))
    print(f"  현재가    {emoji}  {price_str}  {sign}{abs(s['change_pct']):.2f}%")
    print()

    # ── 기술적 분석 ──────────────────────────────────────────────────────────
    def fp(v): return format_price(v, cur) if v else "N/A"

    cross_str    = f"  [{ta['cross']}]" if ta.get("cross") else ""
    pullback_str = "  눌림목구간" if ta.get("pullback") else ""
    patterns     = ta.get("candle_patterns", [])
    vol          = ta.get("volume", {})
    box_str      = "  (박스권)" if ta.get("is_box") else ""

    print("  📊 기술적 분석")
    print(f"  이동평균선  {ta.get('alignment','N/A')}{cross_str}{pullback_str}")
    print(f"  볼린저밴드  {ta.get('bb_position','N/A')}")
    print(f"  이격도      {ta.get('disparity_label','N/A')}")
    print(f"  캔들패턴    {', '.join(patterns)}")
    print(f"  지지/저항   지지선 {fp(ta.get('support'))} / 저항선 {fp(ta.get('resistance'))}")
    print(f"  거래량      평균 대비 {vol.get('ratio', 1):.1f}배  ({vol.get('label', 'N/A')})")
    print(f"  추세        {ta.get('trend','N/A')}{box_str}")
    print()

    # ── 재무 분석 ────────────────────────────────────────────────────────────
    fin_text = format_financial_section(
        s.get("financials", {}),
        s.get("fin_grade", "?"),
        s.get("fin_warnings", ["데이터없음"]),
    )
    print(fin_text)
    print()

    # ── 주요 뉴스 ────────────────────────────────────────────────────────────
    if news:
        print("  📰 주요 뉴스")
        for n in news[:4]:
            title = n["title"].strip()
            if " - " in title:
                title = title.rsplit(" - ", 1)[0].strip()
            print(f"  • {title}")
        print()


# ── AI 시그널 프롬프트 ────────────────────────────────────────────────────────

def build_signal_prompt(profile: dict, stocks: list[dict], news_map: dict) -> str:
    inv           = type_label(profile["investment_type"])
    threshold     = profile.get("alert_threshold", 5.0)
    is_aggressive = profile["investment_type"] == "aggressive"

    def pct(v, d=1):
        return f"{v:.{d}f}%" if v is not None else "N/A"

    def cf_sign(v):
        if v is None: return "?"
        return "+" if v > 0 else "−"

    stock_blocks = []
    for s in stocks:
        if s.get("error"):
            stock_blocks.append(f"\n[{s['ticker']}]\n오류: {s['error']}")
            continue

        ta    = s.get("ta", {})
        fin   = s.get("financials", {})
        cur   = s["currency"]
        sign  = "▲" if s["change_pct"] >= 0 else "▼"
        alert = " (급변)" if abs(s["change_pct"]) >= threshold else ""
        def fp(v): return format_price(v, cur) if v else "N/A"

        cross_str    = f", {ta['cross']}" if ta.get("cross") else ""
        pullback_str = ", 눌림목구간" if ta.get("pullback") else ""
        vol          = ta.get("volume", {})

        ocf_s = cf_sign(fin.get("ocf"))
        icf_s = cf_sign(fin.get("icf"))
        fcf_s = cf_sign(fin.get("fcf"))
        good_cf = (ocf_s == "+" and icf_s == "−" and fcf_s == "−")

        news_items = "\n".join(
            f"  • {n['title'].rsplit(' - ',1)[0].strip()}"
            for n in news_map.get(s["ticker"], [])[:3]
        )

        block = (
            f"\n[{s['ticker']}]\n"
            f"주가: {format_price(s['current'], cur)} ({sign}{abs(s['change_pct']):.2f}%){alert}\n"
            f"── 기술적 ──\n"
            f"이동평균: {ta.get('alignment','N/A')}{cross_str}{pullback_str}\n"
            f"볼린저밴드: {ta.get('bb_position','N/A')}\n"
            f"이격도: {ta.get('disparity_label','N/A')}\n"
            f"캔들패턴: {', '.join(ta.get('candle_patterns',[]))}\n"
            f"지지선: {fp(ta.get('support'))} / 저항선: {fp(ta.get('resistance'))}\n"
            f"거래량: 평균대비 {vol.get('ratio',1):.1f}배 ({vol.get('label','')})\n"
            f"추세: {ta.get('trend','N/A')}{'(박스권)' if ta.get('is_box') else ''}\n"
            f"── 재무 ──\n"
            f"재무등급: {s.get('fin_grade','N/A')}\n"
            f"ROE: {pct(fin.get('roe'))} | 영업이익률: {pct(fin.get('op_margin'))} | 매출성장률: {pct(fin.get('rev_growth'))}\n"
            f"유동비율: {pct(fin.get('current_ratio'),0)} | 부채비율: {pct(fin.get('debt_equity'),0)}\n"
            f"현금흐름: 영업({ocf_s}) 투자({icf_s}) 재무({fcf_s}) → 우량패턴: {'O' if good_cf else 'X'}\n"
            f"이상신호: {', '.join(s.get('fin_warnings',['데이터없음']))}\n"
            f"── 뉴스 ──\n"
            f"{news_items if news_items else '  (뉴스 없음)'}"
        )
        stock_blocks.append(block)

    if is_aggressive:
        signal_choices = "강매수·매수·주목·관망·매도·강매도"
        signal_guide = (
            "공격형 기준: 골든크로스+정배열+볼린저하단+거래량급증→강매수 | "
            "눌림목+이격도≤98+양봉→매수 | 데드크로스+역배열→매도 | "
            "흑삼병+거래량급증하락+재무이상→강매도"
        )
    else:
        signal_choices = "매수·주목·관망·매도"
        signal_guide = (
            "안정형 기준: 정배열+이격도≤98+지지선+유동비율≥100%+부채비율≤200%→매수 | "
            "골든크로스 후 눌림목→주목 | 데드크로스·재무이상신호→관망"
        )

    # 종목별 출력 슬롯을 미리 헤더로 고정 — 모델이 빈칸만 채움
    valid = [s for s in stocks if not s.get("error")]
    output_slots = "\n\n".join(
        f"[{s['ticker']} | {s.get('name', s['ticker'])}]\n"
        f"시그널:\n"
        f"핵심 근거:\n"
        f"  1. [기술적]\n"
        f"  2. [재무]\n"
        f"  3. [뉴스]\n"
        f"주의사항:"
        for s in valid
    )

    return f"""투자 성향: {inv} | 날짜: {datetime.now().strftime('%Y-%m-%d')}
시그널 선택지: {signal_choices}
{signal_guide}

=== 데이터 ===
{''.join(stock_blocks)}

=== 작성 규칙 ===
- 아래 슬롯 {len(valid)}개를 순서대로 한 번씩만 채우세요.
- 슬롯 헤더([종목코드])를 추가하거나 반복하지 마세요.
- 각 근거는 1~2문장, 구체적 수치 포함.

=== 출력 (아래 빈칸만 채우세요) ===

{output_slots}

[오늘 시장 총평]
"""


def generate_signals(profile: dict, stocks: list[dict], news_map: dict) -> str:
    inv = type_label(profile["investment_type"])
    messages = [
        {
            "role": "system",
            "content": (
                f"당신은 {inv} 투자자 전담 주식 분석가입니다. "
                "주어진 출력 슬롯의 빈칸만 채웁니다. "
                "슬롯 헤더는 이미 작성되어 있으므로 절대 다시 쓰지 않습니다. "
                "각 슬롯은 정확히 한 번만 완성합니다."
            ),
        },
        {"role": "user", "content": build_signal_prompt(profile, stocks, news_map)},
    ]
    return call_solar(messages, temperature=0.2)


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    profile = load_profile()
    if not profile:
        print("❌ 투자 프로필이 없습니다. setup_profile.py 를 먼저 실행하세요.")
        sys.exit(1)

    _ensure_yfinance()

    now_str   = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    inv       = type_label(profile["investment_type"])
    threshold = profile.get("alert_threshold", 5.0)

    # ── 데이터 수집 ───────────────────────────────────────────────────────────
    stocks:   list[dict] = []
    news_map: dict[str, list] = {}

    for entry in profile["watchlist"]:
        ticker = entry["ticker"]
        name   = entry.get("name", ticker)
        print(f"  ▸ {name} ({ticker}) 조회 중...", end="\r", flush=True)

        sd = fetch_stock(ticker, profile["investment_type"])
        if sd is None or sd.get("error"):
            err = (sd.get("error", "데이터 없음") if sd else "데이터 없음")
            stocks.append(sd or {"ticker": ticker, "name": name, "error": err})
            continue

        sd["name"] = name
        stocks.append(sd)

        query = name if not name.replace("-", "").isalpha() else f"{name} 주가"
        news_map[ticker] = fetch_news_rss(query, max_items=4)

    # ── 리포트 출력 ───────────────────────────────────────────────────────────
    print("\r" + " " * 55 + "\r", end="")  # 진행 메시지 지우기

    print(_divider("═"))
    print(f"  📈  주식 일일 브리핑  —  {now_str}")
    print(f"  투자 성향 : {inv}   |   급변 기준 : ±{threshold}%")
    print(_divider("═"))

    alerts = [s for s in stocks if not s.get("error") and abs(s.get("change_pct", 0)) >= threshold]
    if alerts:
        print()
        print("  ⚡ 급변 종목")
        for a in alerts:
            sign = "▲" if a["change_pct"] > 0 else "▼"
            print(f"    {a.get('name', a['ticker'])}  {sign}{abs(a['change_pct']):.2f}%")

    for s in stocks:
        print()
        name = s.get("name", s["ticker"])
        if s.get("error"):
            print(_header(f"{s['ticker']}  {name}"))
            print(f"  ⚠️  조회 실패: {s['error']}")
            continue
        print_stock_section(s, name, news_map.get(s["ticker"], []))

    # ── AI 종합 분석 ──────────────────────────────────────────────────────────
    print(_divider())
    if not UPSTAGE_API_KEY:
        print("  ⚠️  UPSTAGE_API_KEY 미설정 — AI 시그널을 표시하려면 API 키를 설정하세요.")
        print("     https://console.upstage.ai")
    else:
        print("  🤖  Solar Pro 3 종합 분석 중 (기술적 + 재무 + 뉴스)...\n")
        analysis = generate_signals(profile, stocks, news_map)
        print(analysis)
    print(_divider())

    profile["last_briefing"] = datetime.now().isoformat()
    save_profile(profile)
    print(f"\n  ✅  브리핑 완료 — {datetime.now().strftime('%H:%M')}\n")


if __name__ == "__main__":
    main()
