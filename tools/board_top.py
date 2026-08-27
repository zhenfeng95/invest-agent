#!/usr/bin/env python3
"""东财行业/概念涨跌 TOP5（§4 板块共振 · 东财侧）。

只拉 clist 各 5 条（领涨+领跌），禁止全 catalog / 全板块分页进 Agent 上下文。
同花顺 THS 侧勿调 catalog 全量；见 prompt「Token 预算」。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

_HOSTS = (
    "https://push2delay.eastmoney.com/api/qt/clist/get",
    "https://82.push2.eastmoney.com/api/qt/clist/get",
    "https://7.push2.eastmoney.com/api/qt/clist/get",
    "https://push2.eastmoney.com/api/qt/clist/get",
)
_UT = "bd1d9ddb04089700cf9c27f6f7426281"
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


def _fetch_board(fs: str, top_n: int, po: int) -> list[dict[str, Any]]:
    s, backend = _session()
    params = {
        "pn": 1,
        "pz": top_n,
        "po": po,
        "np": 1,
        "ut": _UT,
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": fs,
        "fields": "f12,f14,f3,f62",
    }
    last_err: Exception | None = None
    for host in _HOSTS:
        try:
            kw: dict[str, Any] = {"params": params, "timeout": 20}
            if backend == "requests":
                kw["proxies"] = {"http": None, "https": None}
            r = s.get(host, **kw)
            r.raise_for_status()
            diff = (r.json().get("data") or {}).get("diff") or []
            out: list[dict[str, Any]] = []
            for item in diff[:top_n]:
                try:
                    chg = float(item.get("f3"))
                except (TypeError, ValueError):
                    continue
                net = item.get("f62")
                try:
                    net_yi = round(float(net) / 1e8, 2) if net is not None else None
                except (TypeError, ValueError):
                    net_yi = None
                out.append(
                    {
                        "code": str(item.get("f12") or ""),
                        "name": str(item.get("f14") or ""),
                        "chg_pct": round(chg, 2),
                        "net_flow_yi": net_yi,
                    }
                )
            if out:
                return out
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.2)
    raise RuntimeError(f"东财板块榜失败 fs={fs} po={po}: {last_err}")


def analyze(top_n: int = 5) -> dict[str, Any]:
    industry_up = _fetch_board("m:90+t:2", top_n, po=1)
    industry_down = _fetch_board("m:90+t:2", top_n, po=0)
    concept_up = _fetch_board("m:90+t:3", top_n, po=1)
    concept_down = _fetch_board("m:90+t:3", top_n, po=0)
    return {
        "industry_up": industry_up,
        "industry_down": industry_down,
        "concept_up": concept_up,
        "concept_down": concept_down,
        "source": "eastmoney_board_clist_top5",
        "note": "东财行业/概念各TOP5；同花顺侧禁止catalog全量",
    }


def _fmt_rows(rows: list[dict[str, Any]]) -> str:
    return " | ".join(f"{r['name']}{r['chg_pct']:+.2f}%" for r in rows)


def one_liner(rep: dict[str, Any]) -> str:
    return (
        f"行业涨TOP5: {_fmt_rows(rep['industry_up'])} || "
        f"行业跌TOP5: {_fmt_rows(rep['industry_down'])} || "
        f"概念涨TOP5: {_fmt_rows(rep['concept_up'])} || "
        f"概念跌TOP5: {_fmt_rows(rep['concept_down'])} "
        f"source={rep['source']}"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="东财行业/概念涨跌TOP5（§4）")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    try:
        rep = analyze(top_n=args.top)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(one_liner(rep))


if __name__ == "__main__":
    main()
