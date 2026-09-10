#!/usr/bin/env python3
"""东财涨跌家数 / 涨跌分布 / 涨跌中位数（§1 赚钱效应 · 沪深京）。

主数字（涨:跌）——与同花顺等行情软件常见口径对齐：
- 东财 clist **逐票**统计：涨跌幅>0 / <0 / =0（有有效报价的票）
- 范围：沪深 A（主板/创业/科创）+ 北交所
- 停牌等无涨跌幅字段的票不计入涨跌平

中位数：东财涨跌停专题「涨跌分布」直方图桶估计（沪深；北交所无同结构桶）。
辅：`--with-index` 上证/深成指数页宽度；clist 失败时回退 涨跌分布+北证50页。

注意：涨跌分布直方图（fenbu）与逐票计数会差几十～上百家，不要混用。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

_FENBU_URLS = (
    "https://push2ex.eastmoney.com/getTopicZDFenBu",
    "https://push2delayex.eastmoney.com/getTopicZDFenBu",
)
_INDEX_URLS = (
    "https://push2delay.eastmoney.com/api/qt/ulist.np/get",
    "https://push2.eastmoney.com/api/qt/ulist.np/get",
    "https://82.push2.eastmoney.com/api/qt/ulist.np/get",
)
_STOCK_URLS = (
    "https://push2delay.eastmoney.com/api/qt/stock/get",
    "https://push2.eastmoney.com/api/qt/stock/get",
)
_CLIST_URLS = (
    "https://push2delay.eastmoney.com/api/qt/clist/get",
    "https://82.push2.eastmoney.com/api/qt/clist/get",
    "https://push2.eastmoney.com/api/qt/clist/get",
)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}
_UT_FENBU = "7eea3edcaed734bea9cbfc24409ed989"
_UT_QUOTE = "bd1d9ddb04089700cf9c27f6f7426281"
# 沪深A：沪主板/科创 + 深主板/创业；北交所
_FS_HS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
_FS_BJ = "m:0+t:81+s:2048"


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
        "scope": "沪深·涨跌分布直方图",
        "source": "eastmoney_getTopicZDFenBu",
        "note": "直方图口径≠逐票计数；仅作中位数与回退",
    }


def fetch_fenbu() -> dict[str, Any] | None:
    raw = _get_json(
        _FENBU_URLS,
        {"ut": _UT_FENBU, "dpt": "wz.ztzt"},
    )
    if not raw or raw.get("rc") not in (0, None):
        return None
    return _parse_fenbu(raw)


def fetch_bj_breadth() -> dict[str, Any] | None:
    """北交所涨跌家数回退：北证50页 f104/f105/f106。"""
    raw = _get_json(
        _INDEX_URLS,
        {
            "fltt": 2,
            "secids": "0.899050",
            "fields": "f12,f14,f104,f105,f106",
            "ut": _UT_QUOTE,
        },
    )
    if not raw:
        return None
    diff = (raw.get("data") or {}).get("diff") or []
    if not diff:
        return None
    row = diff[0]
    try:
        up = int(row.get("f104") or 0)
        down = int(row.get("f105") or 0)
        flat = int(row.get("f106") or 0)
    except (TypeError, ValueError):
        return None
    return {
        "code": row.get("f12") or "899050",
        "name": row.get("f14") or "北证50",
        "up": up,
        "down": down,
        "flat": flat,
        "total": up + down + flat,
        "scope": "北交所",
        "source": "eastmoney_899050_f104",
    }


def _count_clist_fs(fs: str, *, pz: int = 100, max_pages: int = 100) -> dict[str, Any] | None:
    """逐票涨跌计数：f3>0 涨 / <0 跌 / =0 平；非数字跳过。"""
    s, backend = _session()
    up = down = flat = priced = skip = 0
    total: int | None = None
    page = 1
    host_used = None
    while page <= max_pages:
        raw = None
        last_err: Exception | None = None
        for url in _CLIST_URLS:
            try:
                kw: dict[str, Any] = {
                    "params": {
                        "pn": page,
                        "pz": pz,
                        "po": 1,
                        "np": 1,
                        "fltt": 2,
                        "invt": 2,
                        "fid": "f12",
                        "fs": fs,
                        "fields": "f12,f3",
                        "ut": _UT_QUOTE,
                    },
                    "timeout": 25,
                    "headers": _HEADERS,
                }
                if backend == "requests":
                    kw["proxies"] = {"http": None, "https": None}
                r = s.get(url, **kw)
                r.raise_for_status()
                raw = r.json()
                host_used = url.split("/")[2]
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(0.25)
        if raw is None:
            print(f"[market_breadth] clist 失败 page={page}: {last_err}", file=sys.stderr)
            return None
        data = raw.get("data") or {}
        if total is None:
            try:
                total = int(data.get("total") or 0)
            except (TypeError, ValueError):
                total = 0
        diff = data.get("diff") or []
        if not diff:
            break
        for row in diff:
            try:
                chg = float(row.get("f3"))
            except (TypeError, ValueError):
                skip += 1
                continue
            priced += 1
            if chg > 0:
                up += 1
            elif chg < 0:
                down += 1
            else:
                flat += 1
        done = priced + skip
        if total and done >= total:
            break
        if len(diff) < pz:
            break
        page += 1
        time.sleep(0.04)
    if priced <= 0:
        return None
    return {
        "up": up,
        "down": down,
        "flat": flat,
        "priced": priced,
        "skip": skip,
        "api_total": total,
        "pages": page,
        "host": host_used,
    }


def fetch_tick_breadth_hsj() -> dict[str, Any] | None:
    """沪深京逐票涨跌（对齐行情软件常见口径）。"""
    hs = _count_clist_fs(_FS_HS)
    bj = _count_clist_fs(_FS_BJ)
    if not hs:
        return None
    bj_up = int((bj or {}).get("up") or 0)
    bj_down = int((bj or {}).get("down") or 0)
    bj_flat = int((bj or {}).get("flat") or 0)
    up = hs["up"] + bj_up
    down = hs["down"] + bj_down
    flat = hs["flat"] + bj_flat
    ratio = round(up / down, 2) if down else None
    return {
        "up": up,
        "down": down,
        "flat": flat,
        "total": up + down + flat,
        "up_down_ratio": ratio,
        "hs_up": hs["up"],
        "hs_down": hs["down"],
        "hs_flat": hs["flat"],
        "bj_up": bj_up,
        "bj_down": bj_down,
        "bj_flat": bj_flat,
        "bj_ok": bool(bj),
        "priced": hs["priced"] + int((bj or {}).get("priced") or 0),
        "skip": hs["skip"] + int((bj or {}).get("skip") or 0),
        "scope": "沪深京",
        "source": "eastmoney_clist_tick",
        "method": "逐票f3",
        "note": "涨跌幅>0/<0/=0；无报价跳过；对齐同花顺等常见沪深京涨跌家数",
        "hs_meta": hs,
        "bj_meta": bj,
    }


def merge_fenbu_fallback(
    fenbu: dict[str, Any] | None, bj: dict[str, Any] | None
) -> dict[str, Any] | None:
    """clist 失败时：沪深涨跌分布 + 北证50页。"""
    if not fenbu:
        return None
    bj_up = int((bj or {}).get("up") or 0)
    bj_down = int((bj or {}).get("down") or 0)
    bj_flat = int((bj or {}).get("flat") or 0)
    up = int(fenbu["up"]) + bj_up
    down = int(fenbu["down"]) + bj_down
    flat = int(fenbu["flat"]) + bj_flat
    ratio = round(up / down, 2) if down else None
    return {
        "up": up,
        "down": down,
        "flat": flat,
        "total": up + down + flat,
        "up_down_ratio": ratio,
        "hs_up": fenbu["up"],
        "hs_down": fenbu["down"],
        "hs_flat": fenbu["flat"],
        "bj_up": bj_up,
        "bj_down": bj_down,
        "bj_flat": bj_flat,
        "bj_ok": bool(bj),
        "scope": "沪深京·回退",
        "source": "eastmoney_fenbu+899050",
        "method": "涨跌分布直方图+北证50页",
        "note": "回退口径；与软件逐票数可能差几十～上百家",
    }


def fetch_sh_chg() -> dict[str, Any] | None:
    """上证指数当日涨跌幅%（f170）。"""
    raw = _get_json(
        _STOCK_URLS,
        {
            "secid": "1.000001",
            "fields": "f43,f57,f58,f169,f170",
            "fltt": 2,
            "ut": _UT_QUOTE,
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
    """上证/深成指数页宽度（辅口径）。"""
    raw = _get_json(
        _INDEX_URLS,
        {
            "fltt": 2,
            "secids": "1.000001,0.399001",
            "fields": "f12,f14,f104,f105,f106",
            "ut": _UT_QUOTE,
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
    tick = fetch_tick_breadth_hsj()
    bj_page = None if tick and tick.get("bj_ok") else fetch_bj_breadth()
    if tick:
        market = dict(tick)
        market["median_chg_pct"] = (fenbu or {}).get("median_chg_pct")
        market["limit_up_bucket"] = (fenbu or {}).get("limit_up_bucket")
        market["limit_down_bucket"] = (fenbu or {}).get("limit_down_bucket")
        market["trade_date"] = (fenbu or {}).get("trade_date")
        market["median_scope"] = "沪深分布桶"
        market["median_source"] = "eastmoney_getTopicZDFenBu"
    else:
        market = merge_fenbu_fallback(fenbu, bj_page or fetch_bj_breadth())
        if market and fenbu:
            market["median_chg_pct"] = fenbu.get("median_chg_pct")
            market["limit_up_bucket"] = fenbu.get("limit_up_bucket")
            market["limit_down_bucket"] = fenbu.get("limit_down_bucket")
            market["trade_date"] = fenbu.get("trade_date")
            market["median_scope"] = "沪深分布桶"

    sh = fetch_sh_chg()
    report: dict[str, Any] = {
        "ok": bool(market),
        "market": market,
        "fenbu_hs": fenbu,
        "tick": tick,
        "shanghai": sh,
    }
    if with_index:
        report["index_side"] = fetch_index_breadth()
    if market:
        med = market.get("median_chg_pct")
        sh_chg = (sh or {}).get("chg_pct")
        bj_tag = (
            f"沪深{market['hs_up']}:{market['hs_down']}+京{market['bj_up']}:{market['bj_down']}"
            if market.get("bj_ok") is not False
            else "北交所未获取"
        )
        src = market.get("method") or market.get("source")
        report["one_liner"] = (
            f"涨跌家数 {market['up']}:{market['down']} "
            f"（平 {market['flat']}；比 {market['up_down_ratio']}；"
            f"{bj_tag}；"
            f"中位数 {_fmt_pct(med)} vs 上证 {_fmt_pct(sh_chg)}；"
            f"{_median_vs_sh(med if isinstance(med, (int, float)) else None, sh_chg)}；"
            f"日期 {market.get('trade_date') or '—'}；{src}）"
        )
    else:
        report["one_liner"] = "涨跌家数未获取（clist 与涨跌分布均失败）"
    return report


def main() -> int:
    ap = argparse.ArgumentParser(
        description="沪深京涨跌家数（逐票，对齐软件）+ 中位数 vs 上证"
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
                f"hs={m.get('hs_up')}:{m.get('hs_down')} "
                f"bj={m.get('bj_up')}:{m.get('bj_down')} "
                f"method={m.get('method')}"
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
