#!/usr/bin/env python3
"""把盘前/收盘 md 转成飞书可读纯文本并推送（自定义机器人 Webhook）。

用法:
  python3 scheduler/feishu_send.py <WEBHOOK_URL> <md路径> [卡片标题]

设计要点:
  - 仓库 md 可继续用 Markdown；飞书推送前去掉 ** / ## / 表格竖线等标记
  - 使用 interactive 卡片 + plain_text（不依赖 lark_md，避免星号原样显示）
  - 请求体约 20KB 上限；超长截断，脚注附 GitHub blob 完整 URL（默认 main）
  - 链接：REPO_WEB_BASE / GITHUB_REPO → git remote origin → 绝对路径兜底
  - origin 若为 https://x-access-token:…@github.com/… 会剥掉凭证，只留公开 blob URL
  - 分支：默认 main（定时任务先 merge_to_main）；仅 REPO_BRANCH 可显式覆盖
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

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


def _run_git(args: list[str], cwd: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return (r.stdout or "").strip() or None


def _repo_root(start: Path) -> Path | None:
    p = start.resolve()
    if p.is_file():
        p = p.parent
    out = _run_git(["rev-parse", "--show-toplevel"], p)
    return Path(out) if out else None


def _rel_in_repo(md_path: Path, root: Path | None) -> str:
    resolved = md_path.resolve()
    if root is not None:
        try:
            return resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            pass
    s = md_path.as_posix()
    if s.startswith("./"):
        s = s[2:]
    return s.lstrip("/")


def _strip_url_userinfo(url: str) -> str:
    """去掉 https://user:token@host/... 中的凭证，避免飞书脚注泄露 token。"""
    return re.sub(r"^(https?://)[^/@]+@", r"\1", url.strip())


def _https_repo_base(root: Path | None) -> str | None:
    """返回 https://github.com/owner/repo（无尾斜杠、无凭证）。"""
    env_base = (os.environ.get("REPO_WEB_BASE") or "").strip().rstrip("/")
    if env_base.startswith("http://") or env_base.startswith("https://"):
        return _strip_url_userinfo(env_base).rstrip("/")

    env_repo = (os.environ.get("GITHUB_REPO") or "").strip()
    if re.fullmatch(r"[^/\s]+/[^/\s]+", env_repo):
        return f"https://github.com/{env_repo}"

    if root is None:
        return None
    remote = _run_git(["remote", "get-url", "origin"], root)
    if not remote:
        return None

    remote = remote.strip()
    m = re.match(r"git@([^:]+):(.+?)(?:\.git)?$", remote)
    if m:
        host, path = m.group(1), m.group(2).strip("/")
        if "github" in host:
            return f"https://github.com/{path}"
        return f"https://{host}/{path}"

    # Cloud Agent 常见：https://x-access-token:ghs_…@github.com/owner/repo.git
    remote = _strip_url_userinfo(remote)
    m = re.match(r"https?://([^/]+)/(.+?)(?:\.git)?$", remote)
    if m:
        host, path = m.group(1), m.group(2).strip("/")
        if "github" in host:
            return f"https://github.com/{path}"
        return f"https://{host}/{path}"

    return None


def _current_branch(root: Path | None) -> str:
    """当前检出分支（供调试）；飞书链接请用 _feishu_blob_branch。"""
    env_b = (os.environ.get("REPO_BRANCH") or os.environ.get("GIT_BRANCH") or "").strip()
    if env_b:
        return env_b

    if root is None:
        return "main"

    # 1) 当前检出分支
    head = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], root)
    if head and head != "HEAD":
        return head

    # 2) 上游跟踪分支（push -u 之后）
    upstream = _run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], root)
    if upstream:
        if upstream.startswith("refs/remotes/"):
            upstream = upstream[len("refs/remotes/") :]
        if upstream.startswith("origin/"):
            upstream = upstream[len("origin/") :]
        if upstream and upstream != "HEAD":
            return upstream

    # 3) status 短格式：## cursor/a-xxx...origin/cursor/a-xxx
    sb = _run_git(["status", "-sb"], root)
    if sb:
        first = sb.splitlines()[0]
        m = re.match(r"^##\s+(\S+?)(?:\.\.\.|$)", first)
        if m and m.group(1) not in ("HEAD", "No"):
            return m.group(1)

    return "main"


def _feishu_blob_branch(root: Path | None) -> str:
    """飞书全文链接用的分支：默认 main，避免出现 cursor/xxxx。

    定时任务应先跑 merge_to_main.sh。仅当显式设置 REPO_BRANCH 时覆盖。
    """
    env_b = (os.environ.get("REPO_BRANCH") or "").strip()
    if env_b:
        return env_b
    return "main"


def full_repo_file_url(md_path: Path) -> str:
    """截断脚注用的全文链接：main（默认）上的 GitHub blob 完整 URL。"""
    root = _repo_root(md_path)
    rel = _rel_in_repo(md_path, root)
    base = _https_repo_base(root)
    if base:
        branch = _feishu_blob_branch(root)
        branch_enc = quote(branch, safe="")
        return f"{base}/blob/{branch_enc}/{rel}"
    return md_path.resolve().as_posix()


def truncate_for_feishu(body_text: str, md_path: Path) -> tuple[str, str]:
    url = full_repo_file_url(md_path)
    footer = f"\n\n…（已截断，全文见：{url}）"
    if len(body_text) <= MAX_CHARS - len(footer):
        return body_text, url
    keep = MAX_CHARS - len(footer)
    if keep < 200:
        keep = max(MAX_CHARS - len(footer), 0)
    return body_text[:keep] + footer, url


def send(webhook: str, md_path: Path, title: str | None = None) -> str:
    raw = md_path.read_text(encoding="utf-8")
    body_text = md_for_feishu(raw)
    full_url = full_repo_file_url(md_path)
    if len(body_text) > MAX_CHARS:
        body_text, full_url = truncate_for_feishu(body_text, md_path)
        print(f"[feishu_send] 正文已截断，全文链接: {full_url}", file=sys.stderr)
    else:
        print(f"[feishu_send] 全文未截断；仓库链接(备查): {full_url}", file=sys.stderr)

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
