"""Polite scraping helpers for any public website."""
from __future__ import annotations

import ipaddress
import socket
import time
from functools import lru_cache
from io import StringIO
from typing import Callable
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests
from bs4 import BeautifulSoup

UA = "BookScout/2.0 (learning project)"
MAX_BYTES = 5_000_000
BLOCK_HINTS = ("captcha", "robot check", "unusual traffic", "access denied")


class ScrapeError(Exception):
    """An error whose message is safe to show to the user."""


def check_url(url: str) -> None:
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ScrapeError("Enter a full address that starts with http:// or https://")
    try:
        infos = socket.getaddrinfo(parts.hostname, None)
    except socket.gaierror:
        raise ScrapeError("That address could not be found. Check the spelling.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ScrapeError("Private and local addresses are blocked.")


@lru_cache(maxsize=64)
def _robots(root: str) -> RobotFileParser | None:
    parser = RobotFileParser()
    try:
        resp = requests.get(root + "/robots.txt", headers={"User-Agent": UA}, timeout=8)
        if resp.status_code >= 400:
            return None  # no robots.txt: nothing is disallowed
        parser.parse(resp.text.splitlines())
        return parser
    except requests.RequestException:
        return None


def allowed_by_robots(url: str) -> bool:
    parts = urlparse(url)
    parser = _robots(f"{parts.scheme}://{parts.netloc}")
    return True if parser is None else parser.can_fetch(UA, url)


def fetch_html(url: str) -> str:
    for _ in range(4):  # follow up to 3 redirects, re-checking each hop
        check_url(url)
        try:
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=15, stream=True, allow_redirects=False)
        except requests.RequestException as exc:
            raise ScrapeError(f"Could not reach the site: {exc.__class__.__name__}.")
        if resp.is_redirect and resp.headers.get("Location"):
            url = urljoin(url, resp.headers["Location"])
            continue
        body = b""
        for chunk in resp.iter_content(65536):
            body += chunk
            if len(body) > MAX_BYTES:
                break
        text = body.decode(resp.encoding or "utf-8", errors="replace")
        host = urlparse(url).hostname
        if resp.status_code in (403, 429, 503) or any(h in text[:5000].lower() for h in BLOCK_HINTS):
            raise ScrapeError(
                f"{host} refused automated access (HTTP {resp.status_code}). This tool does not bypass blocks. "
                "Look for an official API or data export instead.")
        if resp.status_code >= 400:
            raise ScrapeError(f"The site returned HTTP {resp.status_code}.")
        return text
    raise ScrapeError("Too many redirects.")


def _soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def auto_extract(html: str, url: str) -> dict[str, pd.DataFrame]:
    soup = _soup(html)
    meta = [("Title", soup.title.get_text(strip=True) if soup.title else None)]
    for tag in soup.select("meta[name=description], meta[property^='og:']"):
        meta.append((tag.get("property") or tag.get("name"), tag.get("content")))
    links = {(urljoin(url, a["href"]), a.get_text(" ", strip=True)) for a in soup.select("a[href]")}
    try:
        tables = pd.read_html(StringIO(html))
    except ValueError:
        tables = []
    out = {
        "Metadata": pd.DataFrame(meta, columns=["Property", "Value"]).dropna(),
        "Headings": pd.DataFrame([(h.name.upper(), h.get_text(" ", strip=True)) for h in soup.select("h1, h2, h3")],
                                 columns=["Level", "Text"]),
        "Links": pd.DataFrame(sorted(links), columns=["URL", "Text"]),
        "Images": pd.DataFrame([(urljoin(url, i["src"]), i.get("alt", "")) for i in soup.select("img[src]")],
                               columns=["URL", "Alt text"]),
    }
    for n, t in enumerate(tables, start=1):
        out[f"Table {n}"] = t
    return {k: v for k, v in out.items() if not v.empty}


def parse_fields(spec: str) -> list[tuple[str, str, str | None]]:
    """Lines like `name = css selector` or `link = a.title@href`."""
    fields = []
    for line in spec.splitlines():
        if "=" not in line:
            continue
        name, selector = (s.strip() for s in line.split("=", 1))
        attr = None
        if "@" in selector:
            selector, attr = (s.strip() for s in selector.rsplit("@", 1))
        if name and selector:
            fields.append((name, selector, attr))
    return fields


def _value(el, attr, url):
    val = el.get(attr) if attr else el.get_text(" ", strip=True)
    return urljoin(url, val) if attr in ("href", "src") and val else val


def custom_extract(html: str, url: str, container: str, fields) -> pd.DataFrame:
    soup = _soup(html)
    if container:
        rows = []
        for root in soup.select(container):
            row = {}
            for name, sel, attr in fields:
                el = root.select_one(sel)
                row[name] = _value(el, attr, url) if el is not None else None
            rows.append(row)
        return pd.DataFrame(rows)
    return pd.DataFrame({n: pd.Series([_value(e, a, url) for e in soup.select(s)]) for n, s, a in fields})


def crawl(url, html, container, fields, next_selector="", max_pages=1, delay=1.0,
          on_progress: Callable[[int, int], None] | None = None) -> pd.DataFrame:
    frames, seen = [], set()
    for page in range(1, max_pages + 1):
        seen.add(url)
        frames.append(custom_extract(html, url, container, fields).assign(**{"Source page": url}))
        if on_progress:
            on_progress(page, max_pages)
        nxt = _soup(html).select_one(next_selector) if next_selector else None
        if page == max_pages or nxt is None or not nxt.get("href"):
            break
        url = urljoin(url, nxt["href"])
        if url in seen or not allowed_by_robots(url):
            break
        time.sleep(delay)
        html = fetch_html(url)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
