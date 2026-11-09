#!/usr/bin/env python3
"""Public-web scanner for the webnovel-radar skill.

Reads references from scripts/sources.json, fetches public pages, extracts
candidate headlines/links/dates, and prints JSON to stdout. It never writes
report files or local state.

Usage:
    python scripts/scan.py --list
    python scripts/scan.py --all --since 7d --max-total 150
    python scripts/scan.py --source nppa_notice --source write_qq
    python scripts/scan.py --category 监管政策 --since 30d
    python scripts/scan.py --source fanqie_search --since 7d
    python scripts/scan.py --all --include-optional --proxy http://127.0.0.1:7897
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.dont_write_bytecode = True

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_PATH = os.path.join(SCRIPT_DIR, "sources.json")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
JINA_PREFIX = "https://r.jina.ai/"
DDG_URL = "https://lite.duckduckgo.com/lite/"

NAV_WORDS = {
    "首页", "登录", "注册", "更多", "下一页", "上一页", "返回", "下载",
    "客户端", "帮助", "关于我们", "联系我们", "网站地图", "设为首页",
    "加入收藏", "APP下载", "English", "简/繁", "无障碍", "退出",
    "查看详情", "阅读全文", "点击进入", "进入专区", "立即下载",
}

POLICY_HINTS = [
    "通知", "公告", "规则", "办法", "规定", "规划", "意见", "决定", "政策",
    "签约", "合同", "分成", "稿费", "全勤", "保底", "买断", "审核", "处罚",
    "违规", "下架", "封禁", "抄袭", "版权", "授权", "改编", "扶持", "征文",
    "福利", "AI", "人工智能", "出海", "治理", "规范", "备案", "出版",
]

SECTION_WORDS = {
    "通知公示", "通知公告", "政策解读", "要闻信息", "许可事项", "结果公示",
    "法定主动公开内容", "视频新闻", "业务动态", "地方工作", "版权信息",
    "作家福利", "关于我们", "联系方式", "帮助中心", "常见问题", "网站地图",
}

SPAM_PHRASES = [
    "欢迎点击", "更多精彩", "关注我们", "官方账号", "扫描二维码", "点击查看",
    "下载客户端", "登录后查看", "版权所有",
]

ANCHOR_RE = re.compile(
    r"<a\b[^>]*?href=[\"']([^\"']+)[\"'][^>]*>([\s\S]*?)</a>", re.IGNORECASE
)
MD_LINK_RE = re.compile(r"\[([^\]\n]{2,120})\]\((https?://[^)\s]+)\)")
TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", re.IGNORECASE)
META_DESC_RE = re.compile(
    r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']+)", re.IGNORECASE
)
TITLE_RE = re.compile(r"<title[^>]*>([\s\S]*?)</title>", re.IGNORECASE)
H1_RE = re.compile(r"<h1[^>]*>([\s\S]*?)</h1>", re.IGNORECASE)

FULL_DATE_RE = re.compile(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?")
COMPACT_DATE_RE = re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")
URL_DATE_RE = re.compile(r"/(20\d{2})/(\d{2})(\d{2})/")
SHORT_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[-/.月](\d{1,2})日?(?!\d)")

NOISE_TITLE_PATTERNS = [
    "完整版在线免费阅读",
    "全文阅读",
    "无弹窗",
    "最新章节",
    "免费阅读",
    "在线免费阅读",
]

DEFAULT_TIMEOUT = 18
JINA_TIMEOUT = 45
PER_DOMAIN_DELAY = 0.6

_last_request_by_domain: dict[str, float] = {}
_last_search_time = 0.0


class FetchError(RuntimeError):
    pass


def load_sources() -> list[dict]:
    with open(SOURCES_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("sources", [])


def detect_proxy(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        value = os.environ.get(key)
        if value:
            return value
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            ) as key:
                enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
                server, _ = winreg.QueryValueEx(key, "ProxyServer")
            if enabled and server:
                if not server.startswith(("http://", "https://")):
                    server = "http://" + server
                return server
        except Exception:
            pass
    return None


def build_opener(proxy: str | None) -> urllib.request.OpenerDirector:
    handlers: list[urllib.request.BaseHandler] = []
    if proxy:
        handlers.append(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    context = ssl.create_default_context()
    handlers.append(urllib.request.HTTPSHandler(context=context))
    return urllib.request.build_opener(*handlers)


def polite_wait(url: str) -> None:
    domain = urllib.parse.urlparse(url).netloc
    last = _last_request_by_domain.get(domain)
    if last is not None:
        elapsed = time.monotonic() - last
        if elapsed < PER_DOMAIN_DELAY:
            time.sleep(PER_DOMAIN_DELAY - elapsed)
    _last_request_by_domain[domain] = time.monotonic()


def search_wait() -> None:
    global _last_search_time
    elapsed = time.monotonic() - _last_search_time
    if elapsed < 3.5:
        time.sleep(3.5 - elapsed)
    _last_search_time = time.monotonic()


def decode_bytes(data: bytes, charset: str | None) -> str:
    candidates: list[str] = []
    if charset:
        candidates.append(charset)
    meta = re.search(rb"charset=[\"']?([\w-]+)", data[:4000], re.IGNORECASE)
    if meta:
        candidates.append(meta.group(1).decode("ascii", "ignore"))
    candidates.extend(["utf-8", "gb18030", "gbk"])
    seen: set[str] = set()
    for encoding in candidates:
        encoding = encoding.lower()
        if not encoding or encoding in seen:
            continue
        seen.add(encoding)
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", "replace")


def fetch_text(
    url: str,
    proxy: str | None,
    timeout: int,
    use_jina: bool = False,
    minimal_headers: bool = False,
) -> tuple[int, str]:
    target = JINA_PREFIX + url if use_jina else url
    polite_wait(target)
    if minimal_headers:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    else:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        }
    request = urllib.request.Request(target, headers=headers)
    if use_jina:
        request.add_header("X-Return-Format", "markdown")
    try:
        with build_opener(proxy).open(request, timeout=timeout) as response:
            data = response.read()
            charset = response.headers.get_content_charset()
            text = decode_bytes(data, charset)
            if response.status >= 400:
                raise FetchError(f"HTTP {response.status}")
            return response.status, text
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code}") from exc
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller
        raise FetchError(str(exc)) from exc


def strip_tags(value: str) -> str:
    value = SCRIPT_RE.sub(" ", value)
    value = TAG_RE.sub(" ", value)
    value = html_lib.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_title(value: str) -> str:
    value = strip_tags(value)
    value = re.sub(r"^[\[\(【]\s*\d{1,2}[-/.]\d{1,2}\s*[\]\)】]\s*", "", value)
    return value.strip(" \t\r\n-|·•")


def is_nav(title: str) -> bool:
    if len(title) < 4 or len(title) > 140:
        return True
    compact = re.sub(r"\s+", "", title)
    if compact in NAV_WORDS or compact in SECTION_WORDS:
        return True
    if len(compact) <= 3:
        return True
    if re.fullmatch(r"[\d\s:：.\-/]+", compact):
        return True
    if any(phrase in title for phrase in SPAM_PHRASES):
        return True
    if any(phrase in title for phrase in NOISE_TITLE_PATTERNS):
        return True
    return False


def make_date(year: int, month: int, day: int) -> str | None:
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    try:
        value = datetime(year, month, day).date()
    except ValueError:
        return None
    if value > datetime.now().date() + timedelta(days=1):
        return None
    return value.isoformat()


def parse_date(text: str, today: datetime | None = None) -> str | None:
    today = today or datetime.now()
    for pattern in (FULL_DATE_RE, COMPACT_DATE_RE, URL_DATE_RE):
        match = pattern.search(text)
        if match:
            year, month, day = (int(part) for part in match.groups())
            value = make_date(year, month, day)
            if value:
                return value
    match = SHORT_DATE_RE.search(text)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        year = today.year
        if month > today.month + 1:
            year -= 1
        return make_date(year, month, day)
    return None


def latest_date(text: str, today: datetime | None = None) -> str | None:
    today = today or datetime.now()
    dates: list[str] = []
    for pattern in (FULL_DATE_RE, COMPACT_DATE_RE):
        for match in pattern.finditer(text):
            year, month, day = (int(part) for part in match.groups())
            if 1 <= month <= 12 and 1 <= day <= 31:
                try:
                    dates.append(datetime(year, month, day).date().isoformat())
                except ValueError:
                    continue
    if dates:
        return max(dates)
    return parse_date(text, today)


def keyword_hit(
    title: str, keywords: list[str], exclude_phrases: list[str] | None = None
) -> bool:
    if exclude_phrases:
        for phrase in exclude_phrases:
            title = title.replace(phrase, " ")
    if not keywords:
        return True
    lowered = title.lower()
    for word in keywords:
        needle = word.lower()
        if re.fullmatch(r"[\x00-\x7f]+", needle):
            if re.search(
                rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", lowered
            ):
                return True
        elif needle in lowered:
            return True
    return False


def clean_url(base: str, href: str) -> str | None:
    href = href.strip()
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None
    absolute = urllib.parse.urljoin(base, href)
    parsed = urllib.parse.urlparse(absolute)
    if parsed.scheme not in ("http", "https"):
        return None
    # Drop tracking fragments and common tracking parameters.
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [
        (key, value)
        for key, value in query
        if not key.lower().startswith(("utm_", "spm", "from", "share"))
    ]
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query), fragment=""))


def enclosing_block(html: str, start: int, end: int) -> str:
    candidates: list[tuple[int, str]] = []
    for tag in ("li", "tr"):
        starts = list(re.finditer(rf"<{tag}\b", html[:start], re.IGNORECASE))
        if not starts:
            continue
        block_start = starts[-1].start()
        end_match = re.search(rf"</{tag}\s*>", html[end:], re.IGNORECASE)
        if end_match is None:
            continue
        block_end = end + end_match.end()
        if (start - block_start) < 2500 and (block_end - end) < 2500:
            candidates.append((block_end - block_start, html[block_start:block_end]))
    if candidates:
        return min(candidates, key=lambda item: item[0])[1]
    return html[max(0, start - 250) : min(len(html), end + 250)]


def extract_html_items(
    html: str,
    base_url: str,
    source: dict,
    since: str,
) -> list[dict]:
    accept_all = bool(source.get("accept_all"))
    keywords = source.get("keywords", [])
    items: list[dict] = []
    seen: set[str] = set()
    for match in ANCHOR_RE.finditer(html):
        href, raw_title = match.group(1), match.group(2)
        title = normalize_title(raw_title)
        if len(title) < 4:
            script_title = re.search(
                r"_docTitle\s*=\s*['\"]([^'\"]+)['\"]", match.group(0)
            )
            if script_title:
                title = normalize_title(script_title.group(1))
        if is_nav(title):
            continue
        if not accept_all and not keyword_hit(
            title, keywords, source.get("exclude_phrases")
        ):
            continue
        allow_js = bool(source.get("allow_js_links")) and href.strip().lower().startswith(
            "javascript:"
        )
        url = base_url if allow_js else clean_url(base_url, href)
        key = f"{url}#{title}" if allow_js else url
        if not url or key in seen:
            continue
        if any(pattern in url for pattern in source.get("block_url_patterns", [])):
            continue
        start, end = match.start(), match.end()
        context_html = enclosing_block(html, start, end)
        context = strip_tags(context_html)[:320]
        date = parse_date(f"{href} {context}")
        if date and date < since:
            continue
        if not date and accept_all and not keyword_hit(title, POLICY_HINTS):
            continue
        if not date and source.get("require_date"):
            continue
        seen.add(key)
        items.append(
            {
                "title": title,
                "url": url,
                "date": date,
                "confidence": "direct",
                "context": context,
            }
        )
    return items


def extract_markdown_items(
    markdown: str,
    base_url: str,
    source: dict,
    since: str,
) -> list[dict]:
    accept_all = bool(source.get("accept_all"))
    keywords = source.get("keywords", [])
    items: list[dict] = []
    seen: set[str] = set()
    lines = markdown.splitlines()
    for line in lines:
        for match in MD_LINK_RE.finditer(line):
            title = normalize_title(match.group(1))
            if is_nav(title):
                continue
            if not accept_all and not keyword_hit(
                title, keywords, source.get("exclude_phrases")
            ):
                continue
            url = clean_url(base_url, match.group(2))
            if not url or url in seen:
                continue
            if any(pattern in url for pattern in source.get("block_url_patterns", [])):
                continue
            date = parse_date(f"{match.group(2)} {line}")
            if date and date < since:
                continue
            if not date and accept_all and not keyword_hit(title, POLICY_HINTS):
                continue
            if not date and source.get("require_date"):
                continue
            seen.add(url)
            items.append(
                {
                    "title": title,
                    "url": url,
                    "date": date,
                    "confidence": "jina",
                    "context": line.strip()[:260],
                }
            )
    return items


def page_item(
    text: str,
    url: str,
    source: dict,
    confidence: str,
    is_markdown: bool,
) -> dict:
    title = ""
    if is_markdown:
        match = re.search(r"^Title:\s*(.+)$", text, re.MULTILINE)
        if match:
            title = normalize_title(match.group(1))
    else:
        match = TITLE_RE.search(text) or H1_RE.search(text)
        if match:
            title = normalize_title(match.group(1))
    if is_nav(title) or len(title) < 4:
        title = source["name"]
    if len(title) <= 22 and re.search(
        r"作家专区|帮助中心|首页|作家福利|作品登载规则|签约作品福利", title
    ):
        title = source["name"]
    if len(title) > 60:
        title = source["name"]
    description = ""
    if not is_markdown:
        match = META_DESC_RE.search(text)
        if match:
            description = strip_tags(match.group(1))
    if not description:
        snippet = re.sub(r"^Title:.*$|^URL Source:.*$|^Markdown Content:.*$", "", text, flags=re.MULTILINE)
        description = re.sub(r"\s+", " ", snippet).strip()[:260]
    date = parse_date(text[:300])
    return {
        "title": title,
        "url": url,
        "date": date,
        "confidence": confidence,
        "context": description,
    }


def fetch_with_fallback(
    source: dict, proxy: str | None, timeout: int
) -> tuple[str, str]:
    """Return (status, text). status is 'direct' or 'jina'."""
    url = source["url"]
    access = source.get("access", "auto")
    if access == "jina":
        return "jina", fetch_text(url, proxy, JINA_TIMEOUT, use_jina=True)[1]
    status, text = fetch_text(url, proxy, timeout)
    if status == 200 and len(text) >= 300:
        return "direct", text
    raise FetchError(f"short response ({len(text)} bytes)")


def scan_url_source(
    source: dict, proxy: str | None, timeout: int, since: str
) -> tuple[str, list[dict], str | None]:
    url = source["url"]
    access = source.get("access", "auto")
    errors: list[str] = []
    direct_ok = False
    attempts: list[str] = []
    if access == "jina":
        attempts = ["jina"]
    else:
        attempts = ["direct"]
        if access == "auto":
            attempts.append("jina")

    for mode in attempts:
        try:
            if mode == "jina":
                _, text = fetch_text(url, proxy, JINA_TIMEOUT, use_jina=True)
                if "Warning: Target URL returned error" in text:
                    raise FetchError("Jina reported target error")
                is_markdown = True
            else:
                status, text = fetch_text(url, proxy, timeout)
                if status != 200:
                    raise FetchError(f"HTTP {status}")
                if len(text) < 300:
                    raise FetchError(f"short response ({len(text)} bytes)")
                direct_ok = True
                is_markdown = False

            if source.get("type") == "page":
                if len(text) < 200:
                    raise FetchError(f"short page ({len(text)} bytes)")
                item = page_item(text, url, source, mode, is_markdown)
                return mode, [item], None

            if is_markdown:
                items = extract_markdown_items(text, url, source, since)
            else:
                items = extract_html_items(text, url, source, since)

            if items:
                return mode, items[: int(source.get("max_items", 20))], None
            errors.append(f"{mode}: no items")
            if source.get("type") == "page":
                return mode, [page_item(text, url, source, mode, is_markdown)], None
        except FetchError as exc:
            errors.append(f"{mode}: {exc}")
            continue
    status = "empty" if direct_ok else "error"
    return status, [], "; ".join(errors) or "no items"


def decode_ddg_url(href: str) -> str:
    parsed = urllib.parse.urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com"):
        params = urllib.parse.parse_qs(parsed.query)
        if "uddg" in params and params["uddg"]:
            return params["uddg"][0]
    return href


def scan_search_source(
    source: dict, proxy: str | None, timeout: int, since: str
) -> tuple[str, list[dict], str | None]:
    query = source.get("query", "")
    if not query:
        return "error", [], "missing query"
    params = {"q": query, "kl": "cn-zh"}
    days = (datetime.now().date() - datetime.fromisoformat(since).date()).days
    if days <= 2:
        params["df"] = "d"
    elif days <= 8:
        params["df"] = "w"
    elif days <= 32:
        params["df"] = "m"
    url = DDG_URL + "?" + urllib.parse.urlencode(params)
    search_wait()
    text = ""
    last_error = ""
    for attempt in range(3):
        if attempt:
            time.sleep(4 * attempt)
        try:
            status, text = fetch_text(url, proxy, max(timeout, 30), minimal_headers=True)
            if status == 200 and "uddg=" in text:
                last_error = ""
                break
            last_error = f"HTTP {status}"
            if status not in (202, 429):
                break
        except FetchError as exc:
            last_error = str(exc)
    if last_error:
        return "error", [], f"search blocked: {last_error}"

    results: list[dict] = []
    seen: set[str] = set()
    keywords = source.get("keywords", [])
    for match in ANCHOR_RE.finditer(text):
        href = html_lib.unescape(match.group(1))
        if "uddg=" not in href:
            continue
        target = decode_ddg_url(href)
        parsed = urllib.parse.urlparse(target)
        if not target.startswith(("http://", "https://")):
            continue
        if parsed.netloc.endswith("duckduckgo.com"):
            continue
        title = normalize_title(match.group(2))
        if is_nav(title) or target in seen:
            continue
        if any(pattern in target for pattern in source.get("block_url_patterns", [])):
            continue
        start, end = match.start(), match.end()
        context = strip_tags(text[max(0, start - 300) : min(len(text), end + 300)])[:260]
        if keywords and not keyword_hit(
            f"{title} {context}", keywords, source.get("exclude_phrases")
        ):
            continue
        date = parse_date(f"{target} {context}")
        if date and date < since:
            continue
        seen.add(target)
        results.append(
            {
                "title": title,
                "url": target,
                "date": date,
                "confidence": "search",
                "context": context,
            }
        )
        if len(results) >= int(source.get("max_items", 15)):
            break
    if not results:
        return "empty", [], "no search results"
    return "search", results, None


def parse_since(value: str) -> str:
    value = value.strip().lower()
    match = re.fullmatch(r"(\d+)([dhw])", value)
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        delta = {
            "d": timedelta(days=amount),
            "h": timedelta(hours=amount),
            "w": timedelta(weeks=amount),
        }[unit]
        return (datetime.now() - delta).date().isoformat()
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "since must be like 24h, 7d, 4w, or YYYY-MM-DD"
        ) from exc


def select_sources(
    all_sources: list[dict],
    ids: list[str],
    categories: list[str],
    include_optional: bool,
) -> list[dict]:
    selected = all_sources
    if ids:
        wanted = {item.strip() for value in ids for item in value.split(",") if item.strip()}
        unknown = wanted - {source["id"] for source in all_sources}
        if unknown:
            raise SystemExit(f"Unknown source id(s): {', '.join(sorted(unknown))}")
        selected = [source for source in selected if source["id"] in wanted]
    if categories:
        wanted_categories = {
            item.strip() for value in categories for item in value.split(",") if item.strip()
        }
        selected = [
            source for source in selected if source.get("category") in wanted_categories
        ]
    if not include_optional:
        selected = [source for source in selected if not source.get("optional")]
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan public webnovel sources")
    parser.add_argument("--source", action="append", default=[], help="source id (repeatable/comma-separated)")
    parser.add_argument("--category", action="append", default=[], help="category filter")
    parser.add_argument("--all", action="store_true", help="scan all selected sources (default)")
    parser.add_argument("--since", default="7d", type=parse_since, help="24h, 7d, 4w, or YYYY-MM-DD")
    parser.add_argument("--max-total", type=int, default=150, help="max items in output")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="per-request timeout seconds")
    parser.add_argument("--proxy", default=None, help="HTTP proxy, e.g. http://127.0.0.1:7897")
    parser.add_argument("--include-optional", action="store_true", help="include optional/login-gated sources")
    parser.add_argument("--search-budget", type=int, default=1, help="max search sources per run (default 1)")
    parser.add_argument("--list", action="store_true", help="list configured sources and exit")
    parser.add_argument("--debug", action="store_true", help="include per-source errors in output")
    args = parser.parse_args()

    sources = load_sources()
    if args.list:
        for source in sources:
            flags = []
            if source.get("optional"):
                flags.append("optional")
            if source.get("access"):
                flags.append(source["access"])
            print(
                f"{source['id']}\t{source.get('category', '')}\t{source['name']}\t"
                f"{source.get('type', 'url')}\t{','.join(flags)}"
            )
        return 0

    selected = select_sources(
        sources, args.source, args.category, args.include_optional
    )
    if not selected:
        raise SystemExit("No sources selected")

    proxy = detect_proxy(args.proxy)
    started = datetime.now()
    results: list[dict] = []
    source_status: list[dict] = []
    search_used = 0

    for source in selected:
        source_type = source.get("type", "url")
        if source_type == "search":
            if search_used >= args.search_budget:
                mode, items, error = "skipped", [], "search budget reached"
            else:
                search_used += 1
                mode, items, error = scan_search_source(
                    source, proxy, args.timeout, args.since
                )
        else:
            mode, items, error = scan_url_source(
                source, proxy, args.timeout, args.since
            )
        for item in items:
            item["source_id"] = source["id"]
            item["source_name"] = source["name"]
            item["category"] = source.get("category", "")
        results.extend(items)
        source_status.append(
            {
                "id": source["id"],
                "name": source["name"],
                "category": source.get("category", ""),
                "type": source_type,
                "url": source.get("url") or source.get("query", ""),
                "status": mode,
                "item_count": len(items),
                "error": error,
            }
        )

    # Deduplicate by URL, preferring items with a date and direct confidence.
    confidence_rank = {"direct": 0, "jina": 1, "search": 2}
    unique: dict[str, dict] = {}
    for item in results:
        existing = unique.get(item["url"])
        if existing is None:
            unique[item["url"]] = item
            continue
        order = (
            confidence_rank.get(item.get("confidence"), 9),
            0 if item.get("date") else 1,
        )
        existing_order = (
            confidence_rank.get(existing.get("confidence"), 9),
            0 if existing.get("date") else 1,
        )
        if order < existing_order:
            unique[item["url"]] = item

    items = list(unique.values())
    items.sort(key=lambda item: (item.get("date") or "", item.get("title", "")), reverse=True)
    items = items[: max(0, args.max_total)]

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "started_at": started.astimezone().isoformat(timespec="seconds"),
        "since": args.since,
        "proxy": proxy or "",
        "source_count": len(selected),
        "item_count": len(items),
        "sources": source_status,
        "items": items,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
