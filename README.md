# 📚 Book Scraping & Analysis Project

A Python-based web scraping application that extracts book information from a website using **BeautifulSoup** and presents the collected data through an interactive **Streamlit** interface.

---

## 📌 Project Overview

The objective of this project is to automate the collection of book information from a website instead of manually collecting the data.

The application scrapes book-related information, processes the collected data using Python and Pandas, and displays the results through an interactive Streamlit application.

This project demonstrates practical knowledge of:

- Web Scraping
- HTML Parsing
- Python
- BeautifulSoup
- Pandas
- Streamlit
- Data Cleaning
- Data Visualization
- Data Export

---

## 🚀 Features

### 🔎 Web Scraping

The application uses **BeautifulSoup** to parse website HTML and extract book information.

Depending on the website structure, the scraper collects information such as:

- 📖 Book Title
- 💰 Price
- ⭐ Rating
- 📦 Availability
- 🔗 Product information

---

### 📊 Data Processing

The scraped information is converted into a structured dataset using **Pandas**.

Data processing can include:

- Removing unnecessary data
- Handling missing values
- Converting values into appropriate formats
- Structuring scraped information into columns

---

### 🖥️ Streamlit Interface

The scraped data is displayed through an interactive Streamlit application.

Users can:

- View scraped books
- Explore book information
- Analyze the collected data
- Filter the displayed results
- Download the scraped dataset

---

## 🔄 Project Workflow

```text
Website
   ↓
Send HTTP Request
   ↓
Receive HTML Response
   ↓
BeautifulSoup
   ↓
Parse HTML
   ↓
Extract Book Information
   ↓
Pandas DataFrame
   ↓
Data Cleaning
   ↓
Streamlit Application
   ↓
Display / Analyze / Download Data
