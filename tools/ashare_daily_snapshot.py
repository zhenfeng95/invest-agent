#!/usr/bin/env python3
"""从 A 股收盘日报摘录评分快照 → data/public/ashare-daily-snapshot.csv。

供个人站 / 其它项目用 ECharts 画柱状图：x=date，y=score；tooltip 用其余列。
只读 output/daily/ashare-close-YYYY-MM-DD.md；缺字段留空，不编造。

用法：
  python3 tools/ashare_daily_snapshot.py
  python3 tools/ashare_daily_snapshot.py --check
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = ROOT / "output" / "daily"
DEFAULT_OUT = ROOT / "data" / "public" / "ashare-daily-snapshot.csv"

FIELDS = [
    "date",
    "score",
    "confidence",
    "market_state",
    "strategy",
    "attack_ok",
    "attack_met",
    "attack_note",
    "defend_ok",
    "defend_met",
    "defend_note",
    "account_focus",
    "suggested_position",
    "position_low",
    "position_high",
    "operation_hint",
]

_MD_DATE = re.compile(r"ashare-close-(\d{4}-\d{2}-\d{2})\.md$")
_BOLD = re.compile(r"\*{1,2}")
_WS = re.compile(r"[ \t]+")

_SCORE = re.compile(
    r"市场评分[：:]\s*\**\s*(\d{1,3})\s*/\s*100",
    re.MULTILINE,
)
_SCORE_FALLBACK = re.compile(
    r"综合评分\s*\**\s*(\d{1,3})\s*/\s*100",
)
_CONF = re.compile(
    r"市场评分[：:].{0,40}?置信度[：:]\s*\**\s*([高中低])",
    re.DOTALL,
)
_STATE = re.compile(
    r"当前状态[：:]\s*\**\s*([^\n｜|]+)",
)
_STRATEGY = re.compile(
    r"对应策略[：:]\s*\**\s*(防守|轻仓试错|积极参与|进攻)",
)
_ATTACK = re.compile(
    r"进攻四条件[：:]\s*\**\s*(是|否)\s*[（(]\s*(\d)\s*/\s*4\s*[）)]\s*[—\-–]?\s*(.*)",
)
_DEFEND = re.compile(
    r"防守四条件[：:]\s*\**\s*(是|否)\s*[（(]\s*(\d)\s*/\s*4\s*[）)]\s*[—\-–]?\s*(.*)",
)
_ACCOUNT = re.compile(
    r"账户重心[：:]\s*(.+)",
)
_POSITION = re.compile(
    r"建议总仓\s*\*{0,2}\s*(?:约|[：:])\s*\*{0,2}\s*(?:约\s*)?(.+)",
)
_HINT = re.compile(
    r"操作提示[：:]\s*(.+)",
)
_RANGE = re.compile(
    r"(\d{1,3})\s*[%％]?\s*[–\-—~至到]\s*(\d{1,3})\s*[%％]",
)
_LEQ = re.compile(r"[≤<]\s*(\d{1,3})\s*[%％]")
_SINGLE = re.compile(r"(\d{1,3})\s*[%％]")


def _clean(text: str, max_len: int = 240) -> str:
    text = text.replace("\u3000", " ")
    text = _BOLD.sub("", text)
    text = text.replace("`", "")
    text = _WS.sub(" ", text).strip(" \t\r\n-—–；;，,")
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def _first(pattern: re.Pattern[str], text: str, group: int = 1) -> str:
    m = pattern.search(text)
    return _clean(m.group(group)) if m else ""


def _parse_position(snippet: str) -> tuple[str, str, str]:
    snippet = re.split(r"[（(]依据", snippet, maxsplit=1)[0]
    raw = _clean(snippet, max_len=80)
    if not raw:
        return "", "", ""
    lo, hi = "", ""
    m = _RANGE.search(raw)
    if m:
        lo, hi = m.group(1), m.group(2)
    else:
        m = _LEQ.search(raw)
        if m:
            hi = m.group(1)
        else:
            m = _SINGLE.search(raw)
            if m:
                lo = hi = m.group(1)
    if lo and hi and lo == hi:
        compact = f"{lo}%"
    elif lo and hi:
        compact = f"{lo}–{hi}%"
        head = re.match(r"^(\d{1,3})\s*[%％](?![–\-—~至到])", raw)
        if head:
            compact = f"{head.group(1)}%"
    elif hi:
        compact = f"≤{hi}%"
    else:
        compact = raw
    # 短标签优先；长句只在抽不出数字时保留
    label = compact if compact else raw
    return label, lo, hi


def parse_daily(path: Path) -> dict[str, str] | None:
    m = _MD_DATE.search(path.name)
    if not m:
        return None
    text = path.read_text(encoding="utf-8")
    score_m = _SCORE.search(text) or _SCORE_FALLBACK.search(text)
    attack_m = _ATTACK.search(text)
    defend_m = _DEFEND.search(text)
    pos_snippet = ""
    for pm in _POSITION.finditer(text):
        if text[max(0, pm.start() - 2) : pm.start()] == "环境":
            continue
        pos_snippet = pm.group(1)
        break
    pos_label, pos_lo, pos_hi = _parse_position(pos_snippet)
    account = _first(_ACCOUNT, text)
    if account:
        account = _clean(re.split(r"账户重心[：:]", account)[-1])

    attack_ok = ""
    attack_met = ""
    attack_note = ""
    if attack_m:
        attack_ok = "true" if attack_m.group(1) == "是" else "false"
        attack_met = attack_m.group(2)
        attack_note = _clean(attack_m.group(3), max_len=160)

    defend_ok = ""
    defend_met = ""
    defend_note = ""
    if defend_m:
        defend_ok = "true" if defend_m.group(1) == "是" else "false"
        defend_met = defend_m.group(2)
        defend_note = _clean(defend_m.group(3), max_len=160)

    return {
        "date": m.group(1),
        "score": score_m.group(1) if score_m else "",
        "confidence": _first(_CONF, text),
        "market_state": _first(_STATE, text),
        "strategy": _first(_STRATEGY, text),
        "attack_ok": attack_ok,
        "attack_met": attack_met,
        "attack_note": attack_note,
        "defend_ok": defend_ok,
        "defend_met": defend_met,
        "defend_note": defend_note,
        "account_focus": account,
        "suggested_position": pos_label,
        "position_low": pos_lo,
        "position_high": pos_hi,
        "operation_hint": _first(_HINT, text),
    }


def collect_rows(daily_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(daily_dir.glob("ashare-close-*.md")):
        row = parse_daily(path)
        if row:
            rows.append(row)
    rows.sort(key=lambda r: r["date"])
    return rows


def write_csv(rows: list[dict[str, str]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _print_check(rows: list[dict[str, str]]) -> int:
    missing_score = [r["date"] for r in rows if not r["score"]]
    missing_pos = [r["date"] for r in rows if not r["suggested_position"]]
    missing_attack = [r["date"] for r in rows if not r["attack_ok"]]
    missing_defend = [r["date"] for r in rows if not r["defend_ok"]]
    print(f"rows={len(rows)}")
    print(f"missing_score={missing_score or '[]'}")
    print(f"missing_position={missing_pos or '[]'}")
    print(f"missing_attack(pre-§0 ok)={missing_attack or '[]'}")
    print(f"missing_defend(pre-§0 ok)={missing_defend or '[]'}")
    return 1 if missing_score else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="摘录 A 股收盘日报评分快照 CSV")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--daily-dir", type=Path, default=DAILY_DIR)
    parser.add_argument("--check", action="store_true", help="只打印覆盖情况，不写文件")
    args = parser.parse_args()

    if not args.daily_dir.is_dir():
        print(f"找不到日报目录: {args.daily_dir}", file=sys.stderr)
        return 1

    rows = collect_rows(args.daily_dir)
    if args.check:
        return _print_check(rows)

    write_csv(rows, args.out)
    print(f"wrote {args.out} rows={len(rows)}")
    return _print_check(rows)


if __name__ == "__main__":
    raise SystemExit(main())
