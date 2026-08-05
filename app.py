import streamlit as st
import requests
import bs4
import pandas as pd

# Title
st.title("📚 Book Scraper")
st.write("This app scrapes 2-star rated books from Books to Scrape.")

# URL
url = "http://books.toscrape.com/catalogue/page-{}.html"

# Button to start scraping
if st.button("Scrape Books"):

    book_data = []

    # Loop through pages
    for page_num in range(1, 2):   # Change 2 to 51 for all pages

        scrape_url = url.format(page_num)

        response = requests.get(scrape_url)

        if response.status_code == 200:

            soup = bs4.BeautifulSoup(response.text, "lxml")

            books = soup.select(".product_pod")

            for book in books:

                # Select only 2-star books
                if book.select(".star-rating.Two"):

                    title = book.select("a")[1]["title"]
                    price = book.find("p", class_="price_color").text
                    stock = book.find(
                        "p",
                        class_="instock availability"
                    ).text.strip()

                    book_data.append({
                        "Title": title,
                        "Price": price,
                        "Stock": stock
                    })

        else:
            st.error(f"Failed to load page {page_num}")

    if book_data:

        df = pd.DataFrame(book_data)

        st.success(f"Found {len(df)} books!")

        st.dataframe(df, use_container_width=True)

        # Download CSV
        csv = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name="two_star_books.csv",
            mime="text/csv",
        )

    else:
        st.warning("No books found.")
    