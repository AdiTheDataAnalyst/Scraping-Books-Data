# 📚 Book Scout

Scrape the [Books to Scrape](https://books.toscrape.com) catalogue with BeautifulSoup, then explore it in an interactive Streamlit dashboard.

## Features
- **Full catalogue scraping**: all 50 pages (1,000 books), fetched concurrently with retries and a live progress bar
- **Deep scrape (optional)**: category, stock count, UPC and description from each book's own page
- **Clean data**: numeric prices, 1 to 5 ratings, correct `£` encoding, and a value score (stars per pound)
- **Filters**: title search, rating, price range, stock, category, and five sort orders
- **Price shelf**: every book drawn as a spine, height = price, shade = rating
- **Browse**: paginated cover cards that link to each book
- **Insights**: auto-written highlights plus price, rating and category charts (Plotly)
- **Export**: CSV, Excel and JSON of the filtered results

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Structure
| File | Purpose |
|---|---|
| `scraper.py` | Fetching and parsing (no Streamlit dependency) |
| `app.py` | UI, filters, charts, exports |
| `.streamlit/config.toml` | Theme |

## Workflow
Website → concurrent requests → BeautifulSoup parsing → Pandas DataFrame → filters → cards, charts and exports
