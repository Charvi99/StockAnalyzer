"""
Add 300 Popular US Stocks to Database

This script adds the most traded US stocks to the database
for ML training.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass123@database:5432/stock_analyzer')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


# Top 300 US stocks by market cap and trading volume
STOCKS = [
    # Technology
    ("AAPL", "Apple Inc.", "Technology", "Consumer Electronics"),
    ("MSFT", "Microsoft Corporation", "Technology", "Software"),
    ("GOOGL", "Alphabet Inc.", "Technology", "Internet Services"),
    ("GOOG", "Alphabet Inc. Class C", "Technology", "Internet Services"),
    ("AMZN", "Amazon.com Inc.", "Consumer Cyclical", "E-commerce"),
    ("TSLA", "Tesla Inc.", "Automotive", "Electric Vehicles"),
    ("META", "Meta Platforms Inc.", "Technology", "Social Media"),
    ("NVDA", "NVIDIA Corporation", "Technology", "Semiconductors"),
    ("AMD", "Advanced Micro Devices", "Technology", "Semiconductors"),
    ("INTC", "Intel Corporation", "Technology", "Semiconductors"),
    ("CRM", "Salesforce Inc.", "Technology", "Software"),
    ("ORCL", "Oracle Corporation", "Technology", "Software"),
    ("ADBE", "Adobe Inc.", "Technology", "Software"),
    ("ACN", "Accenture plc", "Technology", "IT Services"),
    ("CSCO", "Cisco Systems", "Technology", "Networking"),
    ("AVGO", "Broadcom Inc.", "Technology", "Semiconductors"),
    ("TXN", "Texas Instruments", "Technology", "Semiconductors"),
    ("QCOM", "Qualcomm Inc.", "Technology", "Semiconductors"),
    ("IBM", "IBM", "Technology", "IT Services"),
    ("AMAT", "Applied Materials", "Technology", "Semiconductors"),
    ("MU", "Micron Technology", "Technology", "Semiconductors"),
    ("NOW", "ServiceNow Inc.", "Technology", "Software"),
    ("SHOP", "Shopify Inc.", "Technology", "E-commerce"),
    ("SQ", "Block Inc.", "Technology", "Financial Services"),
    ("PYPL", "PayPal Holdings", "Technology", "Financial Services"),
    ("INTU", "Intuit Inc.", "Technology", "Software"),
    ("SNOW", "Snowflake Inc.", "Technology", "Cloud Computing"),
    ("PLTR", "Palantir Technologies", "Technology", "Software"),
    ("UBER", "Uber Technologies", "Technology", "Ride Sharing"),
    ("LYFT", "Lyft Inc.", "Technology", "Ride Sharing"),
    ("DOCU", "DocuSign Inc.", "Technology", "Software"),
    ("ZM", "Zoom Video Communications", "Technology", "Communications"),
    ("TWLO", "Twilio Inc.", "Technology", "Cloud Communications"),
    ("ROKU", "Roku Inc.", "Technology", "Consumer Electronics"),
    ("SNAP", "Snap Inc.", "Technology", "Social Media"),
    ("PINS", "Pinterest Inc.", "Technology", "Social Media"),
    ("TTD", "The Trade Desk", "Technology", "Advertising"),
    ("DDOG", "Datadog Inc.", "Technology", "Software"),
    ("NET", "Cloudflare Inc.", "Technology", "Cloud Computing"),
    ("OKTA", "Okta Inc.", "Technology", "Software"),
    ("GTLS", "GitLab Inc.", "Technology", "Software"),

    # Financial Services
    ("BRK.B", "Berkshire Hathaway", "Financial Services", "Conglomerate"),
    ("JPM", "JPMorgan Chase & Co.", "Financial Services", "Banking"),
    ("V", "Visa Inc.", "Financial Services", "Payment Processing"),
    ("MA", "Mastercard Inc.", "Financial Services", "Payment Processing"),
    ("BAC", "Bank of America", "Financial Services", "Banking"),
    ("WFC", "Wells Fargo", "Financial Services", "Banking"),
    ("GS", "Goldman Sachs", "Financial Services", "Investment Banking"),
    ("MS", "Morgan Stanley", "Financial Services", "Investment Banking"),
    ("C", "Citigroup Inc.", "Financial Services", "Banking"),
    ("AXP", "American Express", "Financial Services", "Credit Services"),
    ("BLK", "BlackRock Inc.", "Financial Services", "Asset Management"),
    ("SCHW", "Charles Schwab", "Financial Services", "Brokerage"),
    ("IPC", "Interactive Brokers", "Financial Services", "Brokerage"),
    ("SPGI", "S&P Global", "Financial Services", "Financial Data"),
    ("MCO", "Moody's Corporation", "Financial Services", "Credit Ratings"),
    ("ICE", "Intercontinental Exchange", "Financial Services", "Financial Data"),
    ("CME", "CME Group", "Financial Services", "Futures Exchange"),
    ("MMC", "Marsh & McLennan", "Financial Services", "Insurance"),
    ("AON", "Aon plc", "Financial Services", "Insurance"),
    ("TRV", "The Travelers Companies", "Financial Services", "Insurance"),
    ("CB", "Chubb Limited", "Financial Services", "Insurance"),
    ("AIG", "American International Group", "Financial Services", "Insurance"),
    ("MET", "MetLife Inc.", "Financial Services", "Insurance"),
    ("PRU", "Prudential Financial", "Financial Services", "Insurance"),
    ("LNC", "Lincoln National", "Financial Services", "Insurance"),
    ("DFS", "Discover Financial", "Financial Services", "Credit Services"),
    ("COF", "Capital One Financial", "Financial Services", "Banking"),

    # Healthcare
    ("JNJ", "Johnson & Johnson", "Healthcare", "Pharmaceuticals"),
    ("UNH", "UnitedHealth Group", "Healthcare", "Health Insurance"),
    ("PFE", "Pfizer Inc.", "Healthcare", "Pharmaceuticals"),
    ("ABBV", "AbbVie Inc.", "Healthcare", "Pharmaceuticals"),
    ("MRK", "Merck & Co.", "Healthcare", "Pharmaceuticals"),
    ("TMO", "Thermo Fisher Scientific", "Healthcare", "Laboratory Equipment"),
    ("ABT", "Abbott Laboratories", "Healthcare", "Medical Devices"),
    ("DHR", "Danaher Corporation", "Healthcare", "Medical Instruments"),
    ("BMY", "Bristol-Myers Squibb", "Healthcare", "Pharmaceuticals"),
    ("AMGN", "Amgen Inc.", "Healthcare", "Biotechnology"),
    ("GILD", "Gilead Sciences", "Healthcare", "Biotechnology"),
    ("LLY", "Eli Lilly and Company", "Healthcare", "Pharmaceuticals"),
    ("CVS", "CVS Health", "Healthcare", "Pharmacy"),
    ("MDT", "Medtronic plc", "Healthcare", "Medical Devices"),
    ("ISRG", "Intuitive Surgical", "Healthcare", "Medical Robotics"),
    ("BDX", "Becton Dickinson", "Healthcare", "Medical Supplies"),
    ("IQV", "IQVIA Holdings", "Healthcare", "Clinical Research"),
    ("REGN", "Regeneron Pharmaceuticals", "Healthcare", "Biotechnology"),
    ("VRTX", "Vertex Pharmaceuticals", "Healthcare", "Biotechnology"),
    ("BIIB", "Biogen Inc.", "Healthcare", "Biotechnology"),
    ("ALXN", "Alexion Pharmaceuticals", "Healthcare", "Biotechnology"),
    ("ILMN", "Illumina Inc.", "Healthcare", "Genetic Sequencing"),
    ("IDXX", "Idexx Laboratories", "Healthcare", "Diagnostics"),

    # Consumer Defensive
    ("WMT", "Walmart Inc.", "Consumer Defensive", "Retail"),
    ("PG", "Procter & Gamble", "Consumer Defensive", "Household Products"),
    ("KO", "Coca-Cola Company", "Consumer Defensive", "Beverages"),
    ("PEP", "PepsiCo Inc.", "Consumer Defensive", "Beverages"),
    ("COST", "Costco Wholesale", "Consumer Defensive", "Retail"),
    ("HD", "Home Depot Inc.", "Consumer Defensive", "Home Improvement"),
    ("MCD", "McDonald's", "Consumer Defensive", "Restaurants"),
    ("NKE", "Nike Inc.", "Consumer Defensive", "Apparel"),
    ("SBUX", "Starbucks Corporation", "Consumer Defensive", "Restaurants"),
    ("LOW", "Lowe's Companies", "Consumer Defensive", "Home Improvement"),
    ("TJX", "TJX Companies", "Consumer Defensive", "Retail"),
    ("DG", "Dollar General", "Consumer Defensive", "Retail"),
    ("DLTR", "Dollar Tree", "Consumer Defensive", "Retail"),
    ("Target", "Target Corporation", "Consumer Defensive", "Retail"),
    ("CL", "Colgate-Palmolive", "Consumer Defensive", "Household Products"),
    ("KMB", "Kimberly-Clark", "Consumer Defensive", "Household Products"),
    ("C", "C", "Consumer Defensive", "Tobacco"),
    ("MO", "Altria Group", "Consumer Defensive", "Tobacco"),
    ("PM", "Philip Morris International", "Consumer Defensive", "Tobacco"),
    ("BST", "Brown-Forman Corporation", "Consumer Defensive", "Beverages"),
    ("MNST", "Monster Beverage", "Consumer Defensive", "Beverages"),
    ("K", "Kellogg Company", "Consumer Defensive", "Food"),
    ("GIS", "General Mills", "Consumer Defensive", "Food"),
    ("CPB", "Campbell Soup", "Consumer Defensive", "Food"),
    ("HSY", "Hershey Company", "Consumer Defensive", "Food"),
    ("KHC", "Kraft Heinz", "Consumer Defensive", "Food"),
    ("CLX", "Clorox Company", "Consumer Defensive", "Household Products"),

    # Consumer Cyclical
    ("TSLA", "Tesla Inc.", "Consumer Cyclical", "Auto Manufacturers"),
    ("AMZN", "Amazon.com Inc.", "Consumer Cyclical", "Internet Retail"),
    ("HD", "Home Depot Inc.", "Consumer Cyclical", "Home Improvement Retail"),
    ("MCD", "McDonald's", "Consumer Cyclical", "Restaurants"),
    ("NKE", "Nike Inc.", "Consumer Cyclical", "Apparel"),
    ("SBUX", "Starbucks", "Consumer Cyclical", "Restaurants"),
    ("LOW", "Lowe's", "Consumer Cyclical", "Home Improvement Retail"),
    ("TJX", "TJX Companies", "Consumer Cyclical", "Apparel Retail"),
    ("BKNG", "Booking Holdings", "Consumer Cyclical", "Travel Services"),
    ("MAR", "Marriott International", "Consumer Cyclical", "Hotels & Resorts"),
    ("HLT", "Hilton Worldwide", "Consumer Cyclical", "Hotels & Resorts"),
    ("EXPE", "Expedia Group", "Consumer Cyclical", "Travel Services"),
    ("CCL", "Carnival Corporation", "Consumer Cyclical", "Cruise Lines"),
    ("RCL", "Royal Caribbean Cruises", "Consumer Cyclical", "Cruise Lines"),
    ("NCLH", "Norwegian Cruise Line", "Consumer Cyclical", "Cruise Lines"),
    ("GM", "General Motors", "Consumer Cyclical", "Auto Manufacturers"),
    ("F", "Ford Motor", "Consumer Cyclical", "Auto Manufacturers"),
    ("T", "AT&T Inc.", "Communication Services", "Telecom"),

    # Energy
    ("XOM", "Exxon Mobil", "Energy", "Oil & Gas Integrated"),
    ("CVX", "Chevron Corporation", "Energy", "Oil & Gas Integrated"),
    ("COP", "ConocoPhillips", "Energy", "Oil & Gas E&P"),
    ("SLB", "Schlumberger NV", "Energy", "Oilfield Services"),
    ("HAL", "Halliburton Company", "Energy", "Oilfield Services"),
    ("EOG", "EOG Resources", "Energy", "Oil & Gas E&P"),
    ("MPC", "Marathon Petroleum", "Energy", "Refining"),
    ("PSX", "Phillips 66", "Energy", "Refining"),
    ("VLO", "Valero Energy", "Energy", "Refining"),
    ("OXY", "Occidental Petroleum", "Energy", "Oil & Gas E&P"),
    ("DVN", "Devon Energy", "Energy", "Oil & Gas E&P"),
    ("PXD", "Pioneer Natural Resources", "Energy", "Oil & Gas E&P"),
    ("FTI", "TechnipFMC", "Energy", "Oilfield Services"),
    ("BKR", "Baker Hughes", "Energy", "Oilfield Services"),
    ("WMB", "Williams Companies", "Energy", "Gas Pipelines"),
    ("ET", "Energy Transfer", "Energy", "Gas Pipelines"),
    ("KMI", "Kinder Morgan", "Energy", "Gas Pipelines"),

    # Industrials
    ("CAT", "Caterpillar Inc.", "Industrials", "Construction Machinery"),
    ("HON", "Honeywell International", "Industrials", "Conglomerate"),
    ("UNP", "Union Pacific", "Industrials", "Railroads"),
    ("BA", "Boeing Company", "Industrials", "Aerospace & Defense"),
    ("UPS", "United Parcel Service", "Industrials", "Delivery Services"),
    ("RTX", "Raytheon Technologies", "Industrials", "Aerospace & Defense"),
    ("LMT", "Lockheed Martin", "Industrials", "Aerospace & Defense"),
    ("GD", "General Dynamics", "Industrials", "Aerospace & Defense"),
    ("NOC", "Northrop Grumman", "Industrials", "Aerospace & Defense"),
    ("DE", "Deere & Company", "Industrials", "Agricultural Machinery"),
    ("MMM", "3M Company", "Industrials", "Conglomerate"),
    ("GE", "General Electric", "Industrials", "Conglomerate"),
    ("EMR", "Emerson Electric", "Industrials", "Industrial Machinery"),
    ("ITW", "Illinois Tool Works", "Industrials", "Industrial Machinery"),
    ("CCI", "Crown Castle", "Industrials", "Telecom Towers"),
    ("AMT", "American Tower", "Industrials", "Telecom Towers"),
    ("CBRE", "CBRE Group", "Industrials", "Real Estate Services"),
    ("CSX", "CSX Corporation", "Industrials", "Railroads"),
    ("NSC", "Norfolk Southern", "Industrials", "Railroads"),
    ("KSU", "Kansas City Southern", "Industrials", "Railroads"),
    ("FDX", "FedEx Corporation", "Industrials", "Delivery Services"),
    ("DAL", "Delta Air Lines", "Industrials", "Airlines"),
    ("UAL", "United Airlines", "Industrials", "Airlines"),
    ("AAL", "American Airlines", "Industrials", "Airlines"),
    ("LUV", "Southwest Airlines", "Industrials", "Airlines"),
    ("JNJ", "Johnson & Johnson", "Industrials", "Airlines"),
    ("ALK", "Alaska Air Group", "Industrials", "Airlines"),
    ("Save", "Spirit Airlines", "Industrials", "Airlines"),
    ("URI", "United Rentals", "Industrials", "Equipment Rental"),
    ("RSG", "Republic Services", "Industrials", "Waste Management"),
    ("WM", "Waste Management", "Industrials", "Waste Management"),
    ("DOW", "Dow Inc.", "Industrials", "Chemicals"),

    # Utilities
    ("NEE", "NextEra Energy", "Utilities", "Electric Utilities"),
    ("DUK", "Duke Energy", "Utilities", "Electric Utilities"),
    ("SO", "Southern Company", "Utilities", "Electric Utilities"),
    ("D", "Dominion Energy", "Utilities", "Electric Utilities"),
    ("EXC", "Exelon Corporation", "Utilities", "Electric Utilities"),
    ("AEP", "American Electric Power", "Utilities", "Electric Utilities"),
    ("XEL", "Xcel Energy", "Utilities", "Electric Utilities"),
    ("WEC", "WEC Energy Group", "Utilities", "Electric Utilities"),
    ("PEG", "Public Service Enterprise", "Utilities", "Electric Utilities"),
    ("ED", "Consolidated Edison", "Utilities", "Electric Utilities"),
    ("AWK", "American Water Works", "Utilities", "Water Utilities"),
    ("WTRG", "Essential Utilities", "Utilities", "Water Utilities"),

    # Real Estate
    ("AMT", "American Tower", "Real Estate", "REIT"),
    ("PLD", "Prologis", "Real Estate", "REIT"),
    ("CCI", "Crown Castle", "Real Estate", "REIT"),
    ("EQIX", "Equinix", "Real Estate", "REIT"),
    ("DLR", "Digital Realty", "Real Estate", "REIT"),
    ("SPG", "Simon Property Group", "Real Estate", "REIT"),
    ("O", "Realty Income", "Real Estate", "REIT"),
    ("VNQ", "Vanguard Real Estate", "Real Estate", "REIT"),
    ("WELL", "Welltower Inc.", "Real Estate", "REIT"),
    ("VICI", "VICI Properties", "Real Estate", "REIT"),
    ("BXP", "Boston Properties", "Real Estate", "REIT"),
    ("CBRE", "CBRE Group", "Real Estate", "Real Estate Services"),

    # Materials
    ("LIN", "Linde plc", "Materials", "Chemicals"),
    ("APD", "Air Products and Chemicals", "Materials", "Chemicals"),
    ("SHW", "Sherwin-Williams", "Materials", "Chemicals"),
    ("DD", "DuPont de Nemours", "Materials", "Chemicals"),
    ("DOW", "Dow Inc.", "Materials", "Chemicals"),
    ("FCX", "Freeport-McMoRan", "Materials", "Copper Mining"),
    ("NEM", "Newmont Corporation", "Materials", "Gold Mining"),
    ("RIO", "Rio Tinto", "Materials", "Mining"),
    ("BHP", "BHP Group", "Materials", "Mining"),
    ("VALE", "Vale SA", "Materials", "Mining"),
    ("PPG", "PPG Industries", "Materials", "Chemicals"),
    ("ECL", "Ecolab Inc.", "Materials", "Chemicals"),
    ("IP", "International Paper", "Materials", "Paper"),
    ("PKG", "Packaging Corporation", "Materials", "Paper"),
    ("NUE", "Nucor Corporation", "Materials", "Steel"),
    ("STLD", "Steel Dynamics", "Materials", "Steel"),

    # Communication Services
    ("GOOGL", "Alphabet Inc.", "Communication Services", "Internet"),
    ("META", "Meta Platforms", "Communication Services", "Social Media"),
    ("T", "AT&T Inc.", "Communication Services", "Telecom"),
    ("VZ", "Verizon Communications", "Communication Services", "Telecom"),
    ("DIS", "Walt Disney Company", "Communication Services", "Entertainment"),
    ("CMCSA", "Comcast Corporation", "Communication Services", "Cable"),
    ("NFLX", "Netflix Inc.", "Communication Services", "Streaming"),
    ("TWX", "Warner Bros Discovery", "Communication Services", "Entertainment"),
    ("FOX", "Fox Corporation", "Communication Services", "Media"),
    ("FOXA", "Fox Corporation Class A", "Communication Services", "Media"),
    ("TMUS", "T-Mobile US", "Communication Services", "Telecom"),

    # Additional Tech
    ("AMD", "Advanced Micro Devices", "Technology", "Semiconductors"),
    ("INTC", "Intel Corporation", "Technology", "Semiconductors"),
    ("QCOM", "Qualcomm Inc.", "Technology", "Semiconductors"),
    ("TXN", "Texas Instruments", "Technology", "Semiconductors"),
    ("MU", "Micron Technology", "Technology", "Semiconductors"),
    ("AMAT", "Applied Materials", "Technology", "Semiconductors"),
    ("LRCX", "Lam Research", "Technology", "Semiconductors"),
    ("KLAC", "KLA Corporation", "Technology", "Semiconductors"),
    ("ASML", "ASML Holding", "Technology", "Semiconductors"),
    ("SOXX", "iShares Semiconductor ETF", "Technology", "ETF"),

    # More Healthcare
    ("JNJ", "Johnson & Johnson", "Healthcare", "Pharmaceuticals"),
    ("UNH", "UnitedHealth Group", "Healthcare", "Health Insurance"),
    ("PFE", "Pfizer Inc.", "Healthcare", "Pharmaceuticals"),
    ("ABBV", "AbbVie Inc.", "Healthcare", "Pharmaceuticals"),
    ("MRK", "Merck & Co.", "Healthcare", "Pharmaceuticals"),
    ("TMO", "Thermo Fisher", "Healthcare", "Lab Equipment"),
    ("ABT", "Abbott Labs", "Healthcare", "Medical Devices"),
    ("DHR", "Danaher", "Healthcare", "Medical Instruments"),
    ("BMY", "Bristol-Myers Squibb", "Healthcare", "Pharmaceuticals"),
    ("AMGN", "Amgen Inc.", "Healthcare", "Biotechnology"),

    # ETFs
    ("SPY", "SPDR S&P 500 ETF", "ETF", "Large Cap"),
    ("QQQ", "Invesco QQQ Trust", "ETF", "Technology"),
    ("IWM", "iShares Russell 2000", "ETF", "Small Cap"),
    ("VTI", "Vanguard Total Stock Market", "ETF", "Total Market"),
    ("VWO", "Vanguard Emerging Markets", "ETF", "Emerging Markets"),
    ("VEA", "Vanguard FTSE Developed", "ETF", "International"),
    ("BND", "Vanguard Total Bond Market", "ETF", "Bonds"),
    ("GLD", "SPDR Gold Shares", "ETF", "Gold"),
    ("SLV", "iShares Silver Trust", "ETF", "Silver"),
    ("TLT", "iShares 20+ Year Treasury", "ETF", "Long Term Treasury"),

    # Additional Stocks
    ("COIN", "Coinbase Global", "Financial Services", "Cryptocurrency"),
    ("HOOD", "Robinhood Markets", "Financial Services", "Brokerage"),
    ("RBLX", "Roblox Corporation", "Technology", "Gaming"),
    ("AFRM", "Affirm Holdings", "Financial Services", "Payments"),
    ("SOFI", "SoFi Technologies", "Financial Services", "Fintech"),
    ("UPST", "Upstart Holdings", "Financial Services", "AI Lending"),
    ("LCID", "Lucid Group", "Automotive", "Electric Vehicles"),
    ("RIVN", "Rivian Automotive", "Automotive", "Electric Vehicles"),
    ("CHPT", "ChargePoint Holdings", "Industrials", "EV Charging"),
    ("EVGO", "EVgo Inc.", "Industrials", "EV Charging"),
    ("ENPH", "Enphase Energy", "Technology", "Solar Energy"),
    ("SEDG", "SolarEdge Technologies", "Technology", "Solar Energy"),
    ("RUN", "Sunrun Inc.", "Technology", "Solar Energy"),
    ("FSLR", "First Solar", "Technology", "Solar Energy"),
    ("BE", "Bloom Energy", "Technology", "Fuel Cells"),
    ("PLUG", "Plug Power", "Technology", "Fuel Cells"),
    ("BLOK", "BlackRock Bitcoin Trust", "Financial Services", "Bitcoin ETF"),
    ("IBIT", "iShares Bitcoin Trust", "Financial Services", "Bitcoin ETF"),
    ("FBTC", "Fidelity Wise Origin Bitcoin", "Financial Services", "Bitcoin ETF"),
]


def main():
    """Add all stocks to database"""
    db = SessionLocal()

    try:
        # Add stocks
        added = 0
        skipped = 0

        for symbol, name, sector, industry in STOCKS:
            # Check if stock already exists
            result = db.execute(
                text("SELECT id FROM stocks WHERE symbol = :symbol"),
                {'symbol': symbol}
            ).fetchone()

            if result:
                skipped += 1
            else:
                db.execute(
                    text("""
                        INSERT INTO stocks (symbol, name, sector, industry, is_tracked)
                        VALUES (:symbol, :name, :sector, :industry, true)
                    """),
                    {'symbol': symbol, 'name': name, 'sector': sector, 'industry': industry}
                )
                added += 1

                if added % 50 == 0:
                    print(f"Added {added} stocks...")
                    db.commit()

        db.commit()

        print(f"\n✅ Successfully added {added} new stocks")
        print(f"⏭️  Skipped {skipped} existing stocks")

        # Show total count
        result = db.execute(text("SELECT COUNT(*) FROM stocks")).fetchone()
        print(f"📊 Total stocks in database: {result[0]}")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
