#!/usr/bin/env python3
"""东财涨跌家数 / 涨跌分布 / 全市场涨跌中位数（§1 赚钱效应）。

主源：东财涨跌停专题「涨跌分布」接口 getTopicZDFenBu（一次返回，无需全市场分页）。
中位数：由分布桶累计求得（桶键≈整数涨跌幅%）；并拉取上证当日涨跌幅便于对照。
辅源：上证/深成指数页 f104/f105/f106（交易所侧宽度，非全市场精确口径）。

禁止：clist 全市场分页自己数涨跌（易触发「分页受限」）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

_FENBU_URLS = (
    "https://push2ex.eastmoney.com/getTopicZDFenBu",
    "https://push2delayex.eastmoney.com/getTopicZDFenBu",
)
_INDEX_URLS = (
    "https://push2.eastmoney.com/api/qt/ulist.np/get",
    "https://push2delay.eastmoney.com/api/qt/ulist.np/get",
    "https://82.push2.eastmoney.com/api/qt/ulist.np/get",
)
_STOCK_URLS = (
    "https://push2.eastmoney.com/api/qt/stock/get",
    "https://push2delay.eastmoney.com/api/qt/stock/get",
)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}
_UT = "7eea3edcaed734bea9cbfc24409ed989"


def _session():
    """优先 curl_cffi；清掉代理环境，避免本机代理 403。"""
    for k in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
    ):
        os.environ.pop(k, None)
    try:
        from curl_cffi import requests as creq

        return creq.Session(impersonate="chrome120"), "curl_cffi"
    except Exception:
        import requests

        s = requests.Session()
        s.trust_env = False
        s.headers.update(_HEADERS)
        return s, "requests"


def _get_json(urls: tuple[str, ...], params: dict[str, Any]) -> dict[str, Any] | None:
    s, backend = _session()
    last_err: Exception | None = None
    for url in urls:
        try:
            kw: dict[str, Any] = {
                "params": params,
                "timeout": 20,
                "headers": _HEADERS,
            }
            if backend == "requests":
                kw["proxies"] = {"http": None, "https": None}
            r = s.get(url, **kw)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
    if last_err:
        print(f"[market_breadth] 请求失败: {last_err}", file=sys.stderr)
    return None


def _median_from_buckets(buckets: dict[int, int]) -> float | None:
    """直方图中位数：桶键为整数涨跌幅%。"""
    total = sum(buckets.values())
    if total <= 0:
        return None
    # 目标：第 (total+1)//2 个观测（1-based）；偶数取中间两桶均值
    if total % 2 == 1:
        target = (total + 1) // 2
        cum = 0
        for k in sorted(buckets):
            cum += buckets[k]
            if cum >= target:
                return float(k)
        return None
    t1, t2 = total // 2, total // 2 + 1
    v1 = v2 = None
    cum = 0
    for k in sorted(buckets):
        cum += buckets[k]
        if v1 is None and cum >= t1:
            v1 = k
        if cum >= t2:
            v2 = k
            break
    if v1 is None or v2 is None:
        return None
    return (v1 + v2) / 2.0


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
    median = _median_from_buckets(buckets)
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
        "median_chg_pct": median,
        "limit_up_bucket": limit_up_like,
        "limit_down_bucket": limit_down_like,
        "buckets": {str(k): buckets[k] for k in sorted(buckets)},
        "source": "eastmoney_getTopicZDFenBu",
        "note": (
            "全市场涨跌分布汇总；中位数由分布桶估计（整数%桶）；"
            "涨停/跌停请以 limit_pool_summary 为准，本接口 10/−10 桶仅供对照"
        ),
    }


def fetch_fenbu() -> dict[str, Any] | None:
    raw = _get_json(
        _FENBU_URLS,
        {"ut": _UT, "dpt": "wz.ztzt"},
    )
    if not raw or raw.get("rc") not in (0, None):
        return None
    return _parse_fenbu(raw)


def fetch_sh_chg() -> dict[str, Any] | None:
    """上证指数当日涨跌幅%（f170）。"""
    raw = _get_json(
        _STOCK_URLS,
        {
            "secid": "1.000001",
            "fields": "f43,f57,f58,f169,f170",
            "fltt": 2,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        },
    )
    if not raw:
        return None
    d = raw.get("data") or {}
    chg = d.get("f170")
    if chg is None:
        return None
    try:
        chg_f = float(chg)
    except (TypeError, ValueError):
        return None
    return {
        "name": d.get("f58") or "上证指数",
        "code": d.get("f57") or "000001",
        "close": d.get("f43"),
        "chg_pct": chg_f,
        "source": "eastmoney_stock_f170",
    }


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


def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "未获取"
    sign = "+" if x > 0 else ""
    # 整数桶中位数常为 x.0；保留 1 位即可
    return f"{sign}{x:.1f}%"


def _median_vs_sh(median: float | None, sh: float | None) -> str:
    if median is None or sh is None:
        return "对照未齐"
    diff = median - sh
    if abs(diff) < 0.15:
        return "中位数≈上证"
    if diff > 0:
        return "中位数>上证（个股强于指数）"
    return "中位数<上证（指数强于个股）"


def build_report(*, with_index: bool = False) -> dict[str, Any]:
    fenbu = fetch_fenbu()
    sh = fetch_sh_chg()
    report: dict[str, Any] = {
        "ok": bool(fenbu),
        "market": fenbu,
        "shanghai": sh,
    }
    if with_index:
        report["index_side"] = fetch_index_breadth()
    if fenbu:
        med = fenbu.get("median_chg_pct")
        sh_chg = (sh or {}).get("chg_pct")
        report["one_liner"] = (
            f"涨跌家数 {fenbu['up']}:{fenbu['down']} "
            f"（平 {fenbu['flat']}；比 {fenbu['up_down_ratio']}；"
            f"中位数 {_fmt_pct(med)} vs 上证 {_fmt_pct(sh_chg)}；"
            f"{_median_vs_sh(med if isinstance(med, (int, float)) else None, sh_chg)}；"
            f"日期 {fenbu.get('trade_date') or '—'}；来源东财涨跌分布）"
        )
    else:
        report["one_liner"] = "涨跌家数未获取（东财 getTopicZDFenBu 失败）"
    return report


def main() -> int:
    ap = argparse.ArgumentParser(
        description="东财全市场涨跌家数 + 涨跌中位数 vs 上证（§1 赚钱效应）"
    )
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
                f"total={m['total']} median={m.get('median_chg_pct')} "
                f"limit_up_bucket≈{m['limit_up_bucket']} "
                f"limit_down_bucket≈{m['limit_down_bucket']}"
            )
        sh = report.get("shanghai") or {}
        if sh:
            print(f"  上证 {sh.get('name')}: {_fmt_pct(sh.get('chg_pct'))} close={sh.get('close')}")
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
