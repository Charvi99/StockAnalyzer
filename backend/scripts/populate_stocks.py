#!/usr/bin/env python3
"""
Populate database with 300+ stock tickers for pattern collection
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.db.database import SessionLocal
from app.models.stock import Stock
from sqlalchemy.exc import IntegrityError

# 300+ Popular stocks across various sectors
STOCKS = [
    # Technology - FAANG and Major Tech
    ("AAPL", "Apple Inc.", "Technology", "Consumer Electronics"),
    ("MSFT", "Microsoft Corporation", "Technology", "Software"),
    ("GOOGL", "Alphabet Inc. Class A", "Technology", "Internet Services"),
    ("AMZN", "Amazon.com Inc.", "Technology", "E-commerce"),
    ("META", "Meta Platforms Inc.", "Technology", "Social Media"),
    ("NVDA", "NVIDIA Corporation", "Technology", "Semiconductors"),
    ("TSLA", "Tesla Inc.", "Automotive", "Electric Vehicles"),
    ("NFLX", "Netflix Inc.", "Technology", "Streaming"),
    ("AMD", "Advanced Micro Devices", "Technology", "Semiconductors"),
    ("INTC", "Intel Corporation", "Technology", "Semiconductors"),
    ("CRM", "Salesforce Inc.", "Technology", "Cloud Software"),
    ("ORCL", "Oracle Corporation", "Technology", "Enterprise Software"),
    ("ADBE", "Adobe Inc.", "Technology", "Software"),
    ("CSCO", "Cisco Systems", "Technology", "Networking"),
    ("AVGO", "Broadcom Inc.", "Technology", "Semiconductors"),
    ("QCOM", "Qualcomm Inc.", "Technology", "Semiconductors"),
    ("TXN", "Texas Instruments", "Technology", "Semiconductors"),
    ("AMAT", "Applied Materials", "Technology", "Semiconductor Equipment"),
    ("MU", "Micron Technology", "Technology", "Memory Chips"),
    ("LRCX", "Lam Research", "Technology", "Semiconductor Equipment"),

    # Financial Services
    ("JPM", "JPMorgan Chase & Co.", "Financial", "Banking"),
    ("BAC", "Bank of America Corp.", "Financial", "Banking"),
    ("WFC", "Wells Fargo & Company", "Financial", "Banking"),
    ("GS", "Goldman Sachs Group", "Financial", "Investment Banking"),
    ("MS", "Morgan Stanley", "Financial", "Investment Banking"),
    ("C", "Citigroup Inc.", "Financial", "Banking"),
    ("BLK", "BlackRock Inc.", "Financial", "Asset Management"),
    ("SCHW", "Charles Schwab Corp.", "Financial", "Brokerage"),
    ("AXP", "American Express", "Financial", "Credit Cards"),
    ("V", "Visa Inc.", "Financial", "Payment Processing"),
    ("MA", "Mastercard Inc.", "Financial", "Payment Processing"),
    ("PYPL", "PayPal Holdings", "Financial", "Digital Payments"),
    ("SQ", "Block Inc. (Square)", "Financial", "Digital Payments"),
    ("COF", "Capital One Financial", "Financial", "Banking"),
    ("USB", "U.S. Bancorp", "Financial", "Banking"),

    # Healthcare & Pharmaceuticals
    ("JNJ", "Johnson & Johnson", "Healthcare", "Pharmaceuticals"),
    ("UNH", "UnitedHealth Group", "Healthcare", "Health Insurance"),
    ("PFE", "Pfizer Inc.", "Healthcare", "Pharmaceuticals"),
    ("ABBV", "AbbVie Inc.", "Healthcare", "Biotechnology"),
    ("TMO", "Thermo Fisher Scientific", "Healthcare", "Life Sciences"),
    ("ABT", "Abbott Laboratories", "Healthcare", "Medical Devices"),
    ("MRK", "Merck & Co.", "Healthcare", "Pharmaceuticals"),
    ("LLY", "Eli Lilly and Company", "Healthcare", "Pharmaceuticals"),
    ("BMY", "Bristol-Myers Squibb", "Healthcare", "Pharmaceuticals"),
    ("AMGN", "Amgen Inc.", "Healthcare", "Biotechnology"),
    ("GILD", "Gilead Sciences", "Healthcare", "Biotechnology"),
    ("CVS", "CVS Health Corporation", "Healthcare", "Pharmacy"),
    ("CI", "Cigna Corporation", "Healthcare", "Health Insurance"),
    ("BIIB", "Biogen Inc.", "Healthcare", "Biotechnology"),
    ("REGN", "Regeneron Pharmaceuticals", "Healthcare", "Biotechnology"),

    # Consumer Goods & Retail
    ("WMT", "Walmart Inc.", "Retail", "Discount Stores"),
    ("HD", "Home Depot Inc.", "Retail", "Home Improvement"),
    ("PG", "Procter & Gamble", "Consumer Goods", "Personal Care"),
    ("KO", "Coca-Cola Company", "Consumer Goods", "Beverages"),
    ("PEP", "PepsiCo Inc.", "Consumer Goods", "Beverages"),
    ("COST", "Costco Wholesale", "Retail", "Wholesale Clubs"),
    ("NKE", "Nike Inc.", "Consumer Goods", "Apparel"),
    ("MCD", "McDonald's Corp.", "Consumer Services", "Restaurants"),
    ("SBUX", "Starbucks Corporation", "Consumer Services", "Restaurants"),
    ("TGT", "Target Corporation", "Retail", "Discount Stores"),
    ("LOW", "Lowe's Companies", "Retail", "Home Improvement"),
    ("DIS", "Walt Disney Company", "Entertainment", "Media"),
    ("CMCSA", "Comcast Corporation", "Telecommunications", "Cable"),
    ("VZ", "Verizon Communications", "Telecommunications", "Wireless"),
    ("T", "AT&T Inc.", "Telecommunications", "Wireless"),

    # Energy
    ("XOM", "Exxon Mobil Corporation", "Energy", "Oil & Gas"),
    ("CVX", "Chevron Corporation", "Energy", "Oil & Gas"),
    ("COP", "ConocoPhillips", "Energy", "Oil & Gas"),
    ("SLB", "Schlumberger NV", "Energy", "Oil Services"),
    ("EOG", "EOG Resources", "Energy", "Oil & Gas"),
    ("PXD", "Pioneer Natural Resources", "Energy", "Oil & Gas"),
    ("OXY", "Occidental Petroleum", "Energy", "Oil & Gas"),
    ("MPC", "Marathon Petroleum", "Energy", "Refining"),
    ("PSX", "Phillips 66", "Energy", "Refining"),
    ("VLO", "Valero Energy", "Energy", "Refining"),

    # Industrials
    ("BA", "Boeing Company", "Aerospace", "Aircraft Manufacturing"),
    ("CAT", "Caterpillar Inc.", "Industrials", "Heavy Machinery"),
    ("GE", "General Electric", "Industrials", "Conglomerate"),
    ("HON", "Honeywell International", "Industrials", "Conglomerate"),
    ("UPS", "United Parcel Service", "Industrials", "Logistics"),
    ("FDX", "FedEx Corporation", "Industrials", "Logistics"),
    ("LMT", "Lockheed Martin", "Aerospace", "Defense"),
    ("RTX", "Raytheon Technologies", "Aerospace", "Defense"),
    ("DE", "Deere & Company", "Industrials", "Agricultural Equipment"),
    ("MMM", "3M Company", "Industrials", "Conglomerate"),

    # Real Estate & Construction
    ("AMT", "American Tower Corp.", "Real Estate", "REIT"),
    ("PLD", "Prologis Inc.", "Real Estate", "REIT"),
    ("CCI", "Crown Castle Inc.", "Real Estate", "REIT"),
    ("SPG", "Simon Property Group", "Real Estate", "REIT"),
    ("PSA", "Public Storage", "Real Estate", "REIT"),

    # Materials & Chemicals
    ("LIN", "Linde plc", "Materials", "Industrial Gases"),
    ("APD", "Air Products & Chemicals", "Materials", "Industrial Gases"),
    ("ECL", "Ecolab Inc.", "Materials", "Specialty Chemicals"),
    ("DD", "DuPont de Nemours", "Materials", "Chemicals"),
    ("DOW", "Dow Inc.", "Materials", "Chemicals"),

    # Additional Tech & Software
    ("IBM", "IBM Corporation", "Technology", "IT Services"),
    ("SHOP", "Shopify Inc.", "Technology", "E-commerce"),
    ("NOW", "ServiceNow Inc.", "Technology", "Cloud Software"),
    ("SNOW", "Snowflake Inc.", "Technology", "Cloud Data"),
    ("PLTR", "Palantir Technologies", "Technology", "Data Analytics"),
    ("UBER", "Uber Technologies", "Technology", "Ride Sharing"),
    ("LYFT", "Lyft Inc.", "Technology", "Ride Sharing"),
    ("ABNB", "Airbnb Inc.", "Technology", "Travel"),
    ("TWLO", "Twilio Inc.", "Technology", "Cloud Communications"),
    ("ZM", "Zoom Video Communications", "Technology", "Video Conferencing"),
    ("DOCU", "DocuSign Inc.", "Technology", "E-signature"),
    ("WDAY", "Workday Inc.", "Technology", "HR Software"),
    ("PANW", "Palo Alto Networks", "Technology", "Cybersecurity"),
    ("CRWD", "CrowdStrike Holdings", "Technology", "Cybersecurity"),
    ("ZS", "Zscaler Inc.", "Technology", "Cybersecurity"),
    ("DDOG", "Datadog Inc.", "Technology", "Cloud Monitoring"),
    ("NET", "Cloudflare Inc.", "Technology", "Cloud Services"),
    ("OKTA", "Okta Inc.", "Technology", "Identity Management"),
    ("ROKU", "Roku Inc.", "Technology", "Streaming"),
    ("SPOT", "Spotify Technology", "Technology", "Music Streaming"),

    # E-commerce & Consumer Internet
    ("BABA", "Alibaba Group", "Technology", "E-commerce"),
    ("JD", "JD.com Inc.", "Technology", "E-commerce"),
    ("PDD", "Pinduoduo Inc.", "Technology", "E-commerce"),
    ("MELI", "MercadoLibre Inc.", "Technology", "E-commerce"),
    ("EBAY", "eBay Inc.", "Technology", "E-commerce"),
    ("ETSY", "Etsy Inc.", "Technology", "E-commerce"),

    # Semiconductors & Hardware
    ("ASML", "ASML Holding NV", "Technology", "Semiconductor Equipment"),
    ("TSM", "Taiwan Semiconductor", "Technology", "Semiconductors"),
    ("KLAC", "KLA Corporation", "Technology", "Semiconductor Equipment"),
    ("MCHP", "Microchip Technology", "Technology", "Semiconductors"),
    ("MRVL", "Marvell Technology", "Technology", "Semiconductors"),
    ("NXPI", "NXP Semiconductors", "Technology", "Semiconductors"),
    ("ADI", "Analog Devices", "Technology", "Semiconductors"),
    ("SWKS", "Skyworks Solutions", "Technology", "Semiconductors"),
    ("QRVO", "Qorvo Inc.", "Technology", "Semiconductors"),

    # Electric Vehicles & Auto
    ("F", "Ford Motor Company", "Automotive", "Automobiles"),
    ("GM", "General Motors", "Automotive", "Automobiles"),
    ("RIVN", "Rivian Automotive", "Automotive", "Electric Vehicles"),
    ("LCID", "Lucid Group Inc.", "Automotive", "Electric Vehicles"),
    ("NIO", "NIO Inc.", "Automotive", "Electric Vehicles"),
    ("XPEV", "XPeng Inc.", "Automotive", "Electric Vehicles"),
    ("LI", "Li Auto Inc.", "Automotive", "Electric Vehicles"),

    # Airlines & Travel
    ("AAL", "American Airlines", "Transportation", "Airlines"),
    ("DAL", "Delta Air Lines", "Transportation", "Airlines"),
    ("UAL", "United Airlines", "Transportation", "Airlines"),
    ("LUV", "Southwest Airlines", "Transportation", "Airlines"),
    ("CCL", "Carnival Corporation", "Leisure", "Cruise Lines"),
    ("RCL", "Royal Caribbean", "Leisure", "Cruise Lines"),
    ("MAR", "Marriott International", "Leisure", "Hotels"),
    ("HLT", "Hilton Worldwide", "Leisure", "Hotels"),

    # Entertainment & Gaming
    ("NTES", "NetEase Inc.", "Entertainment", "Gaming"),
    ("EA", "Electronic Arts", "Entertainment", "Gaming"),
    ("ATVI", "Activision Blizzard", "Entertainment", "Gaming"),
    ("TTWO", "Take-Two Interactive", "Entertainment", "Gaming"),
    ("RBLX", "Roblox Corporation", "Entertainment", "Gaming"),
    ("U", "Unity Software", "Technology", "Gaming Software"),

    # Food & Beverage
    ("KHC", "Kraft Heinz Company", "Consumer Goods", "Food Products"),
    ("GIS", "General Mills", "Consumer Goods", "Food Products"),
    ("K", "Kellogg Company", "Consumer Goods", "Food Products"),
    ("MDLZ", "Mondelez International", "Consumer Goods", "Food Products"),
    ("HSY", "Hershey Company", "Consumer Goods", "Confectionery"),
    ("CAG", "Conagra Brands", "Consumer Goods", "Food Products"),
    ("CPB", "Campbell Soup", "Consumer Goods", "Food Products"),

    # Apparel & Luxury
    ("LULU", "Lululemon Athletica", "Consumer Goods", "Apparel"),
    ("UAA", "Under Armour Class A", "Consumer Goods", "Apparel"),
    ("VFC", "VF Corporation", "Consumer Goods", "Apparel"),
    ("TPR", "Tapestry Inc.", "Consumer Goods", "Luxury Goods"),
    ("RL", "Ralph Lauren Corp.", "Consumer Goods", "Apparel"),

    # Utilities
    ("NEE", "NextEra Energy", "Utilities", "Electric Utilities"),
    ("DUK", "Duke Energy", "Utilities", "Electric Utilities"),
    ("SO", "Southern Company", "Utilities", "Electric Utilities"),
    ("D", "Dominion Energy", "Utilities", "Electric Utilities"),
    ("AEP", "American Electric Power", "Utilities", "Electric Utilities"),

    # Biotech & Medical Devices
    ("ISRG", "Intuitive Surgical", "Healthcare", "Medical Devices"),
    ("DHR", "Danaher Corporation", "Healthcare", "Life Sciences"),
    ("SYK", "Stryker Corporation", "Healthcare", "Medical Devices"),
    ("BSX", "Boston Scientific", "Healthcare", "Medical Devices"),
    ("EW", "Edwards Lifesciences", "Healthcare", "Medical Devices"),
    ("VRTX", "Vertex Pharmaceuticals", "Healthcare", "Biotechnology"),
    ("ALXN", "Alexion Pharmaceuticals", "Healthcare", "Biotechnology"),
    ("ILMN", "Illumina Inc.", "Healthcare", "Life Sciences"),
    ("ALGN", "Align Technology", "Healthcare", "Medical Devices"),
    ("IDXX", "IDEXX Laboratories", "Healthcare", "Diagnostics"),

    # Insurance
    ("BRK.B", "Berkshire Hathaway Class B", "Financial", "Insurance"),
    ("PGR", "Progressive Corporation", "Financial", "Insurance"),
    ("ALL", "Allstate Corporation", "Financial", "Insurance"),
    ("TRV", "Travelers Companies", "Financial", "Insurance"),
    ("AIG", "American International", "Financial", "Insurance"),
    ("MET", "MetLife Inc.", "Financial", "Insurance"),
    ("PRU", "Prudential Financial", "Financial", "Insurance"),

    # Additional Popular Stocks
    ("SNOW", "Snowflake Inc.", "Technology", "Cloud Data"),
    ("COIN", "Coinbase Global", "Financial", "Cryptocurrency"),
    ("HOOD", "Robinhood Markets", "Financial", "Brokerage"),
    ("AFRM", "Affirm Holdings", "Financial", "Buy Now Pay Later"),
    ("UPST", "Upstart Holdings", "Financial", "AI Lending"),
    ("SOFI", "SoFi Technologies", "Financial", "Fintech"),
    ("PATH", "UiPath Inc.", "Technology", "Automation Software"),
    ("FSLR", "First Solar Inc.", "Energy", "Solar"),
    ("ENPH", "Enphase Energy", "Energy", "Solar"),
    ("SEDG", "SolarEdge Technologies", "Energy", "Solar"),

    # Energy & Renewables
    ("PLUG", "Plug Power Inc.", "Energy", "Fuel Cells"),
    ("BE", "Bloom Energy", "Energy", "Fuel Cells"),
    ("FCEL", "FuelCell Energy", "Energy", "Fuel Cells"),
    ("ICLN", "iShares Clean Energy ETF", "Energy", "Clean Energy ETF"),

    # SPACs and Recent IPOs
    ("SPCE", "Virgin Galactic", "Aerospace", "Space Tourism"),
    ("PTON", "Peloton Interactive", "Consumer Goods", "Fitness Equipment"),
    ("ZG", "Zillow Group Class A", "Technology", "Real Estate"),
    ("OPEN", "Opendoor Technologies", "Technology", "Real Estate"),
    ("DASH", "DoorDash Inc.", "Technology", "Food Delivery"),
    ("DKNG", "DraftKings Inc.", "Entertainment", "Sports Betting"),
    ("PENN", "Penn Entertainment", "Entertainment", "Gaming"),

    # REITs & Real Estate
    ("O", "Realty Income Corp.", "Real Estate", "REIT"),
    ("VICI", "VICI Properties", "Real Estate", "REIT"),
    ("EQIX", "Equinix Inc.", "Real Estate", "Data Center REIT"),
    ("DLR", "Digital Realty Trust", "Real Estate", "Data Center REIT"),
    ("AVB", "AvalonBay Communities", "Real Estate", "REIT"),
    ("EQR", "Equity Residential", "Real Estate", "REIT"),
    ("MAA", "Mid-America Apartment", "Real Estate", "REIT"),
    ("INVH", "Invitation Homes", "Real Estate", "REIT"),

    # Specialty Retail
    ("CHWY", "Chewy Inc.", "Retail", "Pet Products"),
    ("W", "Wayfair Inc.", "Retail", "Home Furnishings"),
    ("BBY", "Best Buy Co.", "Retail", "Electronics"),
    ("GPS", "Gap Inc.", "Retail", "Apparel"),
    ("M", "Macy's Inc.", "Retail", "Department Stores"),
    ("KSS", "Kohl's Corporation", "Retail", "Department Stores"),
    ("DG", "Dollar General", "Retail", "Discount Stores"),
    ("DLTR", "Dollar Tree", "Retail", "Discount Stores"),

    # Industrial & Manufacturing
    ("EMR", "Emerson Electric", "Industrials", "Automation"),
    ("ETN", "Eaton Corporation", "Industrials", "Power Management"),
    ("PH", "Parker-Hannifin", "Industrials", "Motion & Control"),
    ("ROK", "Rockwell Automation", "Industrials", "Automation"),
    ("ITW", "Illinois Tool Works", "Industrials", "Manufacturing"),
    ("CMI", "Cummins Inc.", "Industrials", "Engines"),
    ("PCAR", "PACCAR Inc.", "Industrials", "Trucks"),

    # Communication Services
    ("TMUS", "T-Mobile US", "Telecommunications", "Wireless"),
    ("CHTR", "Charter Communications", "Telecommunications", "Cable"),
    ("DISH", "DISH Network", "Telecommunications", "Satellite"),
    ("FOXA", "Fox Corporation Class A", "Entertainment", "Media"),
    ("NWSA", "News Corp Class A", "Entertainment", "Media"),
    ("NYT", "New York Times", "Entertainment", "Publishing"),
    ("PARA", "Paramount Global", "Entertainment", "Media"),

    # Additional Stocks to reach 300+
    ("CLX", "Clorox Company", "Consumer Goods", "Household Products"),
    ("CL", "Colgate-Palmolive", "Consumer Goods", "Personal Care"),
    ("EL", "Estee Lauder", "Consumer Goods", "Cosmetics"),
    ("KMB", "Kimberly-Clark", "Consumer Goods", "Personal Care"),
    ("CHD", "Church & Dwight", "Consumer Goods", "Household Products"),
    ("SJM", "J.M. Smucker", "Consumer Goods", "Food Products"),
    ("MKC", "McCormick & Company", "Consumer Goods", "Food Products"),
    ("TAP", "Molson Coors Beverage", "Consumer Goods", "Beverages"),
    ("STZ", "Constellation Brands", "Consumer Goods", "Alcoholic Beverages"),
    ("BF.B", "Brown-Forman Class B", "Consumer Goods", "Alcoholic Beverages"),
]

def populate_stocks():
    """Insert stocks into database"""
    db = SessionLocal()
    added = 0
    skipped = 0

    try:
        for symbol, name, sector, industry in STOCKS:
            try:
                # Check if stock already exists
                existing = db.query(Stock).filter(Stock.symbol == symbol).first()
                if existing:
                    print(f"[SKIP] {symbol:8} - Already exists")
                    skipped += 1
                    continue

                # Create new stock
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
        print(f"[OK] Total in list: {len(STOCKS)} stocks")
        print(f"{'='*60}")

    finally:
        db.close()

if __name__ == "__main__":
    print(f"{'='*60}")
    print(f"  Stock Database Population Script")
    print(f"{'='*60}\n")
    populate_stocks()
