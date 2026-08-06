#!/usr/bin/env python3
"""把盘前 md 转成飞书可读纯文本并推送（自定义机器人 Webhook）。

用法:
  python3 scheduler/feishu_send.py <WEBHOOK_URL> <md路径> [卡片标题]

设计要点:
  - 仓库 md 可继续用 Markdown；飞书推送前去掉 ** / ## / 表格竖线等标记
  - 使用 interactive 卡片 + plain_text（不依赖 lark_md，避免星号原样显示）
  - 请求体约 20KB 上限；超长截断并注明全文在仓库
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

MAX_CHARS = 5500


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_sep(line: str) -> bool:
    s = line.strip()
    if "|" not in s:
        return False
    core = s.strip("|").replace(":", "").replace("-", "").replace("|", "").replace(" ", "")
    return core == "" and "-" in s


def _strip_md_inline(s: str) -> str:
    """去掉行内 Markdown 标记，只留可读文字。"""
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)  # [文字](url) → 文字
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"__([^_]+)__", r"\1", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", s)
    s = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"\1", s)
    s = s.replace("**", "").replace("__", "")
    return s.strip()


def md_for_feishu(md: str) -> str:
    """Markdown → 飞书纯文本：无 ** / ##，表格改成条目。"""
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""

        if "|" in line and _is_sep(nxt):
            headers = [_strip_md_inline(h) for h in _cells(line)]
            i += 2
            while i < len(lines) and "|" in lines[i] and not lines[i].lstrip().startswith("#"):
                if _is_sep(lines[i]):
                    i += 1
                    continue
                cols = [_strip_md_inline(c) for c in _cells(lines[i])]
                if cols and headers:
                    title = cols[0] or "(空)"
                    rest = []
                    for h, c in zip(headers[1:], cols[1:]):
                        if c:
                            rest.append(f"{h} {c}")
                    out.append(f"· {title}" + ("｜" + "；".join(rest) if rest else ""))
                i += 1
            out.append("")
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            title = _strip_md_inline(m.group(2))
            out.append(f"【{title}】")
            out.append("")
            i += 1
            continue

        if re.match(r"^\s*-{3,}\s*$", line):
            i += 1
            continue

        # 列表：- / * / 数字.
        lm = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", line)
        if lm:
            out.append(f"{lm.group(1)}· {_strip_md_inline(lm.group(3))}")
            i += 1
            continue

        out.append(_strip_md_inline(line) if line.strip() else "")
        i += 1

    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def send(webhook: str, md_path: Path, title: str | None = None) -> str:
    raw = md_path.read_text(encoding="utf-8")
    body_text = md_for_feishu(raw)
    if len(body_text) > MAX_CHARS:
        body_text = (
            body_text[:MAX_CHARS]
            + f"\n\n…（已截断，全文见仓库 {md_path.as_posix()}）"
        )

    card_title = title or md_path.stem
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "template": "blue",
                "title": {"tag": "plain_text", "content": card_title[:50]},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "plain_text", "content": body_text},
                }
            ],
        },
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"飞书 HTTP {e.code}: {err}") from e


def main() -> None:
    if len(sys.argv) < 3:
        print(
            "用法: python3 scheduler/feishu_send.py <WEBHOOK_URL> <md路径> [卡片标题]",
            file=sys.stderr,
        )
        raise SystemExit(2)
    webhook = sys.argv[1].strip()
    path = Path(sys.argv[2])
    title = sys.argv[3] if len(sys.argv) > 3 else None
    if not path.is_file():
        raise SystemExit(f"找不到文件: {path}")
    print(send(webhook, path, title))


if __name__ == "__main__":
    main()
