"""Scrape any public website: auto-detect content or define your own fields."""
import streamlit as st

import generic
from generic import ScrapeError

st.set_page_config(page_title="Scrape any website", page_icon="🔎", layout="wide")
st.title("Scrape any website")
st.caption("Enter a public page. Book Scout checks robots.txt, then lets you pull out tables, links or your own fields.")

url = st.text_input("Website address", placeholder="https://quotes.toscrape.com")
if st.button("Fetch page", type="primary") and url:
    st.session_state.pop("page_html", None)
    try:
        if not generic.allowed_by_robots(url):
            st.error("This site's robots.txt asks automated tools not to read this page, so Book Scout won't fetch it.")
        else:
            with st.spinner("Fetching page"):
                st.session_state.page_html = generic.fetch_html(url)
                st.session_state.page_url = url
    except ScrapeError as exc:
        st.error(str(exc))

if "amazon." in url.lower():
    st.warning("Amazon forbids automated scraping in its terms and blocks bots. Use the Product Advertising API instead.")

html = st.session_state.get("page_html")
if not html:
    st.info("Fetch a page to begin. For practice, try https://quotes.toscrape.com or https://books.toscrape.com.")
    st.stop()

base = st.session_state.page_url
st.success(f"Fetched {base} ({len(html) / 1000:.0f} KB).")
auto, custom = st.tabs(["Auto-detect", "Custom fields"])

with auto:
    found = generic.auto_extract(html, base)
    if not found:
        st.info("Nothing recognisable here. The page may load its content with JavaScript, which this tool can't run.")
    for name, df in found.items():
        with st.expander(f"{name} ({len(df)} rows)", expanded=name in ("Metadata", "Table 1")):
            st.dataframe(df, hide_index=True, width="stretch")
            st.download_button(f"Download {name} as CSV", df.to_csv(index=False).encode("utf-8"),
                               f"{name.lower().replace(' ', '_')}.csv", "text/csv", key=f"dl_{name}")

with custom:
    st.markdown("Right-click an item on the page, choose **Inspect**, and copy its CSS selector. "
                "Add `@href` or `@src` after a selector to read an attribute instead of text.")
    container = st.text_input("Item selector (one match per row)", placeholder="div.quote")
    spec = st.text_area("Fields (name = selector)", height=130,
                        placeholder="text = span.text\nauthor = small.author\nlink = a@href")
    next_sel = st.text_input("Next-page link selector (optional)", placeholder="li.next a")
    c1, c2 = st.columns(2)
    max_pages = c1.slider("Pages to read", 1, 20, 1)
    delay = c2.slider("Pause between pages (seconds)", 0.5, 5.0, 1.0, 0.5, help="Be kind to the server.")
    if st.button("Extract data"):
        fields = generic.parse_fields(spec)
        if not fields:
            st.error("Add at least one field, for example: title = h2 a")
        else:
            bar = st.progress(0.0)
            try:
                df = generic.crawl(base, html, container, fields, next_sel, max_pages, delay,
                                   lambda d, t: bar.progress(d / t, text=f"Page {d} of {t}"))
                st.session_state.custom_df = df
            except ScrapeError as exc:
                st.error(str(exc))
            bar.empty()
    df = st.session_state.get("custom_df")
    if df is not None:
        if df.empty or df.drop(columns=["Source page"], errors="ignore").isna().all().all():
            st.warning("No data matched. Check your selectors against the page's HTML.")
        else:
            st.dataframe(df, hide_index=True, width="stretch")
            st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), "scraped.csv", "text/csv")
