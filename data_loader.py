"""Load and enrich eBay auction data from Excel."""
import pandas as pd
import numpy as np

# Virtual products to diversify the portfolio beyond Samsung phones
_VIRTUAL = [
    {
        "product_id": "V001", "is_virtual": True,
        "title": "Apple iPhone 15 Pro Max 256GB Unlocked - Excellent",
        "category": "Smartphones", "condition": "Excellent",
        "start_price": 850.0, "final_price": 1185.0, "bid_increment": 25.0,
        "number_of_bidders": 11, "total_bids": 28, "duration_hours": 96, "watch_count": 220,
    },
    {
        "product_id": "V002", "is_virtual": True,
        "title": "Apple iPhone 14 128GB Unlocked - Very Good",
        "category": "Smartphones", "condition": "Very Good",
        "start_price": 420.0, "final_price": 585.0, "bid_increment": 15.0,
        "number_of_bidders": 7, "total_bids": 19, "duration_hours": 72, "watch_count": 145,
    },
    {
        "product_id": "V003", "is_virtual": True,
        "title": "iPad Pro 12.9\" M2 256GB WiFi - Good",
        "category": "Tablets", "condition": "Good",
        "start_price": 550.0, "final_price": 790.0, "bid_increment": 20.0,
        "number_of_bidders": 9, "total_bids": 22, "duration_hours": 96, "watch_count": 195,
    },
    {
        "product_id": "V004", "is_virtual": True,
        "title": "Samsung Galaxy Tab S9 Ultra 256GB WiFi - Very Good",
        "category": "Tablets", "condition": "Very Good",
        "start_price": 480.0, "final_price": 685.0, "bid_increment": 18.0,
        "number_of_bidders": 8, "total_bids": 17, "duration_hours": 72, "watch_count": 162,
    },
    {
        "product_id": "V005", "is_virtual": True,
        "title": "Apple Watch Ultra 2 49mm GPS+Cell - Excellent",
        "category": "Wearables", "condition": "Excellent",
        "start_price": 450.0, "final_price": 645.0, "bid_increment": 15.0,
        "number_of_bidders": 10, "total_bids": 24, "duration_hours": 72, "watch_count": 178,
    },
    {
        "product_id": "V006", "is_virtual": True,
        "title": "MacBook Pro M3 Pro 14\" 18GB 512GB Space Black",
        "category": "Laptops", "condition": "Excellent",
        "start_price": 1400.0, "final_price": 1870.0, "bid_increment": 35.0,
        "number_of_bidders": 13, "total_bids": 33, "duration_hours": 120, "watch_count": 285,
    },
    {
        "product_id": "V007", "is_virtual": True,
        "title": "Anker 26800mAh Portable Charger PD - New",
        "category": "Accessories", "condition": "New",
        "start_price": 22.0, "final_price": 38.0, "bid_increment": 1.0,
        "number_of_bidders": 6, "total_bids": 16, "duration_hours": 48, "watch_count": 55,
    },
    {
        "product_id": "V008", "is_virtual": True,
        "title": "USB-C 140W Fast Charging Cable 2m 3-pack",
        "category": "Accessories", "condition": "New",
        "start_price": 9.0, "final_price": 16.5, "bid_increment": 0.5,
        "number_of_bidders": 5, "total_bids": 14, "duration_hours": 24, "watch_count": 40,
    },
]


def _assign_function_type(market_price: float) -> str:
    if market_price > 500:
        return "GMV"
    if market_price < 100:
        return "traffic"
    return "custom"


def load_and_prepare(excel_path: str) -> pd.DataFrame:
    raw = pd.read_excel(excel_path)

    raw = raw.rename(columns={
        "Item_ID":                "product_id",
        "Auction_Title":          "title",
        "Category":               "category",
        "Product_Year":           "year",
        "Condition":              "condition",
        "Storage_GB":             "storage_gb",
        "Has_Accessories":        "has_accessories",
        "Starting_Price_USD":     "start_price",
        "Final_Price_USD":        "final_price",
        "Premium_Rate":           "premium_rate",
        "Number_of_Bidders":      "number_of_bidders",
        "Total_Bids":             "total_bids",
        "Auction_Duration_Hours": "duration_hours",
        "Bid_Increment_USD":      "bid_increment",
        "Watch_Count":            "watch_count",
        "Seller_Rating":          "seller_rating",
        "Free_Returns":           "free_returns",
        "Fast_Shipping":          "fast_shipping",
        "Best_Offer_Enabled":     "best_offer_enabled",
    })
    raw["product_id"] = raw["product_id"].astype(str)
    raw["is_virtual"] = False

    # Virtual products
    vdf = pd.DataFrame(_VIRTUAL)
    vdf["year"] = 2023
    vdf["storage_gb"] = None
    vdf["has_accessories"] = False
    vdf["seller_rating"] = 98
    vdf["free_returns"] = True
    vdf["fast_shipping"] = True
    vdf["best_offer_enabled"] = False
    vdf["premium_rate"] = (vdf["final_price"] / vdf["start_price"]).round(3)

    df = pd.concat([raw, vdf], ignore_index=True)

    # Core derived fields
    df["market_price"]   = df["final_price"]   # actual sold price = market reference
    df["function_type"]  = df["market_price"].apply(_assign_function_type)
    df["viewers"]        = (df["watch_count"] * 4).clip(lower=50).round(0).astype(int)
    df["actual_sp_ratio"] = (df["start_price"] / df["market_price"]).clip(upper=1.0).round(3)
    df["actual_pi_ratio"] = (df["bid_increment"] / df["market_price"]).round(4)

    # Short display title
    df["short_title"] = df["title"].str[:50]

    # Category simplified (strip sub-category)
    df["category_short"] = df["category"].astype(str).str.split(":").str[0].str.strip()

    return df
