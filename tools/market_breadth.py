#!/usr/bin/env python3
"""东财涨跌家数 / 涨跌分布（§1 市场情绪用）。

主源：东财涨跌停专题「涨跌分布」接口 getTopicZDFenBu（一次返回，无需全市场分页）。
辅源：上证/深成指数页 f104/f105/f106（交易所侧宽度，非全市场精确口径）。

禁止：clist 全市场分页自己数涨跌（易触发「分页受限」）。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests

_FENBU_URLS = (
    "https://push2ex.eastmoney.com/getTopicZDFenBu",
    "https://push2delayex.eastmoney.com/getTopicZDFenBu",
)
_INDEX_URLS = (
    "https://push2.eastmoney.com/api/qt/ulist.np/get",
    "https://push2delay.eastmoney.com/api/qt/ulist.np/get",
    "https://82.push2.eastmoney.com/api/qt/ulist.np/get",
)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
_UT = "7eea3edcaed734bea9cbfc24409ed989"


def _get_json(urls: tuple[str, ...], params: dict[str, Any]) -> dict[str, Any] | None:
    last_err: Exception | None = None
    for url in urls:
        try:
            r = requests.get(
                url,
                params=params,
                headers=_HEADERS,
                timeout=20,
                proxies={"http": None, "https": None},
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
    if last_err:
        print(f"[market_breadth] 请求失败: {last_err}", file=sys.stderr)
    return None


def _parse_fenbu(raw: dict[str, Any]) -> dict[str, Any] | None:
    data = raw.get("data") or {}
    fenbu_list = data.get("fenbu") or []
    if not fenbu_list:
        return None
    buckets: dict[int, int] = {}
    for row in fenbu_list:
        if not isinstance(row, dict) or not row:
            continue
        k, v = next(iter(row.items()))
        try:
            buckets[int(k)] = int(v)
        except (TypeError, ValueError):
            continue
    if not buckets:
        return None
    up = sum(n for k, n in buckets.items() if k > 0)
    down = sum(n for k, n in buckets.items() if k < 0)
    flat = buckets.get(0, 0)
    # 东财桶约定：10≈涨停侧、−10≈跌停侧；11/−11 偶发辅桶，一并标出
    limit_up_like = buckets.get(10, 0) + buckets.get(11, 0)
    limit_down_like = buckets.get(-10, 0) + buckets.get(-11, 0)
    total = up + down + flat
    ratio = round(up / down, 2) if down else None
    qdate = data.get("qdate")
    trade_date = None
    if qdate is not None:
        s = str(qdate)
        if len(s) == 8:
            trade_date = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return {
        "trade_date": trade_date,
        "up": up,
        "down": down,
        "flat": flat,
        "total": total,
        "up_down_ratio": ratio,
        "limit_up_bucket": limit_up_like,
        "limit_down_bucket": limit_down_like,
        "buckets": {str(k): buckets[k] for k in sorted(buckets)},
        "source": "eastmoney_getTopicZDFenBu",
        "note": "全市场涨跌分布汇总；涨停/跌停请以扶摇涨跌停池为准，本接口 10/−10 桶仅供对照",
    }


def fetch_fenbu() -> dict[str, Any] | None:
    raw = _get_json(
        _FENBU_URLS,
        {"ut": _UT, "dpt": "wz.ztzt"},
    )
    if not raw or raw.get("rc") not in (0, None):
        return None
    return _parse_fenbu(raw)


def fetch_index_breadth() -> dict[str, Any] | None:
    """上证/深成指数页宽度（成分/交易所侧，非全市场精确口径）。"""
    raw = _get_json(
        _INDEX_URLS,
        {
            "fltt": 2,
            "secids": "1.000001,0.399001",
            "fields": "f12,f14,f104,f105,f106",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        },
    )
    if not raw:
        return None
    diff = (raw.get("data") or {}).get("diff") or []
    if not diff:
        return None
    out: dict[str, Any] = {"source": "eastmoney_index_f104", "items": []}
    for row in diff:
        out["items"].append(
            {
                "code": row.get("f12"),
                "name": row.get("f14"),
                "up": row.get("f104"),
                "down": row.get("f105"),
                "flat": row.get("f106"),
            }
        )
    return out


def build_report(*, with_index: bool = False) -> dict[str, Any]:
    fenbu = fetch_fenbu()
    report: dict[str, Any] = {
        "ok": bool(fenbu),
        "market": fenbu,
    }
    if with_index:
        report["index_side"] = fetch_index_breadth()
    if fenbu:
        report["one_liner"] = (
            f"涨跌家数 {fenbu['up']}:{fenbu['down']} "
            f"（平 {fenbu['flat']}；比 {fenbu['up_down_ratio']}；"
            f"日期 {fenbu.get('trade_date') or '—'}；来源东财涨跌分布）"
        )
    else:
        report["one_liner"] = "涨跌家数未获取（东财 getTopicZDFenBu 失败）"
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="东财全市场涨跌家数（§1 市场情绪）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument(
        "--with-index",
        action="store_true",
        help="附加上证/深成指数页 f104/f105/f106（辅口径）",
    )
    args = ap.parse_args()
    report = build_report(with_index=args.with_index)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(report["one_liner"])
        m = report.get("market") or {}
        if m:
            print(
                f"  up={m['up']} down={m['down']} flat={m['flat']} "
                f"total={m['total']} limit_up_bucket≈{m['limit_up_bucket']} "
                f"limit_down_bucket≈{m['limit_down_bucket']}"
            )
        side = report.get("index_side")
        if side and side.get("items"):
            for it in side["items"]:
                print(
                    f"  辅·{it.get('name')}({it.get('code')}): "
                    f"{it.get('up')}/{it.get('down')}/{it.get('flat')}"
                )
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
