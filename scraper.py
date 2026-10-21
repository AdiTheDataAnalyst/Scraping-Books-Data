"""Scraping layer for books.toscrape.com: concurrent, retrying, and testable."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://books.toscrape.com/"
PAGE_URL = BASE_URL + "catalogue/page-{}.html"
MAX_PAGES = 50
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

Progress = Callable[[str, int, int], None]


def _soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:  # lxml not installed
        return BeautifulSoup(html, "html.parser")


def _number(text: str) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", text or "")
    return float(match.group()) if match else None


def make_session(workers: int = 8) -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.6, status_forcelist=(429, 500, 502, 503, 504))
    adapter = HTTPAdapter(max_retries=retry, pool_connections=workers, pool_maxsize=workers)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = "BookScout/2.0 (learning project)"
    return session


def _get(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=15)
    response.raise_for_status()
    response.encoding = "utf-8"  # avoids the "Â£" mojibake in prices
    return response.text


def parse_listing(html: str, page_url: str, page: int) -> list[dict]:
    rows = []
    for position, pod in enumerate(_soup(html).select("article.product_pod")):
        link = pod.select_one("h3 a")
        if link is None:
            continue
        rating_tag = pod.select_one("p.star-rating")
        classes = rating_tag.get("class", []) if rating_tag else []
        price_tag = pod.select_one("p.price_color")
        stock_tag = pod.select_one("p.availability")
        image = pod.select_one("img")
        availability = stock_tag.get_text(strip=True) if stock_tag else ""
        rows.append({
            "Page": page,
            "Position": position,
            "Title": link.get("title") or link.get_text(strip=True),
            "Price": _number(price_tag.get_text()) if price_tag else None,
            "Rating": next((RATINGS[c] for c in classes if c in RATINGS), None),
            "In stock": "in stock" in availability.lower(),
            "Image": urljoin(page_url, image["src"]) if image and image.get("src") else None,
            "URL": urljoin(page_url, link["href"]),
        })
    return rows


def parse_detail(html: str) -> dict:
    soup = _soup(html)
    crumbs = soup.select("ul.breadcrumb li a")
    stock = soup.select_one("p.availability")
    description = soup.select_one("#product_description ~ p")
    table = {
        th.get_text(strip=True): td.get_text(strip=True)
        for th, td in ((r.select_one("th"), r.select_one("td")) for r in soup.select("table tr"))
        if th and td
    }
    return {
        "Category": crumbs[2].get_text(strip=True) if len(crumbs) >= 3 else None,
        "Stock count": _number(re.sub(r".*\(", "", stock.get_text(" ", strip=True))) if stock else None,
        "Description": description.get_text(strip=True) if description else None,
        "UPC": table.get("UPC"),
    }


def fetch_books(
    pages: int = MAX_PAGES,
    deep: bool = False,
    workers: int = 8,
    on_progress: Progress | None = None,
) -> tuple[pd.DataFrame, list[int]]:
    """Scrape `pages` catalogue pages. With deep=True, also open every book page."""
    session = make_session(workers)
    rows: list[dict] = []
    failed: list[int] = []

    def page_job(n: int) -> list[dict]:
        url = PAGE_URL.format(n)
        return parse_listing(_get(session, url), url, n)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(page_job, n): n for n in range(1, pages + 1)}
        for done, job in enumerate(as_completed(jobs), start=1):
            try:
                rows.extend(job.result())
            except Exception:
                failed.append(jobs[job])
            if on_progress:
                on_progress("Reading catalogue pages", done, pages)

    if deep and rows:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = {pool.submit(lambda u: parse_detail(_get(session, u)), r["URL"]): r for r in rows}
            for done, job in enumerate(as_completed(jobs), start=1):
                try:
                    jobs[job].update(job.result())
                except Exception:
                    pass
                if on_progress:
                    on_progress("Reading book pages", done, len(rows))

    df = pd.DataFrame(rows)
    if df.empty:
        return df, sorted(failed)
    df = df.sort_values(["Page", "Position"]).reset_index(drop=True)
    df["Value score"] = (df["Rating"] / df["Price"] * 10).round(2)
    return df, sorted(failed)
