"""투자 프로필 초기 설정 - 한 번만 실행"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import load_profile, save_profile, DATA_DIR, PROFILE_FILE


# ── 국내 주요 종목 DB (종목명 → 코드) ────────────────────────────────────────
STOCK_DB: dict[str, str] = {
    # 반도체
    "삼성전자":   "005930",
    "SK하이닉스": "000660",
    "삼성전기":   "009150",
    "DB하이텍":   "000990",
    "리노공업":   "058470",
    "ISC":        "095340",
    "원익IPS":    "240810",
    "피에스케이":  "319660",
    "이오테크닉스": "039030",
    # 배터리/전기차
    "LG에너지솔루션": "373220",
    "삼성SDI":     "006400",
    "SK이노베이션": "096770",
    "에코프로비엠":  "247540",
    "에코프로":     "086520",
    "포스코퓨처엠":  "003670",
    "엘앤에프":     "066970",
    "코스모신소재":  "005070",
    # IT/플랫폼
    "NAVER":       "035420",
    "카카오":      "035720",
    "넥슨게임즈":   "225570",
    "카카오게임즈":  "293490",
    "크래프톤":     "259960",
    "엔씨소프트":   "036570",
    "넷마블":      "251270",
    "더블유게임즈":  "192080",
    # 바이오/헬스케어
    "삼성바이오로직스": "207940",
    "셀트리온":    "068270",
    "셀트리온헬스케어": "091990",
    "유한양행":    "000100",
    "HLB":         "028300",
    "알테오젠":    "196170",
    "리가켐바이오":  "141080",
    "오스코텍":    "039200",
    # 금융
    "KB금융":     "105560",
    "신한지주":   "055550",
    "하나금융지주": "086790",
    "우리금융지주": "316140",
    "삼성생명":   "032830",
    "삼성화재":   "000810",
    "미래에셋증권": "006800",
    "키움증권":   "039490",
    # 자동차
    "현대차":     "005380",
    "기아":       "000270",
    "현대모비스":  "012330",
    "한온시스템":  "018880",
    "현대위아":   "011210",
    # 에너지/화학
    "LG화학":     "051910",
    "롯데케미칼":  "011170",
    "금호석유":   "011780",
    "한화솔루션":  "009830",
    "OCI":        "010060",
    # 통신
    "SK텔레콤":   "017670",
    "KT":         "030200",
    "LG유플러스":  "032640",
    # 철강/소재
    "POSCO홀딩스": "005490",
    "현대제철":   "004020",
    "고려아연":   "010130",
    # 유통/소비재
    "삼성물산":   "028260",
    "LG":         "003550",
    "SK":         "034730",
    "롯데쇼핑":   "023530",
    "이마트":     "139480",
    "CJ제일제당":  "097950",
    # 건설/인프라
    "현대건설":   "000720",
    "GS건설":     "006360",
    "대우건설":   "047040",
    # 항공/운송
    "대한항공":   "003490",
    "아시아나항공": "020560",
    "HMM":        "011200",
}

# ── 분야 DB (분야명 → 대표 종목 리스트) ─────────────────────────────────────
SECTOR_DB: dict[str, list[str]] = {
    "반도체": ["삼성전자", "SK하이닉스", "리노공업", "DB하이텍", "원익IPS", "이오테크닉스", "피에스케이"],
    "배터리": ["LG에너지솔루션", "삼성SDI", "SK이노베이션", "에코프로비엠", "에코프로", "포스코퓨처엠", "엘앤에프"],
    "2차전지": ["LG에너지솔루션", "삼성SDI", "SK이노베이션", "에코프로비엠", "에코프로", "포스코퓨처엠", "엘앤에프"],
    "전기차": ["현대차", "기아", "LG에너지솔루션", "삼성SDI", "에코프로비엠", "한온시스템"],
    "바이오": ["삼성바이오로직스", "셀트리온", "셀트리온헬스케어", "유한양행", "HLB", "알테오젠", "리가켐바이오"],
    "헬스케어": ["삼성바이오로직스", "셀트리온", "유한양행", "HLB", "알테오젠", "오스코텍"],
    "제약": ["유한양행", "셀트리온", "HLB", "오스코텍", "리가켐바이오"],
    "IT": ["NAVER", "카카오", "크래프톤", "엔씨소프트", "넷마블"],
    "게임": ["크래프톤", "엔씨소프트", "넷마블", "카카오게임즈", "넥슨게임즈", "더블유게임즈"],
    "플랫폼": ["NAVER", "카카오", "카카오게임즈"],
    "금융": ["KB금융", "신한지주", "하나금융지주", "우리금융지주", "삼성생명", "삼성화재"],
    "은행": ["KB금융", "신한지주", "하나금융지주", "우리금융지주"],
    "보험": ["삼성생명", "삼성화재"],
    "증권": ["미래에셋증권", "키움증권"],
    "자동차": ["현대차", "기아", "현대모비스", "한온시스템", "현대위아"],
    "에너지": ["한화솔루션", "OCI", "SK이노베이션"],
    "화학": ["LG화학", "롯데케미칼", "금호석유", "한화솔루션"],
    "통신": ["SK텔레콤", "KT", "LG유플러스"],
    "철강": ["POSCO홀딩스", "현대제철", "고려아연"],
    "소재": ["POSCO홀딩스", "고려아연", "LG화학", "포스코퓨처엠"],
    "유통": ["롯데쇼핑", "이마트", "CJ제일제당"],
    "건설": ["현대건설", "GS건설", "대우건설"],
    "항공": ["대한항공", "아시아나항공"],
    "해운": ["HMM"],
    "운송": ["대한항공", "아시아나항공", "HMM"],
    "AI": ["NAVER", "삼성전자", "SK하이닉스", "카카오"],
    "방산": ["한화솔루션"],
}


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val if val else default


def select_investment_type() -> str:
    print("\n투자 성향을 선택해주세요:")
    print("  1. 공격형  — 높은 수익 추구, 리스크 적극 감수")
    print("  2. 안정형  — 안정적 수익 추구, 리스크 최소화")
    while True:
        choice = input("\n선택 (1/2): ").strip()
        if choice == "1":
            return "aggressive"
        if choice == "2":
            return "conservative"
        print("  → 1 또는 2를 입력해주세요.")


def fuzzy_search_stock(query: str) -> list[tuple[str, str]]:
    """종목명 부분 일치 검색 → [(종목명, 코드), ...]"""
    q = query.strip()
    exact = STOCK_DB.get(q)
    if exact:
        return [(q, exact)]
    return [(name, code) for name, code in STOCK_DB.items() if q in name]


def sector_search(query: str) -> list[str] | None:
    """분야명 검색 → 대표 종목 리스트 또는 None"""
    q = query.strip()
    if q in SECTOR_DB:
        return SECTOR_DB[q]
    for sector, stocks in SECTOR_DB.items():
        if q in sector:
            return stocks
    return None


def resolve_input(raw: str) -> list[dict] | None:
    """
    입력값을 분석해 종목 dict 리스트로 변환.
    None 반환 시 상위에서 직접 처리.
    """
    # 6자리 숫자 코드
    if raw.isdigit() and len(raw) == 6:
        ticker = f"{raw}.KS"
        name = input(f"    '{raw}' 종목명 (선택, 엔터 시 코드 사용): ").strip() or raw
        print(f"    ✅ {name} ({ticker}) 추가됨\n")
        return [{"ticker": ticker, "name": name, "display": raw}]

    # KOSDAQ 코드 (예: 035720.KQ)
    if "." in raw and raw.split(".")[0].isdigit():
        code, market = raw.upper().split(".", 1)
        ticker = f"{code}.{market}"
        name = input(f"    '{raw}' 종목명 (선택): ").strip() or raw
        print(f"    ✅ {name} ({ticker}) 추가됨\n")
        return [{"ticker": ticker, "name": name, "display": raw}]

    # 분야 검색
    sector_stocks = sector_search(raw)
    if sector_stocks:
        return _handle_sector(raw, sector_stocks)

    # 종목명 검색
    matches = fuzzy_search_stock(raw)
    if matches:
        return _handle_name_match(raw, matches)

    # 해외 티커로 간주
    ticker = raw.upper()
    name = input(f"    '{raw}' 종목명 (선택): ").strip() or raw
    print(f"    ✅ {name} ({ticker}) 추가됨\n")
    return [{"ticker": ticker, "name": name, "display": raw}]


def _handle_name_match(query: str, matches: list[tuple[str, str]]) -> list[dict]:
    if len(matches) == 1:
        name, code = matches[0]
        ticker = f"{code}.KS"
        print(f"    🔍 '{query}' → {name} ({code}) 자동 매핑")
        print(f"    ✅ {name} ({ticker}) 추가됨\n")
        return [{"ticker": ticker, "name": name, "display": code}]

    print(f"\n    🔍 '{query}' 검색 결과 ({len(matches)}건):")
    for i, (name, code) in enumerate(matches, 1):
        print(f"      {i}. {name} ({code})")
    print("      0. 직접 입력")

    while True:
        sel = input("    선택 번호: ").strip()
        if sel == "0":
            return []
        if sel.isdigit() and 1 <= int(sel) <= len(matches):
            name, code = matches[int(sel) - 1]
            ticker = f"{code}.KS"
            print(f"    ✅ {name} ({ticker}) 추가됨\n")
            return [{"ticker": ticker, "name": name, "display": code}]
        print("    → 올바른 번호를 입력해주세요.")


def _handle_sector(sector: str, stock_names: list[str]) -> list[dict]:
    print(f"\n    📂 '{sector}' 분야 대표 종목:")
    for i, name in enumerate(stock_names, 1):
        code = STOCK_DB.get(name, "?")
        print(f"      {i}. {name} ({code})")
    print("      A. 전체 추가")
    print("      0. 취소")

    while True:
        sel = input("    번호 선택 (복수: 1,3,5 / 전체: A / 취소: 0): ").strip().upper()
        if sel == "0":
            return []
        if sel == "A":
            selected = stock_names
            break
        parts = [p.strip() for p in sel.split(",")]
        if all(p.isdigit() and 1 <= int(p) <= len(stock_names) for p in parts):
            selected = [stock_names[int(p) - 1] for p in parts]
            break
        print("    → 올바른 번호를 입력해주세요.")

    result = []
    for name in selected:
        code = STOCK_DB.get(name)
        if code:
            ticker = f"{code}.KS"
            print(f"    ✅ {name} ({ticker}) 추가됨")
            result.append({"ticker": ticker, "name": name, "display": code})
    print()
    return result


def build_watchlist() -> list[dict]:
    print("\n관심 종목을 입력해주세요.")
    print("  입력 방법:")
    print("    종목명   → 삼성전자, SK하이닉스, NAVER  (자동 코드 매핑)")
    print("    분야명   → 반도체, 배터리, 바이오, AI  (대표 종목 추천)")
    print("    코드     → 005930  (6자리, KOSPI 자동 처리)")
    print("    KOSDAQ   → 035720.KQ")
    print("    해외     → AAPL, NVDA, TSLA")
    print("  완료 시 빈 줄 입력\n")

    watchlist: list[dict] = []
    while True:
        raw = input("  종목명/코드/분야 (완료 → 엔터): ").strip()
        if not raw:
            if watchlist:
                break
            print("  → 최소 1개 이상 입력해주세요.")
            continue

        added = resolve_input(raw)
        if added is not None:
            # 중복 제거
            existing_tickers = {s["ticker"] for s in watchlist}
            for item in added:
                if item["ticker"] not in existing_tickers:
                    watchlist.append(item)
                    existing_tickers.add(item["ticker"])
                else:
                    print(f"    ⚠️  {item['name']} 는 이미 추가되어 있습니다.\n")

    return watchlist


def main():
    print("\n" + "=" * 55)
    print("  📋  주식 브리핑 — 투자 프로필 설정")
    print("=" * 55)

    existing = load_profile()
    if existing:
        inv = "공격형" if existing["investment_type"] == "aggressive" else "안정형"
        stocks = ", ".join(s["name"] for s in existing["watchlist"])
        print(f"\n기존 프로필 발견:")
        print(f"  투자 성향 : {inv}")
        print(f"  관심 종목 : {stocks}")
        yn = input("\n새로 설정하시겠습니까? (y/N): ").strip().lower()
        if yn != "y":
            print("→ 기존 프로필 유지.")
            return

    investment_type = select_investment_type()
    label = "공격형" if investment_type == "aggressive" else "안정형"
    print(f"\n  ✅ {label} 선택됨")

    watchlist = build_watchlist()

    print("\n급변 알림 기준 설정:")
    print("  주가가 이 기준 이상 변동될 때 추가 알림을 표시합니다.")
    threshold_str = ask("  변동률 기준 (%)", "5.0")
    try:
        alert_threshold = float(threshold_str)
    except ValueError:
        alert_threshold = 5.0

    profile = {
        "investment_type": investment_type,
        "watchlist": watchlist,
        "alert_threshold": alert_threshold,
        "created_at": datetime.now().isoformat(),
        "last_briefing": None,
    }

    save_profile(profile)

    print(f"\n{'=' * 55}")
    print("  ✅  프로필 저장 완료!")
    print(f"  투자 성향 : {label}")
    for s in watchlist:
        print(f"  종목       : {s['name']} ({s['ticker']})")
    print(f"  급변 기준  : ±{alert_threshold}%")
    print(f"  저장 위치  : {PROFILE_FILE}")
    print("=" * 55)
    print("\n이제 daily_briefing.py 를 실행하면 브리핑을 받을 수 있습니다.")


if __name__ == "__main__":
    main()
