#!/usr/bin/env python3
"""沪+深两市合计成交额：今日 / 较前一日 / 近5日均量（§1 量能）。

主源：腾讯 newfqkline（金额字段为万元；÷10000 → 亿）。
口径：上证 000001 + 深成 399001 日成交额相加（与扶摇 snapshot 沪深 turnover 一致）。
输出刻意极短，避免 Agent 读昨报烧 token。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

_SH = "sh000001"
_SZ = "sz399001"
_URLS = (
    "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get",
    "https://web.ifzq.gtimg.cn/appstock/app/newfqkline/get",
)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.qq.com/",
}


def _session():
    import requests

    s = requests.Session()
    s.trust_env = False
    s.headers.update(_HEADERS)
    return s


def _fetch_bars(sym: str, bars: int = 20) -> list[tuple[str, float]]:
    """Return [(date, amount_yi), ...] oldest→newest. amount in 亿元."""
    s = _session()
    last_err: Exception | None = None
    for url in _URLS:
        try:
            r = s.get(url, params={"param": f"{sym},day,,,{bars},"}, timeout=20)
            r.raise_for_status()
            block = r.json().get("data", {}).get(sym, {})
            rows = block.get("day") or block.get("qfqday") or []
            out: list[tuple[str, float]] = []
            for row in rows:
                if len(row) < 9:
                    continue
                try:
                    # newfqkline: [date,o,c,h,l,vol,{},chg,amount_万元,...]
                    amt_wan = float(row[8])
                except (TypeError, ValueError):
                    continue
                out.append((str(row[0]), amt_wan / 10000.0))
            if len(out) >= 2:
                return out
            last_err = RuntimeError(f"{sym} K线过短({len(out)})")
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"腾讯日K失败 {sym}: {last_err}")


def analyze(bars: int = 20, expect_year: int | None = None) -> dict[str, Any]:
    if expect_year is None:
        expect_year = datetime.now(ZoneInfo("Asia/Shanghai")).year

    sh = _fetch_bars(_SH, bars=bars)
    sz = _fetch_bars(_SZ, bars=bars)
    by_sh = {d: a for d, a in sh}
    by_sz = {d: a for d, a in sz}
    dates = sorted(set(by_sh) & set(by_sz))
    if len(dates) < 2:
        return {"error": "沪深可对齐交易日不足", "source": "tencent_newfqkline"}

    series = [(d, by_sh[d] + by_sz[d]) for d in dates]
    today_d, today_v = series[-1]
    prev_d, prev_v = series[-2]
    last5 = series[-5:] if len(series) >= 5 else series
    ma5 = sum(v for _, v in last5) / len(last5)
    chg = today_v - prev_v
    chg_pct = (chg / prev_v * 100.0) if prev_v else None

    # 防串年：最新一根日期年份必须等于当前复盘年
    try:
        y = int(today_d[:4])
    except ValueError:
        y = -1
    if y != expect_year:
        return {
            "error": f"串年嫌疑：最新K日期 {today_d} 非期望年 {expect_year}",
            "source": "tencent_newfqkline",
            "as_of": today_d,
        }

    label = "放量" if chg_pct is not None and chg_pct >= 3 else (
        "缩量" if chg_pct is not None and chg_pct <= -3 else "平量"
    )

    return {
        "as_of": today_d,
        "prev_date": prev_d,
        "today_yi": round(today_v, 2),
        "prev_yi": round(prev_v, 2),
        "chg_yi": round(chg, 2),
        "chg_pct": round(chg_pct, 2) if chg_pct is not None else None,
        "ma5_yi": round(ma5, 2),
        "ma5_n": len(last5),
        "sh_yi": round(by_sh[today_d], 2),
        "sz_yi": round(by_sz[today_d], 2),
        "label": label,
        "expect_year": expect_year,
        "source": "tencent_newfqkline",
        "note": "沪000001+深399001；腾讯金额万元÷10000=亿；近5日=最近5个对齐交易日均量",
    }


def one_liner(rep: dict[str, Any]) -> str:
    if rep.get("error"):
        return f"ERROR {rep['error']} source={rep.get('source')}"
    chg = rep["chg_pct"]
    chg_s = f"{chg:+.1f}%" if chg is not None else "—"
    return (
        f"today={rep['today_yi']:.0f}亿({rep['as_of']}) "
        f"prev={rep['prev_yi']:.0f}亿({rep['prev_date']}) "
        f"chg={rep['chg_yi']:+.0f}亿({chg_s}) "
        f"ma5={rep['ma5_yi']:.0f}亿(n={rep['ma5_n']}) "
        f"sh={rep['sh_yi']:.0f} sz={rep['sz_yi']:.0f} "
        f"→{rep['label']} source={rep['source']}"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="两市成交额：今日/昨/近5日均（腾讯）")
    p.add_argument("--bars", type=int, default=20, help="各指数拉取日K根数")
    p.add_argument("--year", type=int, default=None, help="期望年份（默认上海时区今年）")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    try:
        rep = analyze(bars=args.bars, expect_year=args.year)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(one_liner(rep))
    if rep.get("error"):
        sys.exit(2)


if __name__ == "__main__":
    main()
