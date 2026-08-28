#!/usr/bin/env python3
"""沪深 A 成交额前 100：默认只输出涨跌家数（§1 赚钱效应）。

行业分布仅在 --with-industries / --json 时给出；日报正文不要贴行业表。

只拉 clist 一页（pn=1, pz=100, fid=f6 成交额降序）。
禁止：全市场分页、行业主力净额、同花顺映射。
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from typing import Any

_HOSTS = (
    "https://push2delay.eastmoney.com/api/qt/clist/get",
    "https://82.push2.eastmoney.com/api/qt/clist/get",
    "https://7.push2.eastmoney.com/api/qt/clist/get",
    "https://push2.eastmoney.com/api/qt/clist/get",
)
_UT = "bd1d9ddb04089700cf9c27f6f7426281"
_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
_FIELDS = "f12,f14,f2,f3,f6,f100"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}


def _session():
    try:
        from curl_cffi import requests as creq

        return creq.Session(impersonate="chrome120"), "curl_cffi"
    except Exception:
        import requests

        s = requests.Session()
        s.trust_env = False
        s.headers.update(_HEADERS)
        return s, "requests"


def fetch_top100() -> tuple[int | None, list[dict[str, Any]]]:
    s, backend = _session()
    params = {
        "pn": 1,
        "pz": 100,
        "po": 1,
        "np": 1,
        "ut": _UT,
        "fltt": 2,
        "invt": 2,
        "fid": "f6",
        "fs": _FS,
        "fields": _FIELDS,
    }
    last_err: Exception | None = None
    for host in _HOSTS:
        try:
            kw: dict[str, Any] = {
                "params": params,
                "timeout": 20,
                "headers": _HEADERS,
            }
            if backend == "requests":
                kw["proxies"] = {"http": None, "https": None}
            r = s.get(host, **kw)
            r.raise_for_status()
            data = r.json().get("data") or {}
            diff = data.get("diff") or []
            total = data.get("total")
            return (int(total) if total is not None else None, list(diff[:100]))
        except Exception as e:
            last_err = e
            time.sleep(0.2)
    raise RuntimeError(f"成交额前100拉取失败: {last_err}")


def _num(v: Any) -> float | None:
    try:
        if v in (None, "", "-"):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def aggregate(stocks: list[dict[str, Any]]) -> dict[str, Any]:
    up = down = flat = 0
    amt_all = amt_up = amt_dn = 0.0
    up_ind: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "amount": 0.0, "names": []}
    )
    dn_ind: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "amount": 0.0, "names": []}
    )
    down_stocks: list[dict[str, Any]] = []

    for it in stocks:
        chg = _num(it.get("f3"))
        amt = _num(it.get("f6")) or 0.0
        ind = str(it.get("f100") or "未分类").strip() or "未分类"
        name = str(it.get("f14") or it.get("f12") or "")
        code = str(it.get("f12") or "").zfill(6)
        amt_all += amt
        if chg is None:
            continue
        if chg > 0:
            up += 1
            amt_up += amt
            g = up_ind[ind]
            g["n"] += 1
            g["amount"] += amt
            if len(g["names"]) < 3:
                g["names"].append(f"{name}(+{chg:.2f}%)")
        elif chg < 0:
            down += 1
            amt_dn += amt
            g = dn_ind[ind]
            g["n"] += 1
            g["amount"] += amt
            g["names"].append(f"{name}({chg:.2f}%)")
            down_stocks.append(
                {
                    "code": code,
                    "name": name,
                    "chg": round(chg, 2),
                    "amount_yi": round(amt / 1e8, 2),
                    "industry": ind,
                }
            )
        else:
            flat += 1

    def pack(d: dict[str, dict[str, Any]], min_n: int = 1) -> list[dict[str, Any]]:
        rows = []
        for name, g in d.items():
            if g["n"] < min_n:
                continue
            rows.append(
                {
                    "industry": name,
                    "n": g["n"],
                    "amount_yi": round(g["amount"] / 1e8, 2),
                    "examples": g["names"],
                }
            )
        rows.sort(key=lambda x: (-x["n"], -x["amount_yi"]))
        return rows

    singles = [
        name
        for name, g in sorted(up_ind.items(), key=lambda kv: -kv[1]["amount"])
        if g["n"] == 1
    ]
    return {
        "ok": bool(stocks),
        "n": len(stocks),
        "up": up,
        "down": down,
        "flat": flat,
        "amount_yi": round(amt_all / 1e8, 2),
        "amount_up_yi": round(amt_up / 1e8, 2),
        "amount_down_yi": round(amt_dn / 1e8, 2),
        "up_industries_ge2": pack(up_ind, min_n=2),
        "up_industries_n1": singles,
        "down_industries": pack(dn_ind, min_n=1),
        "down_stocks": down_stocks,
        "source": "eastmoney_clist_fid_f6_pn1",
        "note": "沪深A成交额前100（不含北交所）；行业=东财f100；非全市场宽度、非主力净额",
    }


def format_counts(rep: dict[str, Any]) -> str:
    """日报默认：只一行涨跌家数。"""
    return (
        f"前100 {rep['up']}涨:{rep['down']}跌"
        f"（平{rep['flat']}；成交{rep['amount_yi']}亿；"
        f"n={rep['n']}；来源东财clist一页）"
    )


def format_industries(rep: dict[str, Any]) -> str:
    """调试用：行业分布表（不进日报正文）。"""
    lines = [format_counts(rep), "涨的行业（只数≥2）："]
    lines.append("| 行业 | 只数 | 成交(亿) | 代表 |")
    lines.append("| ---- | ----: | -------: | ---- |")
    for r in rep["up_industries_ge2"]:
        ex = "、".join(r["examples"])
        lines.append(f"| {r['industry']} | {r['n']} | {r['amount_yi']} | {ex} |")
    n1 = rep.get("up_industries_n1") or []
    if n1:
        lines.append("其余上涨（各1只）：" + "、".join(n1))
    lines.append("跌的行业（全部）：")
    lines.append("| 行业 | 只数 | 成交(亿) | 个股 |")
    lines.append("| ---- | ----: | -------: | ---- |")
    downs = rep["down_industries"]
    if not downs:
        lines.append("| （无） | 0 | 0 | — |")
    else:
        for r in downs:
            ex = "、".join(r["examples"])
            lines.append(f"| {r['industry']} | {r['n']} | {r['amount_yi']} | {ex} |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="沪深A成交额前100涨跌家数（§1 赚钱效应；行业分布仅调试）"
    )
    ap.add_argument("--json", action="store_true", help="输出完整 JSON（含行业）")
    ap.add_argument(
        "--with-industries",
        action="store_true",
        help="文本输出附带行业分布表（调试；日报勿用）",
    )
    args = ap.parse_args()
    try:
        universe, stocks = fetch_top100()
    except Exception as e:
        if args.json:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False, indent=2))
        else:
            print(f"前100未获取：{e}")
        return 1
    rep = aggregate(stocks)
    rep["universe_total"] = universe
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    elif args.with_industries:
        print(format_industries(rep))
    else:
        print(format_counts(rep))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
