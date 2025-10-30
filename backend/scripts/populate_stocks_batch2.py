#!/usr/bin/env python3
"""
Add additional 60+ stocks to reach 300+ total
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.db.database import SessionLocal
from app.models.stock import Stock
from sqlalchemy.exc import IntegrityError

# Additional 60+ stocks to reach 300+
STOCKS_BATCH2 = [
    # More Tech & Software
    ("SPLK", "Splunk Inc.", "Technology", "Data Analytics"),
    ("TEAM", "Atlassian Corporation", "Technology", "Collaboration Software"),
    ("ZI", "ZoomInfo Technologies", "Technology", "Marketing Software"),
    ("BILL", "Bill.com Holdings", "Technology", "Financial Software"),
    ("S", "SentinelOne Inc.", "Technology", "Cybersecurity"),
    ("FTNT", "Fortinet Inc.", "Technology", "Cybersecurity"),
    ("CYBR", "CyberArk Software", "Technology", "Cybersecurity"),
    ("ESTC", "Elastic NV", "Technology", "Search Software"),
    ("MDB", "MongoDB Inc.", "Technology", "Database Software"),
    ("CFLT", "Confluent Inc.", "Technology", "Data Streaming"),

    # Semiconductors
    ("ON", "ON Semiconductor", "Technology", "Semiconductors"),
    ("MPWR", "Monolithic Power Systems", "Technology", "Semiconductors"),
    ("ENTG", "Entegris Inc.", "Technology", "Semiconductor Materials"),
    ("WOLF", "Wolfspeed Inc.", "Technology", "Semiconductors"),
    ("SLAB", "Silicon Laboratories", "Technology", "Semiconductors"),

    # Biotechnology
    ("MRNA", "Moderna Inc.", "Healthcare", "Biotechnology"),
    ("BNTX", "BioNTech SE", "Healthcare", "Biotechnology"),
    ("SGEN", "Seagen Inc.", "Healthcare", "Biotechnology"),
    ("BGNE", "BeiGene Ltd.", "Healthcare", "Biotechnology"),
    ("EXAS", "Exact Sciences", "Healthcare", "Diagnostics"),
    ("JAZZ", "Jazz Pharmaceuticals", "Healthcare", "Biotechnology"),
    ("NBIX", "Neurocrine Biosciences", "Healthcare", "Biotechnology"),
    ("INCY", "Incyte Corporation", "Healthcare", "Biotechnology"),
    ("SSNC", "SS&C Technologies", "Technology", "Financial Software"),

    # Medical Devices
    ("MDT", "Medtronic plc", "Healthcare", "Medical Devices"),
    ("ZBH", "Zimmer Biomet", "Healthcare", "Medical Devices"),
    ("BDX", "Becton Dickinson", "Healthcare", "Medical Devices"),
    ("BAX", "Baxter International", "Healthcare", "Medical Devices"),
    ("HOLX", "Hologic Inc.", "Healthcare", "Medical Devices"),
    ("DXCM", "DexCom Inc.", "Healthcare", "Medical Devices"),
    ("PODD", "Insulet Corporation", "Healthcare", "Medical Devices"),
    ("TDOC", "Teladoc Health", "Healthcare", "Telehealth"),

    # Financial Services
    ("SPGI", "S&P Global Inc.", "Financial", "Financial Data"),
    ("MCO", "Moody's Corporation", "Financial", "Credit Rating"),
    ("ICE", "Intercontinental Exchange", "Financial", "Stock Exchange"),
    ("CME", "CME Group Inc.", "Financial", "Futures Exchange"),
    ("NDAQ", "Nasdaq Inc.", "Financial", "Stock Exchange"),
    ("MKTX", "MarketAxess Holdings", "Financial", "Bond Trading"),
    ("TW", "Tradeweb Markets", "Financial", "Bond Trading"),
    ("FI", "Fiserv Inc.", "Financial", "Payment Processing"),
    ("FISV", "Fiserv Inc.", "Financial", "Payment Processing"),
    ("FIS", "Fidelity National Info", "Financial", "Financial Services"),
    ("GPN", "Global Payments", "Financial", "Payment Processing"),

    # Consumer Goods
    ("EL", "Estee Lauder", "Consumer Goods", "Cosmetics"),
    ("ULTA", "Ulta Beauty", "Retail", "Beauty Products"),
    ("LEVI", "Levi Strauss & Co.", "Consumer Goods", "Apparel"),
    ("CROX", "Crocs Inc.", "Consumer Goods", "Footwear"),
    ("DECK", "Deckers Outdoor", "Consumer Goods", "Footwear"),
    ("SKX", "Skechers USA", "Consumer Goods", "Footwear"),
    ("HAS", "Hasbro Inc.", "Consumer Goods", "Toys"),
    ("MAT", "Mattel Inc.", "Consumer Goods", "Toys"),

    # Restaurants & Food
    ("CMG", "Chipotle Mexican Grill", "Consumer Services", "Restaurants"),
    ("QSR", "Restaurant Brands Intl", "Consumer Services", "Restaurants"),
    ("YUM", "Yum! Brands", "Consumer Services", "Restaurants"),
    ("DPZ", "Domino's Pizza", "Consumer Services", "Restaurants"),
    ("WING", "Wingstop Inc.", "Consumer Services", "Restaurants"),
    ("TXRH", "Texas Roadhouse", "Consumer Services", "Restaurants"),
    ("BLMN", "Bloomin' Brands", "Consumer Services", "Restaurants"),
    ("DNUT", "Krispy Kreme", "Consumer Services", "Restaurants"),

    # E-commerce & Retail
    ("CVNA", "Carvana Co.", "Retail", "Online Auto Sales"),
    ("RH", "RH (Restoration Hardware)", "Retail", "Home Furnishings"),
    ("WSM", "Williams-Sonoma", "Retail", "Home Furnishings"),
    ("BBWI", "Bath & Body Works", "Retail", "Personal Care"),
    ("VSCO", "Victoria's Secret", "Retail", "Apparel"),
    ("FIVE", "Five Below", "Retail", "Discount Stores"),
    ("OLLI", "Ollie's Bargain Outlet", "Retail", "Discount Stores"),
    ("BIG", "Big Lots Inc.", "Retail", "Discount Stores"),

    # Energy & Renewables
    ("APA", "APA Corporation", "Energy", "Oil & Gas"),
    ("DVN", "Devon Energy", "Energy", "Oil & Gas"),
    ("HAL", "Halliburton Company", "Energy", "Oil Services"),
    ("BKR", "Baker Hughes", "Energy", "Oil Services"),
    ("NOV", "NOV Inc.", "Energy", "Oil Equipment"),
    ("RIG", "Transocean Ltd.", "Energy", "Offshore Drilling"),
    ("TELL", "Tellurian Inc.", "Energy", "LNG"),
    ("LNG", "Cheniere Energy", "Energy", "LNG"),

    # Industrials & Transportation
    ("NSC", "Norfolk Southern", "Industrials", "Railroads"),
    ("UNP", "Union Pacific", "Industrials", "Railroads"),
    ("CSX", "CSX Corporation", "Industrials", "Railroads"),
    ("JBHT", "J.B. Hunt Transport", "Industrials", "Trucking"),
    ("ODFL", "Old Dominion Freight", "Industrials", "Trucking"),
    ("XPO", "XPO Logistics", "Industrials", "Logistics"),
    ("CHRW", "C.H. Robinson", "Industrials", "Logistics"),
    ("R", "Ryder System", "Industrials", "Truck Leasing"),

    # Materials
    ("NEM", "Newmont Corporation", "Materials", "Gold Mining"),
    ("GOLD", "Barrick Gold", "Materials", "Gold Mining"),
    ("FCX", "Freeport-McMoRan", "Materials", "Copper Mining"),
    ("NUE", "Nucor Corporation", "Materials", "Steel"),
    ("STLD", "Steel Dynamics", "Materials", "Steel"),
    ("X", "United States Steel", "Materials", "Steel"),
    ("CLF", "Cleveland-Cliffs", "Materials", "Steel"),
    ("AA", "Alcoa Corporation", "Materials", "Aluminum"),

    # Additional Popular Stocks
    ("HOOD", "Robinhood Markets", "Financial", "Brokerage"),
    ("RIVN", "Rivian Automotive", "Automotive", "Electric Vehicles"),
    ("LCID", "Lucid Group Inc.", "Automotive", "Electric Vehicles"),
]

def populate_stocks_batch2():
    """Insert additional stocks into database"""
    db = SessionLocal()
    added = 0
    skipped = 0

    try:
        for symbol, name, sector, industry in STOCKS_BATCH2:
            try:
                existing = db.query(Stock).filter(Stock.symbol == symbol).first()
                if existing:
                    print(f"[SKIP] {symbol:8} - Already exists")
                    skipped += 1
                    continue

                stock = Stock(
                    symbol=symbol,
                    name=name,
                    sector=sector,
                    industry=industry
                )
                db.add(stock)
                db.commit()
                print(f"[ADD]  {symbol:8} - {name}")
                added += 1

            except IntegrityError:
                db.rollback()
                print(f"[ERR]  {symbol:8} - Duplicate (skipped)")
                skipped += 1
            except Exception as e:
                db.rollback()
                print(f"[ERR]  {symbol:8} - Error: {e}")

        print(f"\n{'='*60}")
        print(f"[OK] Added: {added} stocks")
        print(f"[OK] Skipped: {skipped} stocks (already existed)")
        print(f"[OK] Batch 2 total: {len(STOCKS_BATCH2)} stocks")
        print(f"{'='*60}")

    finally:
        db.close()

if __name__ == "__main__":
    print(f"{'='*60}")
    print(f"  Stock Database Population Script - Batch 2")
    print(f"{'='*60}\n")
    populate_stocks_batch2()
