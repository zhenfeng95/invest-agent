#!/usr/bin/env python3
"""涨跌停池摘要（§1 赚钱效应）：家数 + 最高连板 + 代表 2～3 只。

家数口径（对齐同花顺 / 东方财富客户端行情总览）：
  主源：同花顺 `api.php?t=indexflash` → `zdt_data.last_zdt.ztzs/dtzs`
  （含触及跌停、含 ST；与软件「跌停 XX」一致）

连板高度 / 涨停代表：东财 `getTopicZTPool`（专题涨停池）。
跌停样例：东财 `getTopicDTPool`（专题跌停池；家数可能少于客户端，仅作点名）。

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
_THS_FLASH_URL = "https://q.10jqka.com.cn/api.php?t=indexflash"
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
_THS_HEADERS = {
    **_HEADERS,
    "Referer": "https://q.10jqka.com.cn/",
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


def _fetch_ths_zdt_counts() -> dict[str, int] | None:
    """同花顺行情总览涨跌停家数（与客户端一致）。仅当日有效。"""
    s = _session(_THS_HEADERS)
    try:
        r = s.get(_THS_FLASH_URL, timeout=20, proxies={"http": None, "https": None})
        r.raise_for_status()
        last = ((r.json().get("zdt_data") or {}).get("last_zdt") or {})
        zt = last.get("ztzs")
        dt = last.get("dtzs")
        if zt is None or dt is None:
            return None
        return {"limit_up": int(zt), "limit_down": int(dt)}
    except Exception:  # noqa: BLE001
        return None


def _limit_pct(code: str, name: str, direction: int) -> int:
    """direction: +1 涨停 / -1 跌停。"""
    if "ST" in name.upper():
        return 5 * direction
    if code.startswith(("300", "301", "688", "689")):
        return 20 * direction
    if code.startswith(("8", "4", "92")):
        return 30 * direction
    return 10 * direction


def _round_limit_price(pre: float, lim_pct: int) -> float:
    return float(
        (Decimal(str(pre)) * (Decimal(100) + Decimal(lim_pct)) / Decimal(100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )


def _count_clist_touch_limit_down() -> int | None:
    """回退：沪深 A 最低价触及跌停价家数（近似同花顺跌停口径）。"""
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
            "fields": "f12,f14,f2,f16,f18",
        }
        page_rows: list[dict[str, Any]] | None = None
        total = 0
        for url in _CLIST_URLS:
            try:
                r = s.get(url, params=params, timeout=25, proxies={"http": None, "https": None})
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
    if not rows:
        return None
    n = 0
    for row in rows:
        code = str(row.get("f12") or "")
        name = str(row.get("f14") or "")
        low, pre = row.get("f16"), row.get("f18")
        if low in (None, "-") or pre in (None, "-", 0):
            continue
        try:
            low_f = float(low)
            pre_f = float(pre)
        except (TypeError, ValueError):
            continue
        tgt = _round_limit_price(pre_f, _limit_pct(code, name, -1))
        if round(low_f, 2) == round(tgt, 2):
            n += 1
    return n


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

    # 当日：用同花顺客户端口径覆盖家数（涨停/跌停与软件一致）
    if date == today:
        ths = _fetch_ths_zdt_counts()
        if ths:
            up_n = ths["limit_up"]
            down_n = ths["limit_down"]
            count_source = "ths_indexflash_last_zdt"
        else:
            touch_dn = _count_clist_touch_limit_down()
            if touch_dn is not None:
                down_n = touch_dn
                count_source = "eastmoney_clist_touch_dt+topic_zt"
            # 涨停仍用专题池（与同花顺 ztzs / 软件涨停通常一致）

    return {
        "trade_date": f"{date[:4]}-{date[4:6]}-{date[6:8]}",
        "limit_up": up_n,
        "limit_down": down_n,
        "max_lbc": up["max_lbc"],
        "leaders": up["leaders"],
        "leader_names": up["rep_names"],
        "limit_down_samples": down["samples"],
        "topic_limit_up": up_tc if up_tc else up["count"],
        "topic_limit_down": down_tc if down_tc else down["count"],
        "source": count_source,
        "note": "家数对齐同花顺/东财客户端；连板代表来自东财涨停池；禁止贴全池",
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
