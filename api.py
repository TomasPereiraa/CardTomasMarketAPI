from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import FileResponse
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import io
import os
from sqlalchemy import create_engine, Column, String, Float, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta

app = FastAPI()

# Database Configuration
DATABASE_URL = "sqlite:///./prices.db"  # Change to PostgreSQL if needed
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Model for Storing Prices
class CardPrice(Base):
    __tablename__ = "card_prices"

    url = Column(String, primary_key=True, index=True)
    trend_price = Column(Float, nullable=True)
    avg_30_price = Column(Float, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow)

# Create Database Tables
Base.metadata.create_all(bind=engine)

# Function to Get a Database Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Persistent Storage for Railway Deployment
STORAGE_PATH = "/data" if os.getenv("RAILWAY_ENVIRONMENT") else "."

# Chrome Driver Class (Keeps Chrome Open)
class ChromeDriver:
    def __init__(self):
        self.driver = None  # Don't start Chrome immediately

    def get_driver(self):
        if self.driver is None:  # Start Chrome only when needed
            options = uc.ChromeOptions()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--window-size=1920,1080")
            self.driver = uc.Chrome(options=options)  # Chrome starts only when this method is called
            print("✅ Chrome started!")
        return self.driver

    def close_driver(self):
        if self.driver:
            print("Closing Chrome...")
            self.driver.quit()
            self.driver = None

# Create a Single Instance of ChromeDriver (Reused for All Requests)
chrome_instance = ChromeDriver()

# Function to Scrape Cardmarket Prices (Checks Database First)
def get_cardmarket_prices(url, db: Session):
    # Check if the price is already stored (cached)
    cached_price = db.query(CardPrice).filter(CardPrice.url == url).first()

    # If price exists and is recent (last 24h), return cached result
    if cached_price and cached_price.last_updated > datetime.utcnow() - timedelta(hours=24):
        print(f"⚡ Returning cached price for {url}")
        return {
            "trend_price": cached_price.trend_price,
            "30_day_avg_price": cached_price.avg_30_price
        }

    # Otherwise, fetch new data
    driver = chrome_instance.get_driver()

    try:
        driver.get(url)
        time.sleep(3)  # Allow Cloudflare check

        # Extract Trend Price
        try:
            trend_price = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//dt[contains(text(), 'Price Trend')]/following-sibling::dd/span"))
            ).text
            trend_price = float(trend_price.replace(" €", "").replace(",", "."))  # Convert to float
        except:
            trend_price = None

        # Extract 30-Day Avg Price
        try:
            avg_30_price = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//dt[contains(text(), '30-days average price')]/following-sibling::dd/span"))
            ).text
            avg_30_price = float(avg_30_price.replace(" €", "").replace(",", "."))  # Convert to float
        except:
            avg_30_price = None

        # Save new price to database
        new_price = CardPrice(url=url, trend_price=trend_price, avg_30_price=avg_30_price,
                              last_updated=datetime.utcnow())
        db.add(new_price)
        db.commit()

        return {"trend_price": trend_price, "30_day_avg_price": avg_30_price}

    except Exception as e:
        return {"trend_price": "Error", "30_day_avg_price": "Error"}

# API Endpoint to Fetch a Single Price (Uses Database Cache)
@app.get("/price")
def fetch_price(url: str, db: Session = Depends(get_db)):
    if "cardmarket.com" not in url:
        raise HTTPException(status_code=400, detail="Invalid URL. Must be from Cardmarket.")

    prices = get_cardmarket_prices(url, db)
    return {"url": url, "prices": prices}

# API Endpoint to Upload CSV & Get Updated Prices (Uses Database Cache)
@app.post("/upload_csv")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Save the uploaded file in Railway's storage
    file_location = os.path.join(STORAGE_PATH, file.filename)

    with open(file_location, "wb") as f:
        f.write(await file.read())

    df = pd.read_csv(file_location, encoding="utf-8", sep=";")

    if "URL" not in df.columns:
        raise HTTPException(status_code=400, detail="CSV file must contain a 'URL' column.")

    df["Trend Price"] = ""
    df["30-Day Avg Price"] = ""

    for index, row in df.iterrows():
        url = row["URL"]
        print(f"📢 Fetching prices for: {url}...")

        prices = get_cardmarket_prices(url, db)

        df.at[index, "Trend Price"] = prices["trend_price"]
        df.at[index, "30-Day Avg Price"] = prices["30_day_avg_price"]

    # Save updated CSV in Railway storage
    output_file = os.path.join(STORAGE_PATH, "updated_pokemons_cards.csv")
    df.to_csv(output_file, index=False, encoding="utf-8", sep=";")

    # Return file for download
    return FileResponse(output_file, filename="updated_pokemons_cards.csv", media_type="text/csv")

# API Endpoint to Fetch Total Sum of Prices
@app.get("/total_prices")
def get_total_prices(db: Session = Depends(get_db)):
    total_trend_price = db.query(func.sum(CardPrice.trend_price)).scalar() or 0
    total_avg_30_price = db.query(func.sum(CardPrice.avg_30_price)).scalar() or 0

    return {"total_trend_price": round(total_trend_price, 2), "total_avg_30_price": round(total_avg_30_price, 2)}

# Close Chrome when API is stopped
@app.on_event("shutdown")
def shutdown():
    chrome_instance.close_driver()

# Run API with Uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
