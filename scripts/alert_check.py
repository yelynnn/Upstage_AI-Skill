"""급변 알림 체크 — ±threshold% 초과 종목 감지 및 긴급 AI 분석"""

import sys
import subprocess
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_profile,
    call_solar,
    fetch_news_rss,
    format_price,
    type_label,
    UPSTAGE_API_KEY,
)


def _ensure_yfinance():
    try:
        import yfinance  # noqa: F401
    except ImportError:
        print("  yfinance 설치 중...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "yfinance", "-q"],
            check=True,
        )


def check_alerts(profile: dict) -> list[dict]:
    import yfinance as yf

    threshold = profile.get("alert_threshold", 5.0)
    alerts = []

    for entry in profile["watchlist"]:
        ticker = entry["ticker"]
        name = entry.get("name", ticker)

        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if len(hist) < 2:
                continue

            current = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            change_pct = (current - prev) / prev * 100

            info = {}
            try:
                info = t.info
            except Exception:
                pass
            currency = info.get("currency") or (
                "KRW" if (".KS" in ticker or ".KQ" in ticker) else "USD"
            )

            if abs(change_pct) >= threshold:
                alerts.append(
                    {
                        "ticker": ticker,
                        "name": name,
                        "current": current,
                        "prev": prev,
                        "change_pct": change_pct,
                        "direction": "상승" if change_pct > 0 else "하락",
                        "currency": currency,
                    }
                )
        except Exception as e:
            print(f"  ⚠️  {name} ({ticker}) 조회 실패: {e}")

    return alerts


def emergency_analysis(profile: dict, alerts: list[dict], news_map: dict) -> str:
    inv = type_label(profile["investment_type"])

    alert_lines = []
    for a in alerts:
        sign = "▲" if a["change_pct"] > 0 else "▼"
        alert_lines.append(
            f"- {a['name']} ({a['ticker']}): "
            f"{format_price(a['current'], a['currency'])} "
            f"{sign}{abs(a['change_pct']):.2f}%  [{a['direction']}]"
        )

    news_lines = []
    for ticker, news in news_map.items():
        if news:
            news_lines.append(f"\n[{ticker} 뉴스]")
            for n in news[:2]:
                news_lines.append(f"  • {n['title']}")

    content = f"""⚡ 급변 감지 — {inv} 투자자 긴급 분석 요청

급변 종목:
{chr(10).join(alert_lines)}

관련 뉴스:
{"".join(news_lines) if news_lines else "  (뉴스 조회 불가)"}

각 급변 종목에 대해 아래 형식으로 답해주세요:

[종목명 | 종목코드]
긴급 시그널: 즉시매수 / 즉시매도 / 추가매수 / 일부매도 / 관망  (하나)
핵심 이유: 1문장
{inv} 대응 전략: 구체적 행동 지침 1~2문장

---
[종합 판단]
지금 {inv} 투자자가 가장 먼저 해야 할 일 1~2문장

한국어, 간결, 실용적으로."""

    messages = [
        {
            "role": "system",
            "content": (
                f"당신은 {inv} 투자자를 위한 긴급 주식 분석 전문가입니다. "
                "급변 상황에서 즉각적이고 실용적인 대응 전략을 제공합니다."
            ),
        },
        {"role": "user", "content": content},
    ]
    return call_solar(messages, temperature=0.15)


def main():
    profile = load_profile()
    if not profile:
        print("❌ 프로필 없음. setup_profile.py 를 먼저 실행해주세요.")
        sys.exit(1)

    _ensure_yfinance()

    threshold = profile.get("alert_threshold", 5.0)
    inv = type_label(profile["investment_type"])
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"\n{'=' * 55}")
    print(f"  ⚡  급변 알림 체크  —  {now_str}")
    print(f"  투자 성향: {inv}   |   기준: ±{threshold}%")
    print(f"{'=' * 55}\n")

    print("  종목 체크 중...")
    alerts = check_alerts(profile)

    if not alerts:
        print(f"\n  ✅  현재 ±{threshold}% 이상 급변 종목 없음\n")
        return

    print(f"\n  ⚡  급변 종목 {len(alerts)}개 감지!\n")
    for a in alerts:
        sign = "▲" if a["change_pct"] > 0 else "▼"
        price_str = format_price(a["current"], a["currency"])
        print(f"    • {a['name']} ({a['ticker']})")
        print(f"      {price_str}  {sign}{abs(a['change_pct']):.2f}%  [{a['direction']}]")
    print()

    # 급변 종목 뉴스 수집
    news_map: dict[str, list] = {}
    for a in alerts:
        query = f"{a['name']} 주가"
        news_map[a["ticker"]] = fetch_news_rss(query, max_items=3)

    # AI 긴급 분석
    if not UPSTAGE_API_KEY:
        print("  ⚠️  UPSTAGE_API_KEY 미설정 — AI 분석 없이 데이터만 표시됩니다.")
    else:
        print(f"  🤖  Solar Pro 3 긴급 분석 중...\n")
        analysis = emergency_analysis(profile, alerts, news_map)
        print("─" * 55)
        print(analysis)
        print("─" * 55)

    print(f"\n  ✅  체크 완료 — {datetime.now().strftime('%H:%M')}")


if __name__ == "__main__":
    main()
