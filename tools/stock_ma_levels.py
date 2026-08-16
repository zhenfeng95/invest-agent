#!/usr/bin/env python3
"""A股个股 MA60 / MA120 / MA250 及距收盘延伸（§7 空间势用）。

日 K：腾讯前复权 qfqday（与 mtd_screener 兜底同源）。
较近默认 |收盘/MA−1|≤3% → space_tight（空间不足）。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests

_NEAR_PCT_DEFAULT = 3.0


def _symbol(code: str) -> str:
    c = code.strip().zfill(6)
    if c.startswith(("5", "6", "9")):
        return f"sh{c}"
    return f"sz{c}"


def fetch_closes_qfq(code: str, bars: int = 320) -> list[tuple[str, float]]:
    sym = _symbol(code)
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={sym},day,,,{bars},qfq"
    )
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    block = r.json().get("data", {}).get(sym, {})
    rows = block.get("qfqday") or block.get("day") or []
    out: list[tuple[str, float]] = []
    for row in rows:
        if len(row) < 3:
            continue
        try:
            out.append((row[0], float(row[2])))
        except (TypeError, ValueError):
            continue
    return out


def _sma(closes: list[float], n: int) -> float | None:
    if len(closes) < n:
        return None
    seg = closes[-n:]
    return sum(seg) / n


def analyze(code: str, near_pct: float = _NEAR_PCT_DEFAULT) -> dict[str, Any]:
    hist = fetch_closes_qfq(code)
    if len(hist) < 60:
        return {"code": code, "error": "K线不足60日", "source": "tencent_qfq"}
    dates = [x[0] for x in hist]
    closes = [x[1] for x in hist]
    close = closes[-1]
    as_of = dates[-1]

    levels: dict[str, Any] = {}
    tight_labels: list[str] = []
    for label, n in [("ma60", 60), ("ma120", 120), ("ma250", 250)]:
        ma = _sma(closes, n)
        if ma is None or ma <= 0:
            levels[label] = None
            continue
        dist_pct = (close / ma - 1.0) * 100.0
        near = abs(dist_pct) <= near_pct
        pos = "上" if dist_pct > 0 else "下"
        levels[label] = {
            "value": round(ma, 3),
            "dist_pct": round(dist_pct, 2),
            "position": pos,
            "near": near,
        }
        if near:
            tight_labels.append(f"MA{n}{pos}方贴压(距{abs(dist_pct):.2f}%)")

    return {
        "code": code.zfill(6),
        "as_of": as_of,
        "close": round(close, 3),
        "near_pct_threshold": near_pct,
        "ma60": levels.get("ma60"),
        "ma120": levels.get("ma120"),
        "ma250": levels.get("ma250"),
        "space_tight": bool(tight_labels),
        "space_tight_reason": "；".join(tight_labels) if tight_labels else "",
        "source": "tencent_qfq",
    }


def fmt_ma(ma: dict[str, Any] | None) -> str:
    if not ma:
        return "—"
    return f"{ma['value']:.2f}({ma['dist_pct']:+.2f}%)"


def main() -> None:
    p = argparse.ArgumentParser(description="MA60/120/250 与空间贴压")
    p.add_argument("codes", nargs="+", help="A股代码")
    p.add_argument("--near-pct", type=float, default=_NEAR_PCT_DEFAULT, help="较近阈值%")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    rows = [analyze(c, near_pct=args.near_pct) for c in args.codes]

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    for row in rows:
        if row.get("error"):
            print(f"{row.get('code', '')}: {row['error']}")
            continue
        tight = "空间不足" if row["space_tight"] else "空间尚可"
        print(
            f"{row['code']} 收{row['close']}({row['as_of']}) "
            f"MA60={fmt_ma(row['ma60'])} MA120={fmt_ma(row['ma120'])} "
            f"MA250={fmt_ma(row['ma250'])} → {tight}"
            + (f"（{row['space_tight_reason']}）" if row["space_tight_reason"] else "")
        )


if __name__ == "__main__":
    main()
