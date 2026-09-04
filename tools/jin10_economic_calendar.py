#!/usr/bin/env python3
"""金十 MCP → data/public/economic-calendar.json（方案 2：无 LLM）。

直连 https://mcp.jin10.com/mcp，调用 list_calendar，落盘供个人站直链。
默认只写文件；加 --commit / --push 才动 git。

环境变量：
  JIN10_BEARER_TOKEN（必填）
  JIN10_MCP_SERVER_URL（可选，默认官方）
  JIN10_MCP_PROTOCOL_VERSION（可选）

用法：
  python3 tools/jin10_economic_calendar.py
  python3 tools/jin10_economic_calendar.py --commit --push
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "public" / "economic-calendar.json"
DEFAULT_SERVER = "https://mcp.jin10.com/mcp"
DEFAULT_PROTOCOL = "2025-11-25"
TZ = ZoneInfo("Asia/Shanghai")


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k, v = k.strip(), v.strip().strip("'").strip('"')
        if k and v and k not in os.environ:
            os.environ[k] = v


def _extract_sse_json(text: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    event_name = ""
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event_name, data_lines
        if not data_lines:
            return
        raw = "\n".join(data_lines)
        payloads.append({"event": event_name or "message", "data": json.loads(raw)})
        event_name = ""
        data_lines = []

    for line in text.splitlines():
        if line == "":
            flush()
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    flush()
    if not payloads:
        raise RuntimeError("未从 SSE 响应中解析到消息")
    return payloads


class Jin10McpClient:
    def __init__(self, server_url: str, token: str, protocol_version: str) -> None:
        self.server_url = server_url
        self.token = token
        self.protocol_version = protocol_version
        self.session_id: str | None = None
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _headers(self) -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def post_rpc(self, body: dict[str, Any], *, expect_response: bool = True) -> Any:
        data = json.dumps(body).encode("utf-8")
        req = Request(self.server_url, data=data, headers=self._headers(), method="POST")
        try:
            with urlopen(req, timeout=60) as resp:
                sid = resp.headers.get("mcp-session-id") or resp.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                if not expect_response:
                    return None
                text = resp.read().decode("utf-8")
                ctype = (resp.headers.get("content-type") or "").lower()
        except HTTPError as e:
            body_txt = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code}: {body_txt[:500]}") from e
        except URLError as e:
            raise RuntimeError(f"网络错误: {e}") from e

        if "text/event-stream" in ctype:
            events = _extract_sse_json(text)
            msg = next((ev for ev in events if ev.get("event") == "message"), None)
            if msg is None:
                raise RuntimeError("未收到 message 事件")
            rpc = msg["data"]
        else:
            rpc = json.loads(text)

        if isinstance(rpc, dict) and rpc.get("error"):
            err = rpc["error"]
            raise RuntimeError(f"JSON-RPC {err.get('code')}: {err.get('message')}")
        return rpc.get("result") if isinstance(rpc, dict) else rpc

    def connect(self) -> None:
        self.post_rpc(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": self.protocol_version,
                    "capabilities": {},
                    "clientInfo": {"name": "invest-agent-calendar", "version": "1.0.0"},
                },
            }
        )
        self.post_rpc(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            expect_response=False,
        )

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        result = self.post_rpc(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
        )
        if isinstance(result, dict) and result.get("isError"):
            raise RuntimeError(f"工具错误: {json.dumps(result, ensure_ascii=False)[:500]}")
        return result


def _pick_primary(result: Any) -> Any:
    if isinstance(result, dict) and "structuredContent" in result:
        return result["structuredContent"]
    if isinstance(result, dict) and isinstance(result.get("content"), list):
        for item in result["content"]:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text") or ""
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    continue
    return result


def _extract_events(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            items = payload["data"]
        elif isinstance(payload.get("data"), dict) and isinstance(payload["data"].get("items"), list):
            items = payload["data"]["items"]
        elif isinstance(payload.get("items"), list):
            items = payload["items"]
        else:
            raise RuntimeError(f"无法解析日历结构 keys={list(payload.keys())}")
    else:
        raise RuntimeError(f"意外日历类型: {type(payload).__name__}")

    events: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        events.append(
            {
                "pub_time": it.get("pub_time"),
                "star": it.get("star"),
                "title": it.get("title"),
                "previous": it.get("previous"),
                "consensus": it.get("consensus"),
                "actual": it.get("actual"),
                "revised": it.get("revised"),
                "affect_txt": it.get("affect_txt"),
            }
        )
    events.sort(key=lambda e: e.get("pub_time") or "")
    return events


def build_document(events: list[dict[str, Any]]) -> dict[str, Any]:
    now = datetime.now(TZ)
    return {
        "updated_at": now.isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai",
        "source": "jin10",
        "source_tool": "list_calendar",
        "coverage": "current_natural_week_mon_sun",
        "count": len(events),
        "events": events,
    }


def write_json(path: Path, doc: dict[str, Any]) -> bool:
    """写入 JSON；若内容相对旧文件仅 updated_at 变化也算变更（日历实际值常变）。返回是否有字节变化。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    new_text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    old_text = path.read_text(encoding="utf-8") if path.is_file() else None
    if old_text == new_text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def maybe_commit_push(path: Path, *, commit: bool, push: bool, count: int) -> None:
    if not commit and not push:
        return
    rel = path.relative_to(ROOT).as_posix()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", rel],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if not status:
        print(f"[jin10_calendar] git: {rel} 无变更，跳过 commit/push")
        return
    if not commit and push:
        print("[jin10_calendar] --push 需要同时 --commit", file=sys.stderr)
        sys.exit(2)
    _git("add", "--", rel)
    msg = f"chore: refresh economic calendar ({count} events)"
    _git("commit", "-m", msg)
    print(f"[jin10_calendar] committed: {msg}")
    if push:
        _git("push", "origin", "HEAD")
        print("[jin10_calendar] pushed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Jin10 economic calendar → public JSON")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="输出路径")
    parser.add_argument("--commit", action="store_true", help="有变更则 git commit")
    parser.add_argument("--push", action="store_true", help="commit 后 git push（需 --commit）")
    parser.add_argument("--dry-run", action="store_true", help="只拉数打印 count，不写文件")
    args = parser.parse_args()

    _load_dotenv(ROOT / ".env")
    token = os.environ.get("JIN10_BEARER_TOKEN", "").strip()
    if not token:
        print("缺少 JIN10_BEARER_TOKEN（环境变量或 .env）", file=sys.stderr)
        return 1

    server = os.environ.get("JIN10_MCP_SERVER_URL", DEFAULT_SERVER).strip() or DEFAULT_SERVER
    protocol = (
        os.environ.get("JIN10_MCP_PROTOCOL_VERSION", DEFAULT_PROTOCOL).strip() or DEFAULT_PROTOCOL
    )

    client = Jin10McpClient(server, token, protocol)
    client.connect()
    raw = _pick_primary(client.call_tool("list_calendar", {}))
    events = _extract_events(raw)
    doc = build_document(events)

    if args.dry_run:
        print(json.dumps({"count": doc["count"], "updated_at": doc["updated_at"]}, ensure_ascii=False))
        return 0

    out = args.out if args.out.is_absolute() else ROOT / args.out
    changed = write_json(out, doc)
    print(
        f"[jin10_calendar] wrote {out.relative_to(ROOT)} count={doc['count']} "
        f"updated_at={doc['updated_at']} changed={changed}"
    )
    maybe_commit_push(out, commit=args.commit, push=args.push, count=doc["count"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[jin10_calendar] ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
