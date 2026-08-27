#!/usr/bin/env python3
"""涨跌停池摘要（§1 赚钱效应）：家数 + 最高连板 + 代表 2～3 只。

主源：东财 push2ex getTopicZTPool / getTopicDTPool（一页即可，禁止把全池贴进 Agent 上下文）。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

_ZT_URLS = (
    "https://push2ex.eastmoney.com/getTopicZTPool",
    "https://push2delayex.eastmoney.com/getTopicZTPool",
)
_DT_URLS = (
    "https://push2ex.eastmoney.com/getTopicDTPool",
    "https://push2delayex.eastmoney.com/getTopicDTPool",
)
_UT = "7eea3edcaed734bea9cbfc24409ed989"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}


def _session():
    import requests

    s = requests.Session()
    s.trust_env = False
    s.headers.update(_HEADERS)
    return s


def _trade_date_str() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")


def _fetch_pool(urls: tuple[str, ...], date: str) -> list[dict[str, Any]]:
    s = _session()
    params = {
        "ut": _UT,
        "dpt": "wz.ztzt",
        "Pageindex": 0,
        "pagesize": 500,
        "date": date,
    }
    last_err: Exception | None = None
    for url in urls:
        for sort in ("lbc:desc", "fbt:asc"):
            try:
                r = s.get(
                    url,
                    params={**params, "sort": sort},
                    timeout=20,
                    proxies={"http": None, "https": None},
                )
                r.raise_for_status()
                pool = (r.json().get("data") or {}).get("pool") or []
                if isinstance(pool, list):
                    return pool
            except Exception as e:  # noqa: BLE001
                last_err = e
    raise RuntimeError(f"涨跌停池失败: {last_err}")


def _summarize_up(pool: list[dict[str, Any]]) -> dict[str, Any]:
    if not pool:
        return {"count": 0, "max_lbc": 0, "leaders": []}
    leaders: list[dict[str, Any]] = []
    max_lbc = 0
    for row in pool:
        try:
            lbc = int(row.get("lbc") or row.get("zttj", {}).get("days") or 0)
        except (TypeError, ValueError):
            lbc = 0
        max_lbc = max(max_lbc, lbc)
        name = str(row.get("n") or "")
        code = str(row.get("c") or "").zfill(6)
        if name:
            leaders.append({"code": code, "name": name, "lbc": lbc, "hybk": row.get("hybk")})
    leaders.sort(key=lambda x: (-x["lbc"], x["name"]))
    top = leaders[:5]
    # 去重：同 lbc 只保留前 3 个代表
    reps: list[str] = []
    for item in top:
        tag = f"{item['name']}{item['lbc']}连板" if item["lbc"] > 1 else item["name"]
        if tag not in reps:
            reps.append(tag)
        if len(reps) >= 3:
            break
    return {"count": len(pool), "max_lbc": max_lbc, "leaders": top[:3], "rep_names": reps}


def _summarize_down(pool: list[dict[str, Any]]) -> dict[str, Any]:
    if not pool:
        return {"count": 0, "samples": []}
    samples = []
    for row in pool[:3]:
        samples.append(
            {
                "code": str(row.get("c") or "").zfill(6),
                "name": str(row.get("n") or ""),
                "hybk": row.get("hybk"),
            }
        )
    return {"count": len(pool), "samples": samples}


def analyze(date: str | None = None) -> dict[str, Any]:
    date = date or _trade_date_str()
    up_pool = _fetch_pool(_ZT_URLS, date)
    down_pool = _fetch_pool(_DT_URLS, date)
    up = _summarize_up(up_pool)
    down = _summarize_down(down_pool)
    return {
        "trade_date": f"{date[:4]}-{date[4:6]}-{date[6:8]}",
        "limit_up": up["count"],
        "limit_down": down["count"],
        "max_lbc": up["max_lbc"],
        "leaders": up["leaders"],
        "leader_names": up["rep_names"],
        "limit_down_samples": down["samples"],
        "source": "eastmoney_topic_zt_dt_pool",
        "note": "摘要口径；正文只写家数+最高连板+2～3代表，禁止贴全池",
    }


def one_liner(rep: dict[str, Any]) -> str:
    leaders = rep.get("leader_names") or []
    lead_s = "、".join(leaders) if leaders else "—"
    down_n = rep.get("limit_down_samples") or []
    down_s = "、".join(d["name"] for d in down_n[:2] if d.get("name")) or "—"
    return (
        f"涨停={rep['limit_up']} 跌停={rep['limit_down']} "
        f"最高{rep['max_lbc']}连板 代表={lead_s} "
        f"跌停样例={down_s} date={rep['trade_date']} source={rep['source']}"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="涨跌停池摘要（§1）")
    p.add_argument("--date", help="YYYYMMDD，默认今日（上海）")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    try:
        rep = analyze(args.date)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(one_liner(rep))


if __name__ == "__main__":
    main()
