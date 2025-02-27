# Cardmarket Price Scraper API

## Overview

This FastAPI application scrapes and caches prices from Cardmarket.com. It provides endpoints for retrieving individual card prices, uploading a CSV file with multiple card URLs to update prices in bulk, and calculating total prices.

## Features

- Fetch card prices from Cardmarket using Selenium
- Cache prices in a SQLite database for 24 hours
- Upload CSV files to get updated prices
- Retrieve total sum of all stored prices
- Uses an undetected Chrome driver for bypassing bot detection

## Installation

### Prerequisites

- Python 3.8+
- Google Chrome installed
- Chromedriver compatible with the installed Chrome version

### Install Dependencies

```sh
pip install fastapi uvicorn pandas selenium undetected-chromedriver sqlalchemy
```

## Running the API

Start the FastAPI server with:

```sh
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Endpoints

### 1. Fetch a Single Card Price

**GET /price**

**Query Parameters:**

- `url` (string) - The Cardmarket URL of the card.

**Response:**

```json
{
  "url": "https://www.cardmarket.com/en/Magic/Products/Singles/Card-Example",
  "prices": {
    "trend_price": 12.50,
    "30_day_avg_price": 13.20
  }
}
```

### 2. Upload CSV to Fetch Prices

**POST /upload\_csv**

**Request:**

- Upload a CSV file containing a column named `URL`.

**Response:**

- Returns a CSV file with the updated `Trend Price` and `30-Day Avg Price` columns.

### 3. Get Total Prices

**GET /total\_prices**

**Response:**

```json
{
  "total_trend_price": 1000.50,
  "total_avg_30_price": 1100.75
}
```

## Deployment

This API is designed to run on Railway, with persistent storage set to `/data` for uploaded files. Modify the `DATABASE_URL` if using PostgreSQL.

## Notes

- The API keeps a single instance of Chrome open to optimize performance.
- Cached prices are stored for 24 hours to reduce requests to Cardmarket.
- Ensure Chrome and Chromedriver versions match to avoid Selenium errors.

