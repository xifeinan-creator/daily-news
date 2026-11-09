#!/usr/bin/env python3
"""Push a Markdown report to ServerChan Turbo or ServerChan 3."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

MAX_BODY_BYTES = 28000
TIMEOUT_SECONDS = 20
FOOTER = "\n\n---\n> 本简报由 opencode + webnovel-radar 自动生成，内容以官方原文为准。"


def api_url(sendkey: str) -> str:
    explicit = os.environ.get("SERVERCHAN_API_URL", "").strip()
    if explicit:
        return explicit
    match = re.match(r"^sctp(\d+)t", sendkey)
    if match:
        return f"https://{match.group(1)}.push.ft07.com/send/{sendkey}.send"
    return f"https://sctapi.ftqq.com/{sendkey}.send"


def mask_endpoint(url: str) -> str:
    return re.sub(r"/(?:SCT|sctp)[^/]+\.send", "/<SENDKEY>.send", url)


def truncate_bytes(text: str, limit: int) -> str:
    data = text.encode("utf-8")
    if len(data) <= limit:
        return text
    data = data[:limit]
    while data:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            data = data[:-1]
    return ""


def default_title(report_path: str | None) -> str:
    if report_path:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", Path(report_path).name)
        if match:
            return f"网文雷达 · {match.group(1)}"
    return f"网文雷达 · {datetime.now().strftime('%Y-%m-%d')}"


def build_body(args: argparse.Namespace) -> str:
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    elif args.report:
        body = Path(args.report).read_text(encoding="utf-8")
        body += FOOTER
    else:
        raise SystemExit("either a report path or --body-file is required")

    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        note = "\n\n> 报告过长，已截断。完整版见服务器 reports 目录。"
        body = truncate_bytes(body, MAX_BODY_BYTES - len(note.encode("utf-8"))) + note
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description="Push a Markdown file to ServerChan")
    parser.add_argument("report", nargs="?", help="Markdown report path")
    parser.add_argument("--title", help="push title (max 32 chars)")
    parser.add_argument("--body-file", help="use this file as the push body")
    parser.add_argument("--dry-run", action="store_true", help="print request info without sending")
    args = parser.parse_args()

    sendkey = os.environ.get("SERVERCHAN_SENDKEY", "").strip()
    if not sendkey:
        print("SERVERCHAN_SENDKEY is not set", file=sys.stderr)
        return 2

    title = (args.title or default_title(args.report))[:32]
    body = build_body(args)
    endpoint = api_url(sendkey)

    if args.dry_run:
        print(f"endpoint: {mask_endpoint(endpoint)}")
        print(f"title: {title}")
        print(f"body bytes: {len(body.encode('utf-8'))}")
        print(f"body preview: {body.splitlines()[0] if body.splitlines() else ''}")
        return 0

    payload = urllib.parse.urlencode({"title": title, "desp": body}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "User-Agent": "daily-news/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"request failed: {exc.reason}", file=sys.stderr)
        return 1

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        print(f"unexpected response: {raw[:200]}", file=sys.stderr)
        return 1

    if result.get("code") == 0:
        print(f"push ok: {title}")
        return 0

    print(f"push failed: {raw[:300]}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
