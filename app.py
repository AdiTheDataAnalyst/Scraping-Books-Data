"""Book Scout: scrape books.toscrape.com and explore prices, ratings and stock."""
from __future__ import annotations

import html
import io
import math
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from scraper import MAX_PAGES, fetch_books

st.set_page_config(page_title="Book Scout", page_icon="📚", layout="wide")

INK, TEAL, MIST = "#1B1F3B", "#0F766E", "#E6EBF5"
RATING_COLORS = {1: "#CBD5E8", 2: "#9FB3D6", 3: "#6C8FBE", 4: "#2E8B8B", 5: "#0F5F59"}
PER_PAGE = 24

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Newsreader:opsz,wght@6..72,500;6..72,700&display=swap');
.stApp, button, input, textarea { font-family: 'DM Sans', sans-serif; }
h1, h2, h3, .bs-title { font-family: 'Newsreader', Georgia, serif !important; letter-spacing: -0.01em; }
.block-container { padding-top: 2.2rem; max-width: 1280px; }
.bs-title { font-size: clamp(2.4rem, 5vw, 3.6rem); font-weight: 700; line-height: 1.05; margin: 0; color: #1B1F3B; }
.bs-sub { color: #4A5170; font-size: 1.05rem; margin: .5rem 0 1.4rem; max-width: 60ch; }
.bs-shelf { display: flex; align-items: flex-end; gap: 3px; height: 130px; border-bottom: 5px solid #1B1F3B; padding: 0 2px; }
.bs-spine { flex: 1; min-width: 4px; border-radius: 3px 3px 0 0; transition: transform .15s; transform-origin: bottom; }
.bs-spine:hover { transform: scaleY(1.06); }
.bs-legend { display: flex; align-items: center; gap: .4rem; font-size: .85rem; color: #4A5170; margin: .6rem 0 1.4rem; flex-wrap: wrap; }
.bs-legend i { width: 14px; height: 14px; border-radius: 3px; display: inline-block; }
.bs-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 1.1rem; margin-top: .6rem; }
.bs-card { background: #fff; border: 1px solid #E6EBF5; border-radius: 10px; overflow: hidden; text-decoration: none !important; color: #1B1F3B !important; display: flex; flex-direction: column; transition: border-color .15s; }
.bs-card:hover, .bs-card:focus-visible { border-color: #0F766E; outline: none; }
.bs-cover { background: #E6EBF5; aspect-ratio: 4/5; display: flex; align-items: center; justify-content: center; padding: .9rem; }
.bs-cover img { max-width: 100%; max-height: 100%; object-fit: contain; }
.bs-body { padding: .7rem .8rem .9rem; display: flex; flex-direction: column; gap: .3rem; }
.bs-name { font-weight: 500; font-size: .93rem; line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 2.4em; }
.bs-stars .on { color: #E8A33D; } .bs-stars .off { color: #D5DBEA; }
.bs-price { font-family: 'Newsreader', serif; font-size: 1.25rem; font-weight: 700; }
.bs-stock { font-size: .8rem; font-weight: 500; } .bs-stock.ok { color: #0F766E; } .bs-stock.out { color: #B42318; }
.bs-empty { background: #fff; border: 1px dashed #9FB3D6; border-radius: 12px; padding: 1.6rem 1.8rem; max-width: 640px; }
@media (prefers-reduced-motion: reduce) { .bs-spine, .bs-card { transition: none; } }
</style>
""", unsafe_allow_html=True)


# ---------- helpers ----------
def stars(n) -> str:
    n = 0 if pd.isna(n) else int(n)
    spans = "".join(f'<span class="{"on" if i < n else "off"}">★</span>' for i in range(5))
    return f'<span class="bs-stars" role="img" aria-label="{n} out of 5 stars">{spans}</span>'


def card(r: pd.Series) -> str:
    count = r.get("Stock count")
    label = "Out of stock" if not r["In stock"] else (f"In stock, {int(count)} left" if pd.notna(count) else "In stock")
    cls = "ok" if r["In stock"] else "out"
    title = html.escape(str(r["Title"]))
    return (
        f'<a class="bs-card" href="{html.escape(str(r["URL"]))}" target="_blank" rel="noopener noreferrer">'
        f'<div class="bs-cover"><img loading="lazy" src="{html.escape(str(r["Image"]))}" alt="Cover of {title}"></div>'
        f'<div class="bs-body"><div class="bs-name" title="{title}">{title}</div>{stars(r["Rating"])}'
        f'<div class="bs-price">£{r["Price"]:.2f}</div><div class="bs-stock {cls}">{label}</div></div></a>'
    )


def shelf(df: pd.DataFrame) -> str:
    sample = df.iloc[:: max(1, len(df) // 90)].head(90)
    top = sample["Price"].max()
    spines = "".join(
        f'<span class="bs-spine" style="height:{max(22, p / top * 100):.0f}%;background:{RATING_COLORS.get(r, MIST)}" '
        f'title="{html.escape(t)}, £{p:.2f}, {int(r) if pd.notna(r) else 0} stars"></span>'
        for t, p, r in zip(sample["Title"], sample["Price"], sample["Rating"])
    )
    legend = "".join(f'<i style="background:{c}"></i>{k}' for k, c in RATING_COLORS.items())
    return (
        f'<div class="bs-shelf" role="img" aria-label="Shelf of {len(sample)} books. Height shows price, shade shows rating.">{spines}</div>'
        f'<div class="bs-legend">Each spine is a book. Height is price, shade is rating (1 to 5 stars): {legend}</div>'
    )


def style(fig, height=320):
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=40, b=8), font=dict(family="DM Sans", color=INK),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False, title_font_size=15,
    )
    fig.update_xaxes(gridcolor=MIST, zeroline=False)
    fig.update_yaxes(gridcolor=MIST, zeroline=False)
    return fig


def to_excel(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, sheet_name="Books")
    return buffer.getvalue()


def run_scrape(pages: int, deep: bool) -> None:
    bar = st.progress(0.0, text="Starting")

    def on_progress(label: str, done: int, total: int) -> None:
        bar.progress(min(done / total, 1.0), text=f"{label}: {done} of {total}")

    try:
        df, failed = fetch_books(pages, deep, on_progress=on_progress)
    except Exception as exc:
        bar.empty()
        st.error(f"Scraping stopped: {exc}. Check your connection, then select Scrape books again.")
        return
    bar.empty()
    if df.empty:
        st.error("No books came back. The site may be down. Try again in a minute.")
        return
    st.session_state.books = df
    st.session_state.meta = {"pages": pages, "at": datetime.now().strftime("%H:%M"), "failed": failed}


# ---------- sidebar: scrape + filters ----------
with st.sidebar:
    st.markdown("### Scrape")
    pages = st.slider("Pages to scrape", 1, MAX_PAGES, 10, help="Each page lists 20 books.")
    deep = st.toggle("Add category and description", help="Opens every book's own page. Slower, about one request per book.")
    sidebar_scrape = st.button("Scrape books", type="primary", width="stretch")

if sidebar_scrape:
    run_scrape(pages, deep)

books: pd.DataFrame | None = st.session_state.get("books")

# ---------- hero ----------
st.markdown('<h1 class="bs-title">Book Scout</h1>', unsafe_allow_html=True)
st.markdown('<p class="bs-sub">Scrape the Books to Scrape catalogue, then filter it, chart it and export it.</p>', unsafe_allow_html=True)

if books is None:
    st.markdown(
        '<div class="bs-empty"><b>No books yet.</b><br>Choose how many pages to read in the sidebar, then scrape. '
        'Ten pages gives you 200 books in a few seconds.</div>', unsafe_allow_html=True)
    if st.button("Scrape 10 pages", type="primary"):
        run_scrape(10, False)
        st.rerun()
    st.stop()

# filters
with st.sidebar:
    st.markdown("### Filter")
    query = st.text_input("Search titles", placeholder="For example: night")
    rating_pick = st.multiselect("Rating", [5, 4, 3, 2, 1], default=[5, 4, 3, 2, 1], format_func=lambda s: "★" * s)
    lo, hi = math.floor(books["Price"].min()), math.ceil(books["Price"].max())
    price_range = st.slider("Price (£)", lo, hi, (lo, hi)) if lo < hi else (lo, hi)
    stock_only = st.toggle("In stock only")
    categories = st.multiselect("Category", sorted(books["Category"].dropna().unique())) if "Category" in books else []
    sort_by = st.selectbox("Sort by", ["Catalogue order", "Price: low to high", "Price: high to low", "Rating: high to low", "Best value"])

view = books[books["Rating"].isin(rating_pick) & books["Price"].between(*price_range)]
if query:
    view = view[view["Title"].str.contains(query, case=False, regex=False)]
if stock_only:
    view = view[view["In stock"]]
if categories:
    view = view[view["Category"].isin(categories)]
sorters = {
    "Price: low to high": ("Price", True), "Price: high to low": ("Price", False),
    "Rating: high to low": ("Rating", False), "Best value": ("Value score", False),
}
if sort_by in sorters:
    view = view.sort_values(sorters[sort_by][0], ascending=sorters[sort_by][1], kind="stable")

meta = st.session_state.meta
if meta["failed"]:
    st.warning(f"{len(meta['failed'])} catalogue page(s) failed to load: {meta['failed']}. Scrape again to retry.")

if view.empty:
    st.info("No books match these filters. Widen the price range or add more ratings.")
    st.stop()

st.markdown(shelf(view), unsafe_allow_html=True)
st.caption(f"{len(books)} books from {meta['pages']} pages, scraped at {meta['at']}.")

# ---------- KPIs ----------
kpis = [
    ("Books shown", f"{len(view):,}", f"of {len(books):,}"),
    ("Average price", f"£{view['Price'].mean():.2f}", f"median £{view['Price'].median():.2f}"),
    ("Average rating", f"{view['Rating'].mean():.2f} ★", f"{(view['Rating'] >= 4).mean():.0%} rated 4 or 5"),
    ("In stock", f"{view['In stock'].mean():.0%}", f"{int(view['In stock'].sum()):,} books"),
]
for col, (label, value, note) in zip(st.columns(4), kpis):
    with col, st.container(border=True):
        st.metric(label, value)
        st.caption(note)

browse, insights, data = st.tabs(["Browse", "Insights", "Data and export"])

# ---------- browse ----------
with browse:
    n_pages = max(1, math.ceil(len(view) / PER_PAGE))
    st.session_state.page_no = min(st.session_state.get("page_no", 1), n_pages)
    left, right = st.columns([4, 1])
    page_no = right.number_input("Page", 1, n_pages, key="page_no")
    start = (page_no - 1) * PER_PAGE
    left.caption(f"Showing {start + 1} to {min(start + PER_PAGE, len(view))} of {len(view):,} books. Select a card to open it on the site.")
    st.markdown(f'<div class="bs-grid">{"".join(card(r) for _, r in view.iloc[start:start + PER_PAGE].iterrows())}</div>', unsafe_allow_html=True)

# ---------- insights ----------
with insights:
    best = view.loc[view["Value score"].idxmax()]
    five = view[view["Rating"] == 5]
    cheapest5 = five.loc[five["Price"].idxmin()] if not five.empty else None
    st.markdown(f"**Best value:** *{best['Title']}* is rated {int(best['Rating'])} stars at £{best['Price']:.2f}.")
    if cheapest5 is not None:
        st.markdown(f"**Cheapest 5-star book:** *{cheapest5['Title']}* at £{cheapest5['Price']:.2f}.")
    corr = view["Price"].corr(view["Rating"])
    if pd.notna(corr):
        st.markdown(f"**Price and rating:** correlation is {corr:.2f}, so " + ("price says almost nothing about quality here." if abs(corr) < 0.15 else "there is a noticeable link between them."))

    c1, c2 = st.columns(2)
    fig = px.histogram(view, x="Price", nbins=30, title="How prices are spread", color_discrete_sequence=[TEAL])
    c1.plotly_chart(style(fig), width="stretch")
    counts = view["Rating"].value_counts().reindex([1, 2, 3, 4, 5], fill_value=0).reset_index()
    counts.columns = ["Rating", "Books"]
    fig = px.bar(counts, x="Rating", y="Books", title="Books per rating", color="Rating", color_discrete_map={k: v for k, v in RATING_COLORS.items()})
    fig.update_traces(marker_color=[RATING_COLORS[r] for r in counts["Rating"]])
    c2.plotly_chart(style(fig), width="stretch")

    c3, c4 = st.columns(2)
    fig = px.box(view.assign(Rating=view["Rating"].astype(int).astype(str) + " ★"), x="Rating", y="Price",
                 title="Price by rating", category_orders={"Rating": [f"{i} ★" for i in range(1, 6)]}, color_discrete_sequence=[TEAL])
    c3.plotly_chart(style(fig), width="stretch")
    if "Category" in view:
        top = view["Category"].value_counts().head(12).sort_values().reset_index()
        top.columns = ["Category", "Books"]
        fig = px.bar(top, x="Books", y="Category", orientation="h", title="Largest categories", color_discrete_sequence=[TEAL])
        c4.plotly_chart(style(fig), width="stretch")
    else:
        c4.info("Turn on “Add category and description” in the sidebar and scrape again to see categories.")

    st.markdown("#### Top 10 by value")
    st.caption("Value score is rating divided by price, times 10. Higher means more stars per pound.")
    st.dataframe(view.nlargest(10, "Value score")[["Title", "Price", "Rating", "Value score"]],
                 hide_index=True, width="stretch",
                 column_config={"Price": st.column_config.NumberColumn(format="£%.2f"), "Rating": st.column_config.NumberColumn(format="%d ★")})

# ---------- data ----------
with data:
    columns = [c for c in ["Image", "Title", "Category", "Price", "Rating", "In stock", "Stock count", "Value score", "UPC", "Description", "URL"] if c in view]
    st.dataframe(view[columns], hide_index=True, width="stretch", column_config={
        "Image": st.column_config.ImageColumn("Cover", width="small"),
        "Price": st.column_config.NumberColumn(format="£%.2f"),
        "Rating": st.column_config.NumberColumn(format="%d ★"),
        "URL": st.column_config.LinkColumn("Link", display_text="Open"),
    })
    st.caption(f"Downloads include the {len(view):,} books that match your filters.")
    export = view.drop(columns=["Position"], errors="ignore")
    stamp = datetime.now().strftime("%Y%m%d")
    d1, d2, d3 = st.columns(3)
    d1.download_button("Download CSV", export.to_csv(index=False).encode("utf-8"), f"books_{stamp}.csv", "text/csv", width="stretch")
    d2.download_button("Download Excel", to_excel(export), f"books_{stamp}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    d3.download_button("Download JSON", export.to_json(orient="records", force_ascii=False, indent=2), f"books_{stamp}.json", "application/json", width="stretch")

st.caption("Data from books.toscrape.com, a practice site built for scrapers.")
