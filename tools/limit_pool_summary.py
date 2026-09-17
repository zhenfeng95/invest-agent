#!/usr/bin/env python3
"""涨跌停摘要（§1 赚钱效应）：家数 + 最高连板 + 代表 2～3 只。

家数口径（方案 A · 收盘封死）：
  当日主源：东财 clist 沪深 A，收盘价 = 涨停价 / 跌停价
  含 ST（主板 ±5%；创业/科创仍 ±20%）；不含无涨跌幅限制的新股首日
  不含北交所；禁止用「盘中触及」作家数
  失败 / 非当日：回退东财专题涨停池 / 跌停池 tc

连板高度 / 涨停代表：东财 `getTopicZTPool`。
跌停样例：优先 clist 收盘跌停（含 ST）；否则专题跌停池点名。

禁止把全池 JSON 贴进 Agent 上下文。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
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
_CLIST_URLS = (
    "https://push2delay.eastmoney.com/api/qt/clist/get",
    "https://82.push2.eastmoney.com/api/qt/clist/get",
    "https://push2.eastmoney.com/api/qt/clist/get",
)
_FS_HS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
_UT = "7eea3edcaed734bea9cbfc24409ed989"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}

# 涨停池：连板/封板时间排序可用；跌停池无 lbc/fbt，用这些会返回 pool=[] 但 tc>0
_ZT_SORTS = ("lbc:desc", "fbt:asc", "amount:desc")
_DT_SORTS = ("amount:desc", "zdp:asc", "fund:asc", "hs:desc")


def _session(headers: dict[str, str] | None = None):
    import requests

    s = requests.Session()
    s.trust_env = False
    s.headers.update(headers or _HEADERS)
    return s


def _trade_date_str() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")


def _fetch_pool(
    urls: tuple[str, ...],
    date: str,
    sorts: tuple[str, ...],
) -> tuple[list[dict[str, Any]], int]:
    """返回 (pool, tc)。tc 为东财专题总家数；pool 为空但 tc>0 时继续换 sort。"""
    s = _session()
    params = {
        "ut": _UT,
        "dpt": "wz.ztzt",
        "Pageindex": 0,
        "pagesize": 500,
        "date": date,
    }
    last_err: Exception | None = None
    best_tc = 0
    for url in urls:
        for sort in sorts:
            try:
                r = s.get(
                    url,
                    params={**params, "sort": sort},
                    timeout=20,
                    proxies={"http": None, "https": None},
                )
                r.raise_for_status()
                data = r.json().get("data") or {}
                pool = data.get("pool") if isinstance(data, dict) else None
                if not isinstance(pool, list):
                    continue
                try:
                    tc = int(data.get("tc") if data.get("tc") is not None else len(pool))
                except (TypeError, ValueError):
                    tc = len(pool)
                best_tc = max(best_tc, tc)
                # 空 list 也是 list——跌停用 lbc/fbt 时常见 pool=[] 且 tc>0
                if pool or tc == 0:
                    return pool, tc
            except Exception as e:  # noqa: BLE001
                last_err = e
    if best_tc > 0:
        return [], best_tc
    raise RuntimeError(f"涨跌停池失败: {last_err}")


def _limit_pct(code: str, name: str, direction: int) -> int:
    """direction: +1 涨停 / -1 跌停。创业/科创/北交所优先于 ST 名称。"""
    if code.startswith(("300", "301", "688", "689")):
        return 20 * direction
    if code.startswith(("8", "4", "92")):
        return 30 * direction
    if "ST" in name.upper():
        return 5 * direction
    return 10 * direction


def _round_limit_price(pre: float, lim_pct: int) -> float:
    return float(
        (Decimal(str(pre)) * (Decimal(100) + Decimal(lim_pct)) / Decimal(100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )


def _is_unlimited_ipo(name: str) -> bool:
    """无涨跌幅限制的新股首日（N前缀等），不计入收盘封板。"""
    n = (name or "").strip()
    return n.startswith("N") or n.startswith("n")


def _fetch_clist_hs_rows() -> list[dict[str, Any]] | None:
    """当日沪深 A 快照。clist 无历史，仅能用于 today。"""
    s = _session()
    rows: list[dict[str, Any]] = []
    last_err: Exception | None = None
    for page in range(1, 80):
        params = {
            "pn": page,
            "pz": 100,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f12",
            "fs": _FS_HS,
            "fields": "f12,f14,f2,f18",
        }
        page_rows: list[dict[str, Any]] | None = None
        total = 0
        for url in _CLIST_URLS:
            try:
                r = s.get(
                    url,
                    params=params,
                    timeout=25,
                    proxies={"http": None, "https": None},
                )
                r.raise_for_status()
                data = r.json().get("data") or {}
                page_rows = data.get("diff") or []
                total = int(data.get("total") or 0)
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
        if page_rows is None:
            if last_err:
                return None
            break
        if not page_rows:
            break
        rows.extend(page_rows)
        if page * 100 >= total:
            break
    return rows or None


def _count_clist_close_limit(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """沪深 A 收盘价打到涨停价/跌停价。"""
    up: list[dict[str, str]] = []
    down: list[dict[str, str]] = []
    for row in rows:
        code = str(row.get("f12") or "").zfill(6)
        name = str(row.get("f14") or "")
        close, pre = row.get("f2"), row.get("f18")
        if _is_unlimited_ipo(name):
            continue
        if close in (None, "-") or pre in (None, "-", 0):
            continue
        try:
            close_f = float(close)
            pre_f = float(pre)
        except (TypeError, ValueError):
            continue
        up_px = _round_limit_price(pre_f, _limit_pct(code, name, +1))
        dn_px = _round_limit_price(pre_f, _limit_pct(code, name, -1))
        rec = {"code": code, "name": name}
        if round(close_f, 2) == round(up_px, 2):
            up.append(rec)
        if round(close_f, 2) == round(dn_px, 2):
            down.append(rec)
    return {
        "limit_up": len(up),
        "limit_down": len(down),
        "limit_down_samples": down[:3],
    }


def _summarize_up(pool: list[dict[str, Any]]) -> dict[str, Any]:
    if not pool:
        return {"count": 0, "max_lbc": 0, "leaders": [], "rep_names": []}
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
    today = _trade_date_str()

    up_pool, up_tc = _fetch_pool(_ZT_URLS, date, _ZT_SORTS)
    down_pool, down_tc = _fetch_pool(_DT_URLS, date, _DT_SORTS)
    up = _summarize_up(up_pool)
    down = _summarize_down(down_pool)

    count_source = "eastmoney_topic_pool"
    up_n = up_tc if up_tc else up["count"]
    down_n = down_tc if down_tc else down["count"]
    down_samples = down["samples"]

    # 当日：clist 收盘封死覆盖家数（含 ST）；clist 无历史
    if date == today:
        rows = _fetch_clist_hs_rows()
        if rows:
            closed = _count_clist_close_limit(rows)
            up_n = closed["limit_up"]
            down_n = closed["limit_down"]
            if closed["limit_down_samples"]:
                down_samples = closed["limit_down_samples"]
            count_source = "eastmoney_clist_close_limit"

    return {
        "trade_date": f"{date[:4]}-{date[4:6]}-{date[6:8]}",
        "limit_up": up_n,
        "limit_down": down_n,
        "max_lbc": up["max_lbc"],
        "leaders": up["leaders"],
        "leader_names": up["rep_names"],
        "limit_down_samples": down_samples,
        "topic_limit_up": up_tc if up_tc else up["count"],
        "topic_limit_down": down_tc if down_tc else down["count"],
        "source": count_source,
        "note": "家数=沪深A收盘封死（含ST，不含新股首日/北交所）；连板代表来自东财涨停池；禁止贴全池",
    }


def one_liner(rep: dict[str, Any]) -> str:
    leaders = rep.get("leader_names") or []
    lead_s = "、".join(leaders) if leaders else "—"
    down_n = rep.get("limit_down_samples") or []
    down_s = "、".join(d["name"] for d in down_n[:2] if d.get("name")) or "—"
    topic_u = rep.get("topic_limit_up")
    topic_d = rep.get("topic_limit_down")
    return (
        f"涨停={rep['limit_up']} 跌停={rep['limit_down']} "
        f"最高{rep['max_lbc']}连板 代表={lead_s} "
        f"跌停样例={down_s} date={rep['trade_date']} "
        f"source={rep['source']} 池={topic_u}/{topic_d}"
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
