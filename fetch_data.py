#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
증시 각도기 스타일 시장 대시보드 - 데이터 수집 스크립트

매일 GitHub Actions(오전 6:40 KST)가 이 스크립트를 실행합니다.
- 원자재 / 환율 / 금리 항목의 최신 종가를 수집
- data/history.json 에 거래일 기준으로 누적 저장(중복 날짜는 갱신)
- 각 항목의 최근 두 거래일(당일/전일)을 비교해 index.html 을 새로 생성

데이터 소스(모두 무료·인증 불필요):
  - 미국 국채 금리 : 미국 재무부 공식 일별 금리 CSV
  - 그 외 전 항목  : stooq.com 일별 CSV
  - 예비(fallback) : Yahoo Finance chart API
각 항목은 실패해도 전체가 멈추지 않도록 개별 예외 처리합니다.
"""

import csv
import io
import json
import os
import sys
import time
import datetime as dt
from zoneinfo import ZoneInfo

import requests

KST = ZoneInfo("Asia/Seoul")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
HISTORY_PATH = os.path.join(DATA_DIR, "history.json")
INDEX_PATH = os.path.join(HERE, "index.html")
TEMPLATE_PATH = os.path.join(HERE, "template.html")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MarketDashboard/1.0)"}
MAX_HISTORY = 260          # 항목별 보관할 최대 거래일 수
TIMEOUT = 20

# ----------------------------------------------------------------------------
# 추적 항목 정의  (디자인의 3개 화면 = 3개 그룹)
#   dec       : 소수점 자리수
#   thousands : 천단위 콤마 표시 여부
#   icon      : 카드에 표시할 아이콘(이모지)
#   sources   : 순서대로 시도할 데이터 소스
# ----------------------------------------------------------------------------
GROUPS = [
    {
        "id": "commodity", "title": "원자재", "subtitle": "출처 stooq",
        "subgroups": [
            {"label": "원유 · 에너지", "items": [
                {"key": "wti",     "name": "WTI",     "icon": "🛢️", "dec": 2, "thousands": False, "sources": [("stooq", "cl.f"), ("yahoo", "CL=F")]},
                {"key": "brent",   "name": "브렌트",   "icon": "🛢️", "dec": 2, "thousands": False, "sources": [("stooq", "cb.f"), ("yahoo", "BZ=F")]},
                {"key": "gasoline","name": "가솔린",   "icon": "⛽", "dec": 4, "thousands": False, "sources": [("stooq", "rb.f"), ("yahoo", "RB=F")]},
            ]},
            {"label": "금속", "items": [
                {"key": "gold",    "name": "금",       "icon": "🥇", "dec": 2, "thousands": True,  "sources": [("stooq", "gc.f"),  ("yahoo", "GC=F")]},
                {"key": "silver",  "name": "은",       "icon": "🥈", "dec": 3, "thousands": False, "sources": [("stooq", "si.f"),  ("yahoo", "SI=F")]},
                {"key": "copper",  "name": "구리",     "icon": "🟠", "dec": 4, "thousands": False, "sources": [("stooq", "hg.f"),  ("yahoo", "HG=F")]},
                {"key": "alu",     "name": "알루미늄", "icon": "⚪", "dec": 2, "thousands": True,  "sources": [("stooq", "ali.f"), ("yahoo", "ALI=F")]},
            ]},
            {"label": "지수 · 기타", "items": [
                {"key": "vix",     "name": "VIX",     "icon": "📊", "dec": 2, "thousands": False, "sources": [("stooq", "^vix"),  ("yahoo", "^VIX")]},
                {"key": "btc",     "name": "비트코인", "icon": "🪙", "dec": 0, "thousands": True,  "sources": [("stooq", "btc.v"), ("yahoo", "BTC-USD")]},
            ]},
        ],
    },
    {
        "id": "fx", "title": "외환 동향", "subtitle": "출처 stooq",
        "subgroups": [
            {"label": "달러 (기축통화)", "items": [
                {"key": "dxy",    "name": "달러지수",  "icon": "🇺🇸", "dec": 2, "thousands": False, "sources": [("stooq", "dx.f"),   ("yahoo", "DX-Y.NYB")]},
                {"key": "eurusd", "name": "유로/달러", "icon": "🇪🇺", "dec": 4, "thousands": False, "sources": [("stooq", "eurusd"), ("yahoo", "EURUSD=X")]},
                {"key": "usdjpy", "name": "달러/엔",   "icon": "🇯🇵", "dec": 2, "thousands": False, "sources": [("stooq", "usdjpy"), ("yahoo", "USDJPY=X")]},
                {"key": "usdcny", "name": "달러/위안", "icon": "🇨🇳", "dec": 4, "thousands": False, "sources": [("stooq", "usdcny"), ("yahoo", "USDCNY=X")]},
            ]},
            {"label": "원화 환율", "items": [
                {"key": "usdkrw", "name": "달러/원",   "icon": "🇰🇷", "dec": 2, "thousands": True,  "sources": [("stooq", "usdkrw"), ("yahoo", "USDKRW=X")]},
                {"key": "eurkrw", "name": "유로/원",   "icon": "🇪🇺", "dec": 2, "thousands": True,  "sources": [("stooq", "eurkrw"), ("yahoo", "EURKRW=X")]},
                {"key": "jpykrw", "name": "엔/원",     "icon": "🇯🇵", "dec": 4, "thousands": False, "sources": [("stooq", "jpykrw"), ("yahoo", "JPYKRW=X")]},
            ]},
        ],
    },
    {
        "id": "rates", "title": "금리 동향", "subtitle": "출처 미국 재무부 · stooq",
        "subgroups": [
            {"label": "미국", "items": [
                {"key": "us10y", "name": "10년물",  "icon": "🇺🇸", "dec": 3, "thousands": False, "sources": [("ust", "10 Yr"), ("stooq", "10yusy.b"), ("yahoo", "^TNX")]},
                {"key": "us5y",  "name": "5년물",   "icon": "🇺🇸", "dec": 3, "thousands": False, "sources": [("ust", "5 Yr"),  ("stooq", "5yusy.b"),  ("yahoo", "^FVX")]},
                {"key": "us2y",  "name": "2년물",   "icon": "🇺🇸", "dec": 3, "thousands": False, "sources": [("ust", "2 Yr"),  ("stooq", "2yusy.b")]},
                {"key": "us1y",  "name": "1년물",   "icon": "🇺🇸", "dec": 3, "thousands": False, "sources": [("ust", "1 Yr"),  ("stooq", "1yusy.b")]},
                {"key": "us3m",  "name": "3개월물", "icon": "🇺🇸", "dec": 3, "thousands": False, "sources": [("ust", "3 Mo"),  ("stooq", "3musy.b"), ("yahoo", "^IRX")]},
                {"key": "us30y", "name": "30년물",  "icon": "🇺🇸", "dec": 3, "thousands": False, "sources": [("ust", "30 Yr"), ("stooq", "30yusy.b"), ("yahoo", "^TYX")]},
            ]},
            {"label": "일본", "items": [
                {"key": "jp10y", "name": "10년물",  "icon": "🇯🇵", "dec": 4, "thousands": False, "sources": [("stooq", "10yjpy.b")]},
                {"key": "jp30y", "name": "30년물",  "icon": "🇯🇵", "dec": 3, "thousands": False, "sources": [("stooq", "30yjpy.b")]},
            ]},
            {"label": "독일", "items": [
                {"key": "de10y", "name": "10년물",  "icon": "🇩🇪", "dec": 4, "thousands": False, "sources": [("stooq", "10ydey.b")]},
            ]},
        ],
    },
]


def all_items():
    """모든 그룹/서브그룹의 항목을 평탄화해 순회."""
    for g in GROUPS:
        for sub in g["subgroups"]:
            for it in sub["items"]:
                yield it

# ----------------------------------------------------------------------------
# 데이터 소스별 수집 함수 : {date(str) -> close(float)} 반환
# ----------------------------------------------------------------------------
_UST_CACHE = None


def fetch_stooq(symbol):
    """stooq 일별 CSV. Date,Open,High,Low,Close,Volume"""
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    text = r.text.strip()
    if not text or text.lower().startswith("<") or "no data" in text.lower():
        raise ValueError(f"stooq no data for {symbol}")
    out = {}
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        d = (row.get("Date") or "").strip()
        c = (row.get("Close") or "").strip()
        if not d or c in ("", "N/A"):
            continue
        try:
            out[d] = float(c)
        except ValueError:
            continue
    if not out:
        raise ValueError(f"stooq empty parse for {symbol}")
    return out


def fetch_ust(column):
    """미국 재무부 일별 금리 CSV(당해 연도). column 예: '10 Yr'"""
    global _UST_CACHE
    if _UST_CACHE is None:
        year = dt.datetime.now(KST).year
        url = (
            "https://home.treasury.gov/resource-center/data-chart-center/"
            f"interest-rates/daily-treasury-rates.csv/{year}/all"
            "?type=daily_treasury_yield_curve&_format=csv"
        )
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        _UST_CACHE = list(csv.DictReader(io.StringIO(r.text)))
    out = {}
    for row in _UST_CACHE:
        raw_date = (row.get("Date") or "").strip()
        val = (row.get(column) or "").strip()
        if not raw_date or val in ("", "N/A"):
            continue
        # 재무부 날짜형식 MM/DD/YYYY -> YYYY-MM-DD
        try:
            d = dt.datetime.strptime(raw_date, "%m/%d/%Y").strftime("%Y-%m-%d")
            out[d] = float(val)
        except ValueError:
            continue
    if not out:
        raise ValueError(f"UST empty for {column}")
    return out


def fetch_yahoo(symbol):
    """Yahoo Finance chart API (예비 소스)."""
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        "?interval=1d&range=1mo"
    )
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    js = r.json()
    res = js["chart"]["result"][0]
    ts = res["timestamp"]
    closes = res["indicators"]["quote"][0]["close"]
    out = {}
    for t, c in zip(ts, closes):
        if c is None:
            continue
        d = dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
        out[d] = float(c)
    if not out:
        raise ValueError(f"yahoo empty for {symbol}")
    return out


SOURCE_FUNCS = {"stooq": fetch_stooq, "ust": fetch_ust, "yahoo": fetch_yahoo}


def fetch_item(item):
    """정의된 소스를 순서대로 시도. 첫 성공 결과({date:close}) 반환."""
    errors = []
    for kind, sym in item["sources"]:
        try:
            data = SOURCE_FUNCS[kind](sym)
            if data:
                return data, f"{kind}:{sym}"
        except Exception as e:  # noqa: BLE001
            errors.append(f"{kind}:{sym} -> {e}")
        time.sleep(0.4)
    print(f"  [WARN] {item['key']} 모든 소스 실패: {' | '.join(errors)}", file=sys.stderr)
    return {}, None


# ----------------------------------------------------------------------------
# 누적 저장 / 병합
# ----------------------------------------------------------------------------
def load_history():
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            pass
    return {"series": {}, "meta": {}}


def merge_series(existing, new_points):
    """existing: [[date, close], ...] , new_points: {date: close}"""
    merged = {d: c for d, c in existing}
    merged.update(new_points)          # 같은 날짜는 새 값으로 갱신
    ordered = sorted(merged.items(), key=lambda kv: kv[0])
    ordered = ordered[-MAX_HISTORY:]
    return [[d, c] for d, c in ordered]


def fmt(value, dec, thousands):
    if value is None:
        return "—"
    q = round(float(value), dec)
    if thousands:
        return f"{q:,.{dec}f}"
    return f"{q:.{dec}f}"


def _item_payload(it, series):
    pts = series.get(it["key"], [])
    cur = prev = None
    cur_date = prev_date = None
    if len(pts) >= 1:
        cur_date, cur = pts[-1]
    if len(pts) >= 2:
        prev_date, prev = pts[-2]
    change = pct = None
    direction = "flat"
    if cur is not None and prev is not None:
        change = cur - prev
        if prev != 0:
            pct = change / abs(prev) * 100
        if change > 1e-12:
            direction = "up"
        elif change < -1e-12:
            direction = "down"
    return {
        "name": it["name"],
        "icon": it["icon"],
        "cur": fmt(cur, it["dec"], it["thousands"]),
        "prev": fmt(prev, it["dec"], it["thousands"]),
        "change": ("—" if change is None else fmt(abs(change), it["dec"], it["thousands"])),
        "pct": ("—" if pct is None else f"{abs(pct):.2f}"),
        "direction": direction,
        "cur_date": cur_date or "",
        "prev_date": prev_date or "",
    }


def build_render_payload(history):
    """각 항목의 최근 두 거래일로 당일/전일/변화 계산 (서브그룹 구조 유지)."""
    series = history["series"]
    groups_out = []
    for g in GROUPS:
        subs_out = []
        for sub in g["subgroups"]:
            subs_out.append({
                "label": sub["label"],
                "items": [_item_payload(it, series) for it in sub["items"]],
            })
        groups_out.append({
            "id": g["id"], "title": g["title"], "subtitle": g["subtitle"],
            "subgroups": subs_out,
        })
    return groups_out


def render_html(groups_out, updated_kst):
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()
    payload = {"updated": updated_kst, "groups": groups_out}
    data_json = json.dumps(payload, ensure_ascii=False)
    return template.replace("/*__DATA__*/null", data_json)


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    now_kst = dt.datetime.now(KST)
    print(f"[RUN] {now_kst:%Y-%m-%d %H:%M} KST")

    history = load_history()
    series = history.setdefault("series", {})
    ok, fail = 0, 0

    for it in all_items():
        data, src = fetch_item(it)
        if data:
            series[it["key"]] = merge_series(series.get(it["key"], []), data)
            ok += 1
            last = series[it["key"]][-1]
            print(f"  [OK]  {it['key']:8s} <- {src:18s} last {last[0]} = {last[1]}")
        else:
            fail += 1
        # 항목별 series 는 있으면 유지(이전 값 보존)

    history["meta"] = {
        "updated_at_kst": now_kst.strftime("%Y-%m-%d %H:%M"),
        "ok": ok, "fail": fail,
    }
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=1)

    groups_out = build_render_payload(history)
    html = render_html(groups_out, now_kst.strftime("%Y-%m-%d %H:%M"))
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[DONE] 성공 {ok} / 실패 {fail}  -> index.html, data/history.json 갱신")
    # 전부 실패한 경우에만 오류 종료(부분 실패는 정상 진행)
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
