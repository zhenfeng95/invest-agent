#!/usr/bin/env python3
"""四选一买点检测（my-soul 量能口径；趋势线为自动近似）。

1. 放量突破 MA5
2. 放量突破下降趋势线（近端两段下降波峰连线）
3. 缩量回踩 MA5
4. 缩量回踩上升趋势线（近端两段上升波谷连线）

量能：MA(V,5)=评估日前5日均量（不含当日）；放量>1.2；缩量<0.8；中间带不算。
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _vol_metrics(hist: pd.DataFrame) -> tuple[float, float, float] | None:
    if len(hist) < 6:
        return None
    v = float(hist["volume"].iloc[-1])
    ma = float(hist["volume"].iloc[-6:-1].mean())
    if ma <= 0:
        return None
    return v, ma, v / ma


def _ma5_series(close: pd.Series) -> pd.Series:
    return close.rolling(5, min_periods=5).mean()


def _local_extrema(series: pd.Series, order: int = 2) -> tuple[list[int], list[int]]:
    vals = series.to_numpy(dtype=float)
    n = len(vals)
    highs: list[int] = []
    lows: list[int] = []
    for i in range(order, n - order):
        window = vals[i - order : i + order + 1]
        if vals[i] >= window.max() and vals[i] > vals[i - 1] and vals[i] > vals[i + 1]:
            highs.append(i)
        if vals[i] <= window.min() and vals[i] < vals[i - 1] and vals[i] < vals[i + 1]:
            lows.append(i)
    return highs, lows


def _line_value(i1: int, y1: float, i2: int, y2: float, i: int) -> float:
    if i2 == i1:
        return y2
    return y1 + (y2 - y1) * (i - i1) / (i2 - i1)


def detect_buy_setups(
    hist: pd.DataFrame,
    *,
    touch_pct: float = 2.0,
    breakout_max_ext_pct: float = 3.0,
) -> dict[str, Any] | None:
    """检测当日是否命中四选一；未命中返回 None。"""
    if hist is None or len(hist) < 20:
        return None
    hist = hist.sort_values("date").reset_index(drop=True)
    vm = _vol_metrics(hist)
    if vm is None:
        return None
    v, ma_v5, vr = vm
    is_fang = vr > 1.2
    is_suo = vr < 0.8
    if not is_fang and not is_suo:
        return None

    close = hist["close"].astype(float)
    if "high" in hist.columns:
        high = hist["high"].astype(float)
    else:
        high = close
    if "low" in hist.columns:
        low = hist["low"].astype(float)
    else:
        low = close

    ma5 = _ma5_series(close)
    if pd.isna(ma5.iloc[-1]) or pd.isna(ma5.iloc[-2]):
        return None

    c0 = float(close.iloc[-1])
    c1 = float(close.iloc[-2])
    m0 = float(ma5.iloc[-1])
    m1 = float(ma5.iloc[-2])
    ext = (c0 / m0 - 1.0) * 100.0

    signals: list[str] = []

    # 1) 放量突破 MA5（限制延伸，降低追加速）
    if is_fang and c1 <= m1 and c0 > m0 and ext <= breakout_max_ext_pct:
        signals.append("放量突破MA5")

    # 3) 缩量回踩 MA5
    ma5_up = float(ma5.iloc[-1]) >= float(ma5.iloc[-5])
    near = abs(c0 / m0 - 1.0) * 100.0 <= touch_pct or float(low.iloc[-1]) <= m0 * (
        1 + touch_pct / 100.0
    )
    if is_suo and ma5_up and near and c0 >= m0 * 0.985:
        signals.append("缩量回踩MA5")

    highs_i, lows_i = _local_extrema(high, order=2)

    # 2) 放量突破下降趋势线
    if is_fang and len(highs_i) >= 2:
        i2, i1 = highs_i[-1], highs_i[-2]
        y2, y1 = float(high.iloc[i2]), float(high.iloc[i1])
        if y2 < y1 and i2 > i1:
            line0 = _line_value(i1, y1, i2, y2, len(hist) - 1)
            line1 = _line_value(i1, y1, i2, y2, len(hist) - 2)
            if c1 <= line1 and c0 > line0 and ext <= breakout_max_ext_pct + 2:
                signals.append("放量突破下降趋势线")

    # 4) 缩量回踩上升趋势线
    if is_suo and len(lows_i) >= 2:
        i2, i1 = lows_i[-1], lows_i[-2]
        y2, y1 = float(low.iloc[i2]), float(low.iloc[i1])
        if y2 > y1 and i2 > i1:
            line0 = _line_value(i1, y1, i2, y2, len(hist) - 1)
            dist = abs(c0 / line0 - 1.0) * 100.0 if line0 > 0 else 999.0
            touched = float(low.iloc[-1]) <= line0 * (1 + touch_pct / 100.0)
            if c0 >= line0 * 0.985 and (dist <= touch_pct or touched):
                signals.append("缩量回踩趋势线")

    if not signals:
        return None

    return {
        "signals": signals,
        "signal": "+".join(signals),
        "v": int(v),
        "ma_v5_ex": int(round(ma_v5)),
        "vr_ex": round(vr, 3),
        "ma5": round(m0, 4),
        "ext_ma5_pct": round(ext, 2),
        "vol_side": "放量" if is_fang else "缩量",
    }
