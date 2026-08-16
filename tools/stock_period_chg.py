#!/usr/bin/env python3
"""东财 push2：个股多周期涨跌幅（A股持仓 §7 周期势用）。

字段映射（实测与腾讯前复权 K 对齐）：
  f127  3日   f109  5日   f160  10日
  f110  20日  f24   60日  f25   年初至今
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests

_HOSTS = (
    "https://push2delay.eastmoney.com/api/qt/ulist.np/get",
    "https://82.push2.eastmoney.com/api/qt/ulist.np/get",
    "https://push2.eastmoney.com/api/qt/ulist.np/get",
)
_FIELDS = "f12,f14,f2,f3,f127,f109,f160,f110,f24,f25"
_HEADERS = {"Referer": "https://quote.eastmoney.com/"}
_UT = "bd1d9ddb04089700cf9c27f6f7426281"


def secid(code: str) -> str:
    c = code.strip().zfill(6)
    market = "1" if c.startswith("6") else "0"
    return f"{market}.{c}"


def fetch_period_chg(code: str) -> dict[str, Any] | None:
    sid = secid(code)
    params = {
        "secids": sid,
        "fields": _FIELDS,
        "ut": _UT,
        "fltt": 2,
    }
    last_err: Exception | None = None
    for host in _HOSTS:
        try:
            r = requests.get(
                host,
                params=params,
                headers=_HEADERS,
                timeout=20,
                proxies={"http": None, "https": None},
            )
            r.raise_for_status()
            diff = (r.json().get("data") or {}).get("diff") or []
            if not diff:
                continue
            row = diff[0]
            return {
                "code": row.get("f12") or code,
                "name": row.get("f14") or "",
                "close": row.get("f2"),
                "chg_pct": row.get("f3"),
                "pct_3d": row.get("f127"),
                "pct_5d": row.get("f109"),
                "pct_10d": row.get("f160"),
                "pct_20d": row.get("f110"),
                "pct_60d": row.get("f24"),
                "pct_ytd": row.get("f25"),
                "source": "eastmoney_push2",
            }
        except Exception as e:
            last_err = e
    if last_err:
        print(f"[stock_period_chg] 失败 {code}: {last_err}", file=sys.stderr)
    return None


def fmt_pct(v: Any) -> str:
    if v is None or v == "-" or v == "":
        return "—"
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return str(v)


def main() -> None:
    p = argparse.ArgumentParser(description="东财多周期涨跌幅")
    p.add_argument("codes", nargs="+", help="A股代码，如 002455 600519")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    args = p.parse_args()
    rows = []
    for code in args.codes:
        row = fetch_period_chg(code)
        if row:
            rows.append(row)
        else:
            rows.append({"code": code, "error": "未获取"})

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    for row in rows:
        if row.get("error"):
            print(f"{row['code']}: {row['error']}")
            continue
        print(
            f"{row['code']} {row['name']} 收{row['close']} 当日{fmt_pct(row['chg_pct'])} | "
            f"3日{fmt_pct(row['pct_3d'])} 5日{fmt_pct(row['pct_5d'])} "
            f"10日{fmt_pct(row['pct_10d'])} 20日{fmt_pct(row['pct_20d'])} "
            f"60日{fmt_pct(row['pct_60d'])} 年初至今{fmt_pct(row['pct_ytd'])}"
        )


if __name__ == "__main__":
    main()
