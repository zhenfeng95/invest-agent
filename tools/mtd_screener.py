#!/usr/bin/env python3
"""选股辅助：用户一层池全量四选一分析（收盘日报默认）+ 可选公式一层

收盘日报默认（用户自理第一层）:
  .venv/bin/python tools/mtd_screener.py
  # 或指定文件：
  .venv/bin/python tools/mtd_screener.py --from-pool data/raw/screener/pool-latest.csv

  读用户池 → 全量四选一 → stdout 打印「命中 / 未命中」两表 → 写入日报 §9
  不跑公式一层、不过东财主线 TOP 过滤。

可选：跑通达信月初至今公式池（调试/备查，非日报默认）:
  N:=BARSLAST(MONTH<>REF(MONTH,1))+1;
  MTD:=(C/REF(C,N)-1)*100;
  VOL5:=MA(V,5);
  XG:MTD>5 AND MTD<15 AND V>VOL5*1.2 AND AMOUNT>300000000
      AND TURN>2 AND C<30;
  .venv/bin/python tools/mtd_screener.py --formula
  # VOL5 含当日（通达信）；买点量能按 my-soul「不含当日」

输出（日报默认）:
  stdout：=== BUYSETUP_FOR_§9 === 命中表 + 未命中表 === END BUYSETUP ===
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _disable_proxies() -> None:
    """本机若配了系统/环境代理，东财 push2 常被拦；强制直连。"""
    for k in list(os.environ):
        if "proxy" in k.lower():
            del os.environ[k]
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    try:
        import requests

        _orig = requests.Session.request

        def _request(self, method, url, **kwargs):  # type: ignore[no-untyped-def]
            kwargs.setdefault("proxies", {"http": None, "https": None})
            return _orig(self, method, url, **kwargs)

        requests.Session.request = _request  # type: ignore[method-assign]
    except Exception:
        pass


_disable_proxies()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="用户一层池全量四选一（默认）/ 可选通达信公式一层（--formula）"
    )
    p.add_argument("--min-mtd", type=float, default=5.0, help="MTD 下限（不含），默认 5")
    p.add_argument("--max-mtd", type=float, default=15.0, help="MTD 上限（不含），默认 15")
    p.add_argument("--vol-mult", type=float, default=1.2, help="放量倍数，默认 1.2")
    p.add_argument(
        "--min-amount",
        type=float,
        default=3e8,
        help="成交额下限（元），默认 3e8=3亿",
    )
    p.add_argument(
        "--min-turnover",
        type=float,
        default=2.0,
        help="换手率下限(%%，不含)，默认 2",
    )
    p.add_argument(
        "--max-price",
        type=float,
        default=30.0,
        help="现价/收盘上限（元，不含），默认 30",
    )
    p.add_argument(
        "--include-st",
        action="store_true",
        help="默认排除 ST/*ST/退；加此开关则保留",
    )
    p.add_argument(
        "--include-bj",
        action="store_true",
        help="默认排除北交所(8/4开头)；加此开关则纳入",
    )
    p.add_argument("--workers", type=int, default=8, help="并发拉日线线程数")
    p.add_argument(
        "--prefilter-amount",
        action="store_true",
        default=True,
        help="先用现货成交额预筛（默认开）",
    )
    p.add_argument(
        "--no-prefilter-amount",
        action="store_false",
        dest="prefilter_amount",
        help="关闭现货预筛（更慢、更贴近全市场日线复算）",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=ROOT / "output" / "screener",
        help="输出目录",
    )
    p.add_argument(
        "--asof",
        type=str,
        default="",
        help="评估日 YYYY-MM-DD；默认用日线最新交易日",
    )
    p.add_argument(
        "--formula",
        action="store_true",
        help="跑通达信月初至今公式一层（非收盘日报默认；调试/备查）",
    )
    p.add_argument(
        "--refine",
        action="store_true",
        default=False,
        help="公式模式附加：东财主线∩四选一（仅 --formula 时有用）",
    )
    p.add_argument(
        "--no-refine",
        action="store_false",
        dest="refine",
        help="公式模式关闭主线二筛",
    )
    p.add_argument(
        "--mainline-top",
        type=int,
        default=8,
        help="东财行业涨幅 TOP N（仅 --formula --refine），默认 8",
    )
    p.add_argument(
        "--touch-pct",
        type=float,
        default=2.0,
        help="回踩贴近均线/趋势线容忍%%，默认 2",
    )
    p.add_argument(
        "--breakout-max-ext",
        type=float,
        default=3.0,
        help="突破类距 MA5 最大延伸%%（防追加速），默认 3",
    )
    p.add_argument(
        "--from-pool",
        type=Path,
        default=None,
        help="用户一层池文件（csv/txt）；默认 data/raw/screener/pool-latest.csv",
    )
    p.add_argument(
        "--write-buysetup",
        action="store_true",
        help="调试：额外把分析结果写入 *-buysetup.csv/.md（默认只打印）",
    )
    return p.parse_args()


DEFAULT_USER_POOL = ROOT / "data" / "raw" / "screener" / "pool-latest.csv"


def load_user_pool(path: Path) -> list[dict[str, Any]]:
    """读取用户第一层池：csv(code[,name,...]) 或 txt(每行一个代码)。"""
    if not path.exists():
        raise FileNotFoundError(f"池文件不存在: {path}")
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []

    rows: list[dict[str, Any]] = []
    if path.suffix.lower() == ".csv" or "," in text.splitlines()[0]:
        import io

        reader = csv.DictReader(io.StringIO(text))
        # 允许无表头：纯 code 列
        if reader.fieldnames and any(
            (f or "").lower() in ("code", "代码", "symbol", "ticker")
            for f in reader.fieldnames
        ):
            for r in reader:
                code = ""
                name = ""
                for k, v in r.items():
                    kl = (k or "").lower()
                    if kl in ("code", "代码", "symbol", "ticker"):
                        code = str(v or "").strip()
                    elif kl in ("name", "名称", "简称"):
                        name = str(v or "").strip()
                code = "".join(ch for ch in code if ch.isdigit()).zfill(6)[-6:]
                if code and len(code) == 6:
                    rows.append({"code": code, "name": name})
        else:
            # 无标准表头：第一列当代码
            path_rows = list(csv.reader(io.StringIO(text)))
            start = 1 if path_rows and not any(ch.isdigit() for ch in path_rows[0][0]) else 0
            for parts in path_rows[start:]:
                if not parts:
                    continue
                code = "".join(ch for ch in parts[0] if ch.isdigit()).zfill(6)[-6:]
                name = parts[1].strip() if len(parts) > 1 else ""
                if code and len(code) == 6:
                    rows.append({"code": code, "name": name})
    else:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 支持 300827 或 300827 上能电气
            parts = line.replace(",", " ").split()
            code = "".join(ch for ch in parts[0] if ch.isdigit()).zfill(6)[-6:]
            name = " ".join(parts[1:]) if len(parts) > 1 else ""
            if code and len(code) == 6:
                rows.append({"code": code, "name": name})

    # 去重保序
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        if r["code"] in seen:
            continue
        seen.add(r["code"])
        out.append(r)
    return out


def enrich_pool_from_spot(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """用现货补名称/价/额/换手，供二筛排序与输出。"""
    try:
        spot = fetch_spot()
        by_code = {r.code: r for r in spot.itertuples(index=False)}
    except Exception:
        by_code = {}

    hits: list[dict[str, Any]] = []
    today_s = date.today().isoformat()
    for p in pool:
        code = p["code"]
        sp = by_code.get(code)
        name = p.get("name") or (getattr(sp, "name", "") if sp else "")
        price = float(getattr(sp, "price", 0) or 0) if sp else 0.0
        amount = float(getattr(sp, "amount", 0) or 0) if sp else 0.0
        turnover = float(getattr(sp, "turnover", 0) or 0) if sp else 0.0
        hits.append(
            {
                "code": code,
                "name": name or code,
                "asof": today_s,
                "close": price,
                "prev_month_end_close": 0.0,
                "mtd_pct": 0.0,
                "turnover": turnover,
                "volume": 0,
                "vol5": 0,
                "vol_ratio": 0.0,
                "amount": int(amount),
                "amount_yi": round(amount / 1e8, 2) if amount else 0.0,
            }
        )
    return hits


def _is_st_name(name: str) -> bool:
    n = (name or "").upper().replace(" ", "")
    return "ST" in n or "退" in (name or "")


def _is_bj(code: str) -> bool:
    return code.startswith(("8", "4"))


import threading

_thread_local = threading.local()


def _em_session():
    """线程局部 Session；优先 curl_cffi 伪装 Chrome。"""
    cached = getattr(_thread_local, "em_session", None)
    if cached is not None:
        return cached

    try:
        from curl_cffi import requests as creq

        s = creq.Session(impersonate="chrome120")
        backend = "curl_cffi"
    except Exception:
        import requests

        s = requests.Session()
        s.trust_env = False
        s.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://quote.eastmoney.com/",
            }
        )
        backend = "requests"

    pair = (s, backend)
    _thread_local.em_session = pair
    return pair


_SPOT_HOSTS = [
    "https://push2delay.eastmoney.com/api/qt/clist/get",
    "https://82.push2.eastmoney.com/api/qt/clist/get",
    "https://7.push2.eastmoney.com/api/qt/clist/get",
    "https://push2.eastmoney.com/api/qt/clist/get",
]

_HIST_HOSTS = [
    "https://91.push2his.eastmoney.com/api/qt/stock/kline/get",
    "https://92.push2his.eastmoney.com/api/qt/stock/kline/get",
    "https://94.push2his.eastmoney.com/api/qt/stock/kline/get",
    "https://97.push2his.eastmoney.com/api/qt/stock/kline/get",
    "https://push2his.eastmoney.com/api/qt/stock/kline/get",
]


def _symbol_tx(code: str) -> str:
    return f"sh{code}" if code.startswith(("6", "5", "9")) else f"sz{code}"


def _requests_plain():
    import requests

    s = requests.Session()
    s.trust_env = False
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
    )
    return s


def fetch_hist_tencent(code: str, limit: int = 60) -> pd.DataFrame | None:
    """腾讯日 K（不复权 day）；成交额字段单位为万元。"""
    symbol = _symbol_tx(code)
    url = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
    params = {"param": f"{symbol},day,,,{limit},"}
    s = _requests_plain()
    try:
        r = s.get(url, params=params, timeout=15, proxies={"http": None, "https": None})
        r.raise_for_status()
        block = (r.json().get("data") or {}).get(symbol) or {}
        raw = block.get("day") or block.get("qfqday") or []
    except Exception:
        return None
    if not raw:
        return None
    records = []
    for row in raw:
        if len(row) < 6:
            continue
        amount = None
        if len(row) > 8 and row[8] not in ("", None, {}):
            try:
                amount = float(row[8]) * 10000.0  # 万元 → 元
            except (TypeError, ValueError):
                amount = None
        records.append(
            {
                "date": row[0],
                "open": row[1],
                "close": row[2],
                "high": row[3],
                "low": row[4],
                "volume": row[5],
                "amount": amount,
            }
        )
    if not records:
        return None
    df = pd.DataFrame(records)
    for c in ("open", "close", "high", "low", "volume", "amount"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["turnover"] = float("nan")
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df.dropna(subset=["date", "close", "volume"]).sort_values("date")


def fetch_hist_sina(code: str, datalen: int = 60) -> pd.DataFrame | None:
    """新浪日 K；无成交额/换手，仅作价量兜底。"""
    symbol = _symbol_tx(code)
    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": symbol, "scale": "240", "ma": "no", "datalen": str(datalen)}
    s = _requests_plain()
    try:
        r = s.get(url, params=params, timeout=15, proxies={"http": None, "https": None})
        r.raise_for_status()
        raw = r.json()
    except Exception:
        return None
    if not raw:
        return None
    records = [
        {
            "date": x["day"],
            "close": x["close"],
            "high": x.get("high", x["close"]),
            "low": x.get("low", x["close"]),
            # 新浪 volume 为股；统一成「手」以便与腾讯/东财量级接近（÷100）
            "volume": float(x["volume"]) / 100.0,
            "amount": float("nan"),
            "turnover": float("nan"),
        }
        for x in raw
    ]
    df = pd.DataFrame(records)
    for c in ("close", "high", "low", "volume", "amount", "turnover"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df.dropna(subset=["date", "close", "volume"]).sort_values("date")


def _secid(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return f"1.{code}"
    return f"0.{code}"


def fetch_hist_eastmoney(code: str, start: str, end: str) -> pd.DataFrame | None:
    """东财日 K；失败返回 None。"""
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "klt": "101",
        "fqt": "0",
        "secid": _secid(code),
        "beg": start,
        "end": end,
    }
    s, backend = _em_session()
    raw = None
    for host in _HIST_HOSTS:
        try:
            kw = {"params": params, "timeout": 8}
            if backend == "requests":
                kw["proxies"] = {"http": None, "https": None}
            r = s.get(host, **kw)
            r.raise_for_status()
            klines = ((r.json().get("data") or {}).get("klines")) or []
            if klines:
                raw = klines
                break
        except Exception:
            continue
    if not raw:
        return None

    records = []
    for line in raw:
        parts = line.split(",")
        if len(parts) < 7:
            continue
        records.append(
            {
                "date": parts[0],
                "close": parts[2],
                "high": parts[3],
                "low": parts[4],
                "volume": parts[5],
                "amount": parts[6],
                "turnover": parts[10] if len(parts) > 10 else None,
            }
        )
    if not records:
        return None
    df = pd.DataFrame(records)
    for c in ("close", "high", "low", "volume", "amount", "turnover"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df.dropna(subset=["date", "close", "volume", "amount"]).sort_values("date")


def fetch_hist(code: str, start: str, end: str) -> pd.DataFrame | None:
    """日 K：腾讯 → 新浪 → 东财（当前东财 his 常被掐）。"""
    df = fetch_hist_tencent(code)
    if df is not None and not df.empty:
        return df
    df = fetch_hist_sina(code)
    if df is not None and not df.empty:
        return df
    return fetch_hist_eastmoney(code, start, end)


def fetch_spot() -> pd.DataFrame:
    """东财全 A 现货分页。"""
    fs = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
    # f8=换手率(%)
    fields = "f12,f14,f2,f3,f5,f6,f8"
    rows: list[dict[str, Any]] = []
    page = 1
    total = None
    s, backend = _em_session()
    print(f"   现货后端: {backend}", flush=True)
    while True:
        params = {
            "pn": page,
            "pz": 100,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f6",
            "fs": fs,
            "fields": fields,
        }
        last_err: Exception | None = None
        data = None
        for host in _SPOT_HOSTS:
            for attempt in range(2):
                try:
                    kw = {"params": params, "timeout": 20}
                    if backend == "requests":
                        kw["proxies"] = {"http": None, "https": None}
                    r = s.get(host, **kw)
                    r.raise_for_status()
                    data = r.json().get("data") or {}
                    break
                except Exception as e:
                    last_err = e
                    time.sleep(0.3 * (attempt + 1))
            if data is not None:
                break
        if data is None:
            raise RuntimeError(f"现货拉取失败 page={page}: {last_err}")
        if total is None:
            total = int(data.get("total") or 0)
        diff = data.get("diff") or []
        if not diff:
            break
        for item in diff:
            rows.append(
                {
                    "code": str(item.get("f12", "")).zfill(6),
                    "name": item.get("f14") or "",
                    "price": item.get("f2"),
                    "chg_pct": item.get("f3"),
                    "volume": item.get("f5"),
                    "amount": item.get("f6"),
                    "turnover": item.get("f8"),
                }
            )
        if len(rows) >= total or len(diff) < 100:
            break
        page += 1
        if page % 10 == 0:
            print(f"   …现货已拉 {len(rows)}/{total}", flush=True)
        time.sleep(0.05)

    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("现货接口返回空")
    for c in ("price", "chg_pct", "volume", "amount", "turnover"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out.dropna(subset=["code", "amount"])


def prev_month_end_close(df: pd.DataFrame, asof: pd.Timestamp) -> float | None:
    """通达信 REF(C,N)：上月最后一个交易日收盘。"""
    hist = df[df["date"] <= asof]
    if hist.empty:
        return None
    cur_month = asof.to_period("M")
    prev = hist[hist["date"].dt.to_period("M") < cur_month]
    if prev.empty:
        return None
    return float(prev.iloc[-1]["close"])


def eval_row(
    code: str,
    name: str,
    hist: pd.DataFrame,
    *,
    asof: pd.Timestamp | None,
    min_mtd: float,
    max_mtd: float,
    vol_mult: float,
    min_amount: float,
    min_turnover: float,
    max_price: float,
    turnover_fallback: float | None = None,
    amount_fallback: float | None = None,
) -> dict[str, Any] | None:
    if hist is None or hist.empty:
        return None
    if asof is not None:
        hist = hist[hist["date"] <= asof]
    if len(hist) < 5:
        return None

    row = hist.iloc[-1]
    asof_d = row["date"]
    close = float(row["close"])
    vol = float(row["volume"])
    amount = float(row["amount"]) if pd.notna(row.get("amount")) else float("nan")
    if (not pd.notna(amount)) and amount_fallback is not None:
        amount = float(amount_fallback)

    turnover = row.get("turnover")
    try:
        turnover_f = float(turnover) if pd.notna(turnover) else float("nan")
    except (TypeError, ValueError):
        turnover_f = float("nan")
    if (not pd.notna(turnover_f)) and turnover_fallback is not None:
        turnover_f = float(turnover_fallback)

    ref = prev_month_end_close(hist, asof_d)
    if ref is None or ref <= 0:
        return None

    mtd = (close / ref - 1.0) * 100.0
    vol5 = float(hist["volume"].iloc[-5:].mean())  # 含当日，通达信 MA(V,5)
    if vol5 <= 0:
        return None

    vol_ratio = vol / vol5
    hit = (
        mtd > min_mtd
        and mtd < max_mtd
        and vol > vol5 * vol_mult
        and pd.notna(amount)
        and amount > min_amount
        and close < max_price
        and pd.notna(turnover_f)
        and turnover_f > min_turnover
    )
    if not hit:
        return None

    return {
        "code": code,
        "name": name,
        "asof": asof_d.strftime("%Y-%m-%d"),
        "close": round(close, 4),
        "prev_month_end_close": round(ref, 4),
        "mtd_pct": round(mtd, 2),
        "turnover": round(turnover_f, 2),
        "volume": int(vol),
        "vol5": int(round(vol5)),
        "vol_ratio": round(vol_ratio, 3),
        "amount": int(round(amount)),
        "amount_yi": round(amount / 1e8, 2),
    }


def fetch_mainline_membership(top_n: int = 8) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """东财行业 TOP N → {code: 行业名}, 行业列表。"""
    s, backend = _em_session()
    params = {
        "pn": 1,
        "pz": max(top_n * 3, 30),
        "po": 1,
        "np": 1,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": "m:90+t:2",
        "fields": "f12,f14,f3",
    }
    data = None
    last_err: Exception | None = None
    for host in _SPOT_HOSTS:
        try:
            kw: dict[str, Any] = {"params": params, "timeout": 20}
            if backend == "requests":
                kw["proxies"] = {"http": None, "https": None}
            r = s.get(host, **kw)
            r.raise_for_status()
            data = r.json().get("data") or {}
            break
        except Exception as e:
            last_err = e
            time.sleep(0.3)
    if data is None:
        raise RuntimeError(f"东财行业榜失败: {last_err}")

    boards: list[dict[str, Any]] = []
    for item in (data.get("diff") or [])[:top_n]:
        try:
            chg = float(item.get("f3"))
        except (TypeError, ValueError):
            continue
        boards.append(
            {"bk": str(item.get("f12") or ""), "name": item.get("f14") or "", "chg_pct": chg}
        )

    code_to_ind: dict[str, str] = {}
    for b in boards:
        bk = b["bk"]
        if not bk:
            continue
        page = 1
        total = None
        while True:
            p = {
                "pn": page,
                "pz": 100,
                "po": 1,
                "np": 1,
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": f"b:{bk}",
                "fields": "f12,f14",
            }
            payload = None
            for host in _SPOT_HOSTS:
                try:
                    kw = {"params": p, "timeout": 15}
                    if backend == "requests":
                        kw["proxies"] = {"http": None, "https": None}
                    r = s.get(host, **kw)
                    r.raise_for_status()
                    payload = r.json().get("data") or {}
                    break
                except Exception:
                    continue
            if payload is None:
                break
            if total is None:
                total = int(payload.get("total") or 0)
            diff = payload.get("diff") or []
            if not diff:
                break
            for item in diff:
                code_to_ind[str(item.get("f12", "")).zfill(6)] = b["name"]
            if len(diff) < 100 or (total is not None and page * 100 >= total):
                break
            page += 1
            time.sleep(0.05)
        time.sleep(0.05)
    return code_to_ind, boards


def refine_hits(
    hits: list[dict[str, Any]],
    *,
    start: str,
    end: str,
    asof_ts: pd.Timestamp | None,
    workers: int,
    mainline_top: int,
    touch_pct: float,
    breakout_max_ext: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    """返回 (精选列表, 主线行业, 备注)。"""
    # 延迟导入，避免脚本路径问题
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from buy_setup_filter import detect_buy_setups  # type: ignore

    print(
        f"3/4 东财主线 TOP{mainline_top} + 四选一买点二筛…",
        flush=True,
    )
    try:
        code_to_ind, boards = fetch_mainline_membership(mainline_top)
    except Exception as e:
        return [], [], f"主线拉取失败: {e}"

    board_desc = "、".join(f"{b['name']}({b['chg_pct']:+.2f}%)" for b in boards)
    print(f"   主线: {board_desc}", flush=True)
    print(f"   主线成分约 {len(code_to_ind)} 只；公式池 {len(hits)} 只", flush=True)

    in_main = [h for h in hits if h["code"] in code_to_ind]
    print(f"   公式∩主线: {len(in_main)}", flush=True)
    if not in_main:
        return [], boards, board_desc

    refined: list[dict[str, Any]] = []
    done = 0
    t0 = time.time()

    def job(h: dict[str, Any]) -> dict[str, Any] | None:
        hist = fetch_hist(h["code"], start, end)
        if hist is None or hist.empty:
            return None
        if asof_ts is not None:
            hist = hist[hist["date"] <= asof_ts]
        setup = detect_buy_setups(
            hist,
            touch_pct=touch_pct,
            breakout_max_ext_pct=breakout_max_ext,
        )
        if setup is None:
            return None
        out = dict(h)
        out["industry"] = code_to_ind.get(h["code"], "")
        out["signal"] = setup["signal"]
        out["vr_ex"] = setup["vr_ex"]
        out["ma5"] = setup["ma5"]
        out["ext_ma5_pct"] = setup["ext_ma5_pct"]
        out["vol_side"] = setup["vol_side"]
        out["v"] = setup["v"]
        out["ma_v5_ex"] = setup["ma_v5_ex"]
        return out

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(job, h): h["code"] for h in in_main}
        for fut in as_completed(futs):
            done += 1
            if done % 20 == 0 or done == len(futs):
                print(
                    f"   …买点 {done}/{len(futs)} 精选 {len(refined)} "
                    f"({time.time() - t0:.0f}s)",
                    flush=True,
                )
            try:
                r = fut.result()
            except Exception:
                continue
            if r is not None:
                refined.append(r)

    refined.sort(key=lambda x: (-x["amount"], -x["mtd_pct"]))
    return refined, boards, board_desc


def analyze_user_pool(
    hits: list[dict[str, Any]],
    *,
    start: str,
    end: str,
    asof_ts: pd.Timestamp | None,
    workers: int,
    touch_pct: float,
    breakout_max_ext: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """用户池全量四选一；返回 (全部, 命中, 未命中)。不过主线过滤。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from buy_setup_filter import analyze_buy_setup  # type: ignore

    print(f"2/2 全量四选一分析（{len(hits)} 只）…", flush=True)
    all_rows: list[dict[str, Any]] = []
    done = 0
    t0 = time.time()

    def job(h: dict[str, Any]) -> dict[str, Any]:
        hist = fetch_hist(h["code"], start, end)
        out = dict(h)
        if hist is None or hist.empty:
            out.update(
                {
                    "hit": False,
                    "signal": "—",
                    "miss_reason": "日线未获取",
                    "v": "",
                    "ma_v5_ex": "",
                    "vr_ex": "",
                    "ma5": "",
                    "ext_ma5_pct": "",
                    "vol_side": "",
                }
            )
            return out
        if asof_ts is not None:
            hist = hist[hist["date"] <= asof_ts]
        setup = analyze_buy_setup(
            hist,
            touch_pct=touch_pct,
            breakout_max_ext_pct=breakout_max_ext,
        )
        if setup is None:
            out.update(
                {
                    "hit": False,
                    "signal": "—",
                    "miss_reason": "数据不足",
                    "v": "",
                    "ma_v5_ex": "",
                    "vr_ex": "",
                    "ma5": "",
                    "ext_ma5_pct": "",
                    "vol_side": "",
                }
            )
            return out
        out["hit"] = bool(setup["hit"])
        out["signal"] = setup["signal"]
        out["miss_reason"] = setup.get("miss_reason", "")
        out["vr_ex"] = setup["vr_ex"]
        out["ma5"] = setup["ma5"]
        out["ext_ma5_pct"] = setup["ext_ma5_pct"]
        out["vol_side"] = setup["vol_side"]
        out["v"] = setup["v"]
        out["ma_v5_ex"] = setup["ma_v5_ex"]
        if "close" in setup and setup["close"]:
            out["close"] = setup["close"]
        return out

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(job, h): h["code"] for h in hits}
        for fut in as_completed(futs):
            done += 1
            if done % 20 == 0 or done == len(futs):
                print(
                    f"   …分析 {done}/{len(futs)} ({time.time() - t0:.0f}s)",
                    flush=True,
                )
            try:
                all_rows.append(fut.result())
            except Exception:
                code = futs[fut]
                all_rows.append(
                    {
                        "code": code,
                        "name": "",
                        "hit": False,
                        "signal": "—",
                        "miss_reason": "分析异常",
                        "close": "",
                        "turnover": "",
                        "v": "",
                        "ma_v5_ex": "",
                        "vr_ex": "",
                        "ma5": "",
                        "ext_ma5_pct": "",
                        "vol_side": "",
                    }
                )

    all_rows.sort(key=lambda x: (not x.get("hit", False), str(x.get("code", ""))))
    hit_rows = [r for r in all_rows if r.get("hit")]
    miss_rows = [r for r in all_rows if not r.get("hit")]
    return all_rows, hit_rows, miss_rows


def _row_md_line(h: dict[str, Any], *, miss: bool = False) -> str:
    buy = h.get("signal", "—") if not miss else (
        h.get("miss_reason") or h.get("signal") or "未命中"
    )
    return (
        f"| {h.get('code','')} | {h.get('name','')} | {buy} | "
        f"{h.get('close','')} | {h.get('ma5','')} | {h.get('ext_ma5_pct','')} | "
        f"{h.get('v','')} | {h.get('ma_v5_ex','')} | {h.get('vr_ex','')} | "
        f"{h.get('turnover','')} |"
    )


def format_buysetup_md(
    *,
    stamp: str,
    asof_label: str,
    hit_rows: list[dict[str, Any]],
    miss_rows: list[dict[str, Any]],
    pool_label: str,
    touch_pct: float,
    breakout_max_ext: float,
) -> str:
    """用户池全量分析结果 Markdown（供日报 §9）。"""
    n = len(hit_rows) + len(miss_rows)
    header = (
        "| 代码 | 简称 | 买点 | 收盘 | MA5 | ext | V | MA(V,5) | VR | 换手% |"
    )
    sep = "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    lines = [
        f"# 用户池四选一全量分析 {stamp} — 供日报 §9",
        "",
        f"- 评估日: {asof_label}",
        f"- 第一层来源: {pool_label}（用户自理；Agent 不代选）",
        f"- 买点: 四选一；量能按 my-soul（MA(V,5)不含当日）；"
        f"回踩≤{touch_pct}%；突破延伸≤{breakout_max_ext}%",
        f"- 趋势线为自动近似（波峰/波谷连线），人工画线可能不一致",
        f"- 池内 {n} → 命中 {len(hit_rows)} / 未命中 {len(miss_rows)}",
        f"- 非荐股；写入日报 §9「明日值得关注的个股」",
        "",
        "## 命中四选一",
        "",
        header,
        sep,
    ]
    if hit_rows:
        for h in hit_rows:
            lines.append(_row_md_line(h, miss=False))
    else:
        lines.append("| — | 无命中 | — | — | — | — | — | — | — | — |")
    lines.extend(
        [
            "",
            "## 未命中",
            "",
            header,
            sep,
        ]
    )
    if miss_rows:
        for h in miss_rows:
            lines.append(_row_md_line(h, miss=True))
    else:
        lines.append("| — | 全部命中 | — | — | — | — | — | — | — | — |")
    lines.append("")
    return "\n".join(lines)


def emit_buysetup(
    *,
    args: argparse.Namespace,
    stamp: str,
    asof_label: str,
    hit_rows: list[dict[str, Any]],
    miss_rows: list[dict[str, Any]],
    pool_label: str,
) -> None:
    """打印全量分析供日报 §9；仅 --write-buysetup 时才写文件。"""
    md = format_buysetup_md(
        stamp=stamp,
        asof_label=asof_label,
        hit_rows=hit_rows,
        miss_rows=miss_rows,
        pool_label=pool_label,
        touch_pct=args.touch_pct,
        breakout_max_ext=args.breakout_max_ext,
    )
    print("=== BUYSETUP_FOR_§9（用户池全量 · 勿默认落盘）===", flush=True)
    print(md, flush=True)
    print("=== END BUYSETUP ===", flush=True)
    print(
        f"命中 {len(hit_rows)} / 未命中 {len(miss_rows)} → 写入日报 §9",
        flush=True,
    )
    for h in hit_rows[:20]:
        print(
            f"   ✓ {h.get('code')} {h.get('name')} {h.get('signal')} "
            f"价={h.get('close')} MA5={h.get('ma5')} VR={h.get('vr_ex')}",
            flush=True,
        )

    if not args.write_buysetup:
        return

    fields = [
        "code",
        "name",
        "hit",
        "signal",
        "miss_reason",
        "close",
        "ma5",
        "ext_ma5_pct",
        "v",
        "ma_v5_ex",
        "vr_ex",
        "turnover",
        "vol_side",
        "amount",
        "amount_yi",
        "mtd_pct",
    ]
    all_rows = hit_rows + miss_rows
    out2_csv = args.out / f"user-pool-analyze-{stamp}.csv"
    out2_md = args.out / f"user-pool-analyze-{stamp}.md"
    with out2_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)
    out2_md.write_text(md, encoding="utf-8")
    print(f"（调试）已写分析 → {out2_csv}", flush=True)
    print(f"（调试）摘要 → {out2_md}", flush=True)


def main() -> int:
    args = _parse_args()
    asof_ts = pd.Timestamp(args.asof) if args.asof else None
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    today = date.today()
    start = (today.replace(day=1) - timedelta(days=40)).strftime("%Y%m%d")
    end = (today + timedelta(days=1)).strftime("%Y%m%d")

    # —— 默认：用户一层池 → 全量四选一（命中 / 未命中）——
    if not args.formula:
        pool_path = args.from_pool or DEFAULT_USER_POOL
        print(f"1/2 读取用户一层池: {pool_path}", flush=True)
        if not pool_path.exists():
            print(f"一层池文件不存在: {pool_path}", flush=True)
            print("=== BUYSETUP_FOR_§9 ===", flush=True)
            print("用户未提供一层池（文件不存在）", flush=True)
            print("=== END BUYSETUP ===", flush=True)
            return 0
        pool = load_user_pool(pool_path)
        if not pool:
            print("一层池为空。", flush=True)
            print("=== BUYSETUP_FOR_§9 ===", flush=True)
            print("用户未提供一层池（文件为空）", flush=True)
            print("=== END BUYSETUP ===", flush=True)
            return 0
        print(f"   {len(pool)} 只", flush=True)
        hits = enrich_pool_from_spot(pool)
        _all, hit_rows, miss_rows = analyze_user_pool(
            hits,
            start=start,
            end=end,
            asof_ts=asof_ts,
            workers=args.workers,
            touch_pct=args.touch_pct,
            breakout_max_ext=args.breakout_max_ext,
        )
        asof_label = args.asof or stamp
        emit_buysetup(
            args=args,
            stamp=stamp,
            asof_label=asof_label,
            hit_rows=hit_rows,
            miss_rows=miss_rows,
            pool_label=str(pool_path),
        )
        return 0

    # —— 可选：通达信公式一层（--formula）——
    print("1/4 拉取 A 股现货…", flush=True)
    spot = fetch_spot()
    n0 = len(spot)

    if not args.include_st:
        spot = spot[~spot["name"].map(_is_st_name)]
    if not args.include_bj:
        spot = spot[~spot["code"].map(_is_bj)]

    if args.prefilter_amount:
        spot = spot[spot["amount"] > args.min_amount]
    # 现货预筛：换手、股价（最终仍以日线收盘复核）
    spot = spot[spot["price"] < args.max_price]
    spot = spot[spot["turnover"] > args.min_turnover]

    spot = spot.reset_index(drop=True)
    print(
        f"   全市场 {n0} → 过滤后待复算 {len(spot)} "
        f"(额>{args.min_amount/1e8:.0f}亿预筛={'开' if args.prefilter_amount else '关'}；"
        f"换手>{args.min_turnover}%；价<{args.max_price})",
        flush=True,
    )
    if spot.empty:
        print("无候选，退出。", flush=True)
        return 0

    print(f"2/4 并发拉日线 workers={args.workers} 区间={start}~{end} …", flush=True)
    hits: list[dict[str, Any]] = []
    errors = 0
    done = 0
    t0 = time.time()

    def job(
        code: str,
        name: str,
        turnover: float,
        amount: float,
    ) -> tuple[str, dict[str, Any] | None]:
        hist = fetch_hist(code, start, end)
        if hist is None:
            return ("err", None)
        hit = eval_row(
            code,
            name,
            hist,
            asof=asof_ts,
            min_mtd=args.min_mtd,
            max_mtd=args.max_mtd,
            vol_mult=args.vol_mult,
            min_amount=args.min_amount,
            min_turnover=args.min_turnover,
            max_price=args.max_price,
            turnover_fallback=float(turnover) if pd.notna(turnover) else None,
            amount_fallback=float(amount) if pd.notna(amount) else None,
        )
        return ("ok", hit)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {
            ex.submit(job, r.code, r.name, r.turnover, r.amount): r.code
            for r in spot.itertuples(index=False)
        }
        for fut in as_completed(futs):
            done += 1
            if done % 50 == 0 or done == len(futs):
                elapsed = time.time() - t0
                print(
                    f"   … {done}/{len(futs)} 命中 {len(hits)} "
                    f"({elapsed:.0f}s)",
                    flush=True,
                )
            try:
                status, r = fut.result()
            except Exception:
                errors += 1
                continue
            if status == "err":
                errors += 1
                continue
            if r is not None:
                hits.append(r)

    hits.sort(key=lambda x: (-x["amount"], -x["mtd_pct"]))

    out_csv = args.out / f"mtd-screener-{stamp}.csv"
    out_md = args.out / f"mtd-screener-{stamp}.md"

    fields = [
        "code",
        "name",
        "asof",
        "close",
        "prev_month_end_close",
        "mtd_pct",
        "turnover",
        "volume",
        "vol5",
        "vol_ratio",
        "amount",
        "amount_yi",
    ]
    with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(hits)

    asof_label = hits[0]["asof"] if hits else (args.asof or "最新交易日")
    lines = [
        f"# 月初至今选股 {stamp}",
        "",
        f"- 评估日: {asof_label}",
        f"- 条件: {args.min_mtd} < MTD% < {args.max_mtd}；"
        f"V > MA(V,5)×{args.vol_mult}（含当日）；"
        f"成交额 > {args.min_amount/1e8:.0f} 亿；"
        f"换手 > {args.min_turnover}%；"
        f"收盘 < {args.max_price} 元",
        f"- 候选复算: {len(spot)}；命中: {len(hits)}；接口异常约: {errors}",
        f"- 口径: 通达信 XG 公式池；非买卖信号",
        "",
        "| 代码 | 名称 | 收盘 | MTD% | 换手% | 量比V/VOL5 | 成交额(亿) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for h in hits:
        lines.append(
            f"| {h['code']} | {h['name']} | {h['close']} | {h['mtd_pct']} | "
            f"{h['turnover']} | {h['vol_ratio']} | {h['amount_yi']} |"
        )
    if not hits:
        lines.append("| — | 无命中 | — | — | — | — | — |")
    lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"公式池 {len(hits)} 只 → {out_csv}", flush=True)

    if args.refine and hits:
        refined, _boards, board_desc = refine_hits(
            hits,
            start=start,
            end=end,
            asof_ts=asof_ts,
            workers=args.workers,
            mainline_top=args.mainline_top,
            touch_pct=args.touch_pct,
            breakout_max_ext=args.breakout_max_ext,
        )
        # 公式+主线模式：命中=refined，未命中不展开（仅调试）
        emit_buysetup(
            args=args,
            stamp=stamp,
            asof_label=asof_label,
            hit_rows=refined,
            miss_rows=[],
            pool_label=f"脚本公式池∩东财TOP{args.mainline_top}（{board_desc}）",
        )
        print("4/4 完成", flush=True)
    else:
        print("3/3 完成（未开主线二筛）", flush=True)
        if hits:
            for h in hits[:10]:
                print(
                    f"   {h['code']} {h['name']} 价={h['close']} MTD={h['mtd_pct']}% "
                    f"换手={h['turnover']}% VR={h['vol_ratio']} 额={h['amount_yi']}亿",
                    flush=True,
                )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n中断", file=sys.stderr)
        raise SystemExit(130)
