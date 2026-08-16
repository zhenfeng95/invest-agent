#!/usr/bin/env python3
"""东财 CYQ 筹码分布 **汇总指标**（§7 筹码势用）。

算法：移植东财前端 CYQCalculator（与 AKShare stock_cyq_em 同源）。
原料：东财日 K（含换手率）；**非**直连接口返回分布图。
输出：获利比例、平均成本、70%/90% 成本区间与集中度（最新交易日）。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Any

import requests

try:
    from py_mini_racer import py_mini_racer
except ImportError:
    py_mini_racer = None  # type: ignore

_CYQ_JS = r"""
function CYQCalculator(index, klinedata) {
    var maxprice = 0;
    var minprice = 0;
    var factor = 150;
    var start = this.range ? Math.max(0, index - this.range + 1) : 0;
    var kdata = klinedata.slice(start, Math.max(1, index + 1));
    if (kdata.length === 0) throw 'invaild index';
    for (var i = 0; i < kdata.length; i++) {
        var elements = kdata[i];
        maxprice = !maxprice ? elements.high : Math.max(maxprice, elements.high);
        minprice = !minprice ? elements.low : Math.min(minprice, elements.low);
    }
    var accuracy = Math.max(0.01, (maxprice - minprice) / (factor - 1));
    var yrange = [];
    for (var i = 0; i < factor; i++) {
        yrange.push((minprice + accuracy * i).toFixed(2) / 1);
    }
    var xdata = createNumberArray(factor);
    for (var i = 0; i < kdata.length; i++) {
        var eles = kdata[i];
        var open = eles.open, close = eles.close, high = eles.high, low = eles.low,
            avg = (open + close + high + low) / 4,
            turnoverRate = Math.min(1, eles.hsl / 100 || 0);
        var H = Math.floor((high - minprice) / accuracy),
            L = Math.ceil((low - minprice) / accuracy),
            GPoint = [high == low ? factor - 1 : 2 / (high - low), Math.floor((avg - minprice) / accuracy)];
        for (var n = 0; n < xdata.length; n++) {
            xdata[n] *= (1 - turnoverRate);
        }
        if (high == low) {
            xdata[GPoint[1]] += GPoint[0] * turnoverRate / 2;
        } else {
            for (var j = L; j <= H; j++) {
                var curprice = minprice + accuracy * j;
                if (curprice <= avg) {
                    if (Math.abs(avg - low) < 1e-8) {
                        xdata[j] += GPoint[0] * turnoverRate;
                    } else {
                        xdata[j] += (curprice - low) / (avg - low) * GPoint[0] * turnoverRate;
                    }
                } else {
                    if (Math.abs(high - avg) < 1e-8) {
                        xdata[j] += GPoint[0] * turnoverRate;
                    } else {
                        xdata[j] += (high - curprice) / (high - avg) * GPoint[0] * turnoverRate;
                    }
                }
            }
        }
    }
    var currentprice = klinedata[index].close;
    var totalChips = 0;
    for (var i = 0; i < factor; i++) {
        totalChips += xdata[i].toPrecision(12) / 1;
    }
    var result = new CYQData();
    result.x = xdata;
    result.y = yrange;
    result.benefitPart = result.getBenefitPart(currentprice);
    result.avgCost = getCostByChip(totalChips * 0.5).toFixed(2);
    result.percentChips = {
        '90': result.computePercentChips(0.9),
        '70': result.computePercentChips(0.7)
    };
    return result;
    function getCostByChip(chip) {
        var result = 0, sum = 0;
        for (var i = 0; i < factor; i++) {
            var x = xdata[i].toPrecision(12) / 1;
            if (sum + x > chip) {
                result = minprice + i * accuracy;
                break;
            }
            sum += x;
        }
        return result;
    }
    function CYQData() {
        this.x = arguments[0];
        this.y = arguments[1];
        this.benefitPart = arguments[2];
        this.avgCost = arguments[3];
        this.percentChips = arguments[4];
        this.computePercentChips = function (percent) {
            if (percent > 1 || percent < 0) throw 'argument "percent" out of range';
            var ps = [(1 - percent) / 2, (1 + percent) / 2];
            var pr = [getCostByChip(totalChips * ps[0]), getCostByChip(totalChips * ps[1])];
            return {
                priceRange: [pr[0].toFixed(2), pr[1].toFixed(2)],
                concentration: pr[0] + pr[1] === 0 ? 0 : (pr[1] - pr[0]) / (pr[0] + pr[1])
            };
        };
        this.getBenefitPart = function (price) {
            var below = 0;
            for (var i = 0; i < factor; i++) {
                var x = xdata[i].toPrecision(12) / 1;
                if (price >= minprice + i * accuracy) {
                    below += x;
                }
            }
            return totalChips == 0 ? 0 : below / totalChips;
        };
    }
}
function createNumberArray(count) {
    var array = [];
    for (var i = 0; i < count; i++) {
        array.push(0);
    }
    return array;
}
"""

_HIST_HOSTS = (
    "https://91.push2his.eastmoney.com/api/qt/stock/kline/get",
    "https://92.push2his.eastmoney.com/api/qt/stock/kline/get",
    "https://94.push2his.eastmoney.com/api/qt/stock/kline/get",
    "https://97.push2his.eastmoney.com/api/qt/stock/kline/get",
    "https://push2his.eastmoney.com/api/qt/stock/kline/get",
)
_HEADERS = {"Referer": "https://quote.eastmoney.com/"}
_ADJUST = {"qfq": "1", "hfq": "2", "": "0"}


def _secid(code: str) -> str:
    c = code.strip().zfill(6)
    m = "1" if c.startswith("6") else "0"
    return f"{m}.{c}"


def _http_get(url: str, params: dict) -> requests.Response:
    """东财 his 偶发断连；优先 curl_cffi impersonate。"""
    try:
        from curl_cffi import requests as creq

        s = creq.Session(impersonate="chrome120")
        return s.get(url, params=params, headers=_HEADERS, timeout=30)
    except Exception:
        return requests.get(
            url,
            params=params,
            headers=_HEADERS,
            timeout=30,
            proxies={"http": None, "https": None},
        )


def fetch_kline(code: str, adjust: str = "qfq", days: int = 210) -> list[dict[str, Any]]:
    secid = _secid(code)
    fqt = _ADJUST.get(adjust, "1")
    end = datetime.now().strftime("%Y%m%d")
    beg = (datetime.now() - timedelta(days=max(days * 2, 400))).strftime("%Y%m%d")
    param_sets = [
        {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "klt": "101",
            "fqt": fqt,
            "lmt": str(days),
            "end": end,
        },
        {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "klt": "101",
            "fqt": fqt,
            "beg": beg,
            "end": end,
        },
    ]
    klines: list[str] = []
    last_err: Exception | None = None
    for params in param_sets:
        for host in _HIST_HOSTS:
            for attempt in range(2):
                try:
                    r = _http_get(host, params)
                    r.raise_for_status()
                    klines = (r.json().get("data") or {}).get("klines") or []
                    if klines:
                        break
                except Exception as e:
                    last_err = e
            if klines:
                break
        if klines:
            break
    if not klines:
        raise RuntimeError(f"日K拉取失败: {last_err}")

    records: list[dict[str, Any]] = []
    for line in klines[-days:]:
        parts = line.split(",")
        if len(parts) < 11:
            continue
        records.append(
            {
                "date": parts[0],
                "open": float(parts[1]),
                "close": float(parts[2]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "volume": float(parts[5]),
                "volume_money": float(parts[6]),
                "zf": float(parts[7]),
                "zdf": float(parts[8]),
                "zde": float(parts[9]),
                "hsl": float(parts[10]),
            }
        )
    return records


def cyq_summary(code: str, adjust: str = "qfq") -> dict[str, Any]:
    if py_mini_racer is None:
        return {"code": code, "error": "缺少 py_mini_racer，请 pip install py_mini_racer"}
    try:
        records = fetch_kline(code, adjust=adjust)
    except Exception as e:
        return {"code": code.zfill(6), "error": f"日K拉取失败: {e}"}
    if len(records) < 30:
        return {"code": code.zfill(6), "error": "K线不足，无法推演筹码"}

    js = py_mini_racer.MiniRacer()
    js.eval(_CYQ_JS)
    idx = len(records) - 1
    m = js.call("CYQCalculator", idx, records)
    row = records[idx]
    benefit = float(m["benefitPart"])
    avg_cost = float(m["avgCost"])
    p70 = m["percentChips"]["70"]
    p90 = m["percentChips"]["90"]

    return {
        "code": code.zfill(6),
        "date": row["date"],
        "close": row["close"],
        "profit_ratio_pct": round(benefit * 100, 2),
        "avg_cost": avg_cost,
        "cost_70_low": float(p70["priceRange"][0]),
        "cost_70_high": float(p70["priceRange"][1]),
        "conc_70": round(float(p70["concentration"]), 4),
        "cost_90_low": float(p90["priceRange"][0]),
        "cost_90_high": float(p90["priceRange"][1]),
        "conc_90": round(float(p90["concentration"]), 4),
        "adjust": adjust or "qfq",
        "source": "eastmoney_cyq_calc",
        "note": "东财CYQ推演汇总；与App可能有复权/窗口细微差异",
    }


def fmt_summary(row: dict[str, Any]) -> str:
    if row.get("error"):
        return f"{row.get('code', '')}: {row['error']}"
    return (
        f"获利{row['profit_ratio_pct']:.2f}% · 均价{row['avg_cost']:.2f} · "
        f"90%[{row['cost_90_low']:.2f}-{row['cost_90_high']:.2f}]集{row['conc_90']:.3f} · "
        f"70%[{row['cost_70_low']:.2f}-{row['cost_70_high']:.2f}]集{row['conc_70']:.3f}"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="筹码分布汇总指标（CYQ）")
    p.add_argument("codes", nargs="+", help="A股代码")
    p.add_argument("--adjust", default="qfq", choices=["qfq", "hfq", ""], help="复权")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    rows = [cyq_summary(c, adjust=args.adjust) for c in args.codes]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for row in rows:
        code = row.get("code", "")
        if row.get("error"):
            print(f"{code}: {row['error']}")
        else:
            print(f"{code} {row['date']} 收{row['close']:.2f} | {fmt_summary(row)}")


if __name__ == "__main__":
    main()
