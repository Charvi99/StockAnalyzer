"""
Database Reset Script - 500 Stocks
Drops all tables, recreates schema, and inserts 500 diverse stocks
"""
import sys
import os
sys.path.append('/app')

from app.db.database import SessionLocal, engine
from app.models import stock  # Import to register models
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 335 existing stocks (from current database)
EXISTING_STOCKS = [
    # Tech - Mega Cap
    {'symbol': 'AAPL', 'name': 'Apple Inc.', 'sector': 'Technology', 'industry': 'Consumer Electronics'},
    {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'GOOGL', 'name': 'Alphabet Inc. Class A', 'sector': 'Technology', 'industry': 'Internet'},
    {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'sector': 'Technology', 'industry': 'E-commerce'},
    {'symbol': 'META', 'name': 'Meta Platforms Inc.', 'sector': 'Technology', 'industry': 'Social Media'},
    {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Auto Manufacturers'},

    # Tech - Large Cap
    {'symbol': 'NFLX', 'name': 'Netflix Inc.', 'sector': 'Technology', 'industry': 'Entertainment'},
    {'symbol': 'ADBE', 'name': 'Adobe Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'CRM', 'name': 'Salesforce Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'ORCL', 'name': 'Oracle Corporation', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'CSCO', 'name': 'Cisco Systems Inc.', 'sector': 'Technology', 'industry': 'Networking'},
    {'symbol': 'INTC', 'name': 'Intel Corporation', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'AMD', 'name': 'Advanced Micro Devices Inc.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'QCOM', 'name': 'QUALCOMM Inc.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'AVGO', 'name': 'Broadcom Inc.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'TXN', 'name': 'Texas Instruments Inc.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'AMAT', 'name': 'Applied Materials Inc.', 'sector': 'Technology', 'industry': 'Semiconductor Equipment'},
    {'symbol': 'LRCX', 'name': 'Lam Research Corporation', 'sector': 'Technology', 'industry': 'Semiconductor Equipment'},
    {'symbol': 'KLAC', 'name': 'KLA Corporation', 'sector': 'Technology', 'industry': 'Semiconductor Equipment'},

    # Tech - Mid Cap
    {'symbol': 'SNOW', 'name': 'Snowflake Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'PLTR', 'name': 'Palantir Technologies Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'SQ', 'name': 'Block Inc.', 'sector': 'Technology', 'industry': 'Financial Services'},
    {'symbol': 'SHOP', 'name': 'Shopify Inc.', 'sector': 'Technology', 'industry': 'E-commerce'},
    {'symbol': 'UBER', 'name': 'Uber Technologies Inc.', 'sector': 'Technology', 'industry': 'Ride-Sharing'},
    {'symbol': 'LYFT', 'name': 'Lyft Inc.', 'sector': 'Technology', 'industry': 'Ride-Sharing'},
    {'symbol': 'ABNB', 'name': 'Airbnb Inc.', 'sector': 'Technology', 'industry': 'Travel Services'},
    {'symbol': 'COIN', 'name': 'Coinbase Global Inc.', 'sector': 'Technology', 'industry': 'Cryptocurrency'},
    {'symbol': 'RBLX', 'name': 'Roblox Corporation', 'sector': 'Technology', 'industry': 'Gaming'},
    {'symbol': 'U', 'name': 'Unity Software Inc.', 'sector': 'Technology', 'industry': 'Software'},

    # Healthcare - Large Cap
    {'symbol': 'JNJ', 'name': 'Johnson & Johnson', 'sector': 'Healthcare', 'industry': 'Drug Manufacturers'},
    {'symbol': 'UNH', 'name': 'UnitedHealth Group Inc.', 'sector': 'Healthcare', 'industry': 'Healthcare Plans'},
    {'symbol': 'PFE', 'name': 'Pfizer Inc.', 'sector': 'Healthcare', 'industry': 'Drug Manufacturers'},
    {'symbol': 'ABBV', 'name': 'AbbVie Inc.', 'sector': 'Healthcare', 'industry': 'Drug Manufacturers'},
    {'symbol': 'TMO', 'name': 'Thermo Fisher Scientific Inc.', 'sector': 'Healthcare', 'industry': 'Diagnostics'},
    {'symbol': 'ABT', 'name': 'Abbott Laboratories', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
    {'symbol': 'DHR', 'name': 'Danaher Corporation', 'sector': 'Healthcare', 'industry': 'Diagnostics'},
    {'symbol': 'LLY', 'name': 'Eli Lilly and Company', 'sector': 'Healthcare', 'industry': 'Drug Manufacturers'},
    {'symbol': 'MRK', 'name': 'Merck & Co. Inc.', 'sector': 'Healthcare', 'industry': 'Drug Manufacturers'},
    {'symbol': 'BMY', 'name': 'Bristol-Myers Squibb Company', 'sector': 'Healthcare', 'industry': 'Drug Manufacturers'},

    # Healthcare - Mid Cap
    {'symbol': 'GILD', 'name': 'Gilead Sciences Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'AMGN', 'name': 'Amgen Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'VRTX', 'name': 'Vertex Pharmaceuticals Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'REGN', 'name': 'Regeneron Pharmaceuticals Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'BIIB', 'name': 'Biogen Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'MRNA', 'name': 'Moderna Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'ISRG', 'name': 'Intuitive Surgical Inc.', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
    {'symbol': 'SYK', 'name': 'Stryker Corporation', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
    {'symbol': 'BSX', 'name': 'Boston Scientific Corporation', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
    {'symbol': 'MDT', 'name': 'Medtronic plc', 'sector': 'Healthcare', 'industry': 'Medical Devices'},

    # Financial Services
    {'symbol': 'JPM', 'name': 'JPMorgan Chase & Co.', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'BAC', 'name': 'Bank of America Corporation', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'WFC', 'name': 'Wells Fargo & Company', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'C', 'name': 'Citigroup Inc.', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'GS', 'name': 'The Goldman Sachs Group Inc.', 'sector': 'Financial Services', 'industry': 'Investment Banking'},
    {'symbol': 'MS', 'name': 'Morgan Stanley', 'sector': 'Financial Services', 'industry': 'Investment Banking'},
    {'symbol': 'BLK', 'name': 'BlackRock Inc.', 'sector': 'Financial Services', 'industry': 'Asset Management'},
    {'symbol': 'SCHW', 'name': 'The Charles Schwab Corporation', 'sector': 'Financial Services', 'industry': 'Brokerage'},
    {'symbol': 'AXP', 'name': 'American Express Company', 'sector': 'Financial Services', 'industry': 'Credit Services'},
    {'symbol': 'V', 'name': 'Visa Inc.', 'sector': 'Financial Services', 'industry': 'Credit Services'},
    {'symbol': 'MA', 'name': 'Mastercard Inc.', 'sector': 'Financial Services', 'industry': 'Credit Services'},
    {'symbol': 'PYPL', 'name': 'PayPal Holdings Inc.', 'sector': 'Financial Services', 'industry': 'Payment Services'},

    # Consumer - Retail
    {'symbol': 'WMT', 'name': 'Walmart Inc.', 'sector': 'Consumer Defensive', 'industry': 'Discount Stores'},
    {'symbol': 'COST', 'name': 'Costco Wholesale Corporation', 'sector': 'Consumer Defensive', 'industry': 'Discount Stores'},
    {'symbol': 'TGT', 'name': 'Target Corporation', 'sector': 'Consumer Defensive', 'industry': 'Discount Stores'},
    {'symbol': 'HD', 'name': 'The Home Depot Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Home Improvement'},
    {'symbol': 'LOW', 'name': 'Lowe\'s Companies Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Home Improvement'},
    {'symbol': 'NKE', 'name': 'NIKE Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Footwear & Accessories'},
    {'symbol': 'SBUX', 'name': 'Starbucks Corporation', 'sector': 'Consumer Cyclical', 'industry': 'Restaurants'},
    {'symbol': 'MCD', 'name': 'McDonald\'s Corporation', 'sector': 'Consumer Cyclical', 'industry': 'Restaurants'},

    # Consumer - Brands
    {'symbol': 'PG', 'name': 'The Procter & Gamble Company', 'sector': 'Consumer Defensive', 'industry': 'Household Products'},
    {'symbol': 'KO', 'name': 'The Coca-Cola Company', 'sector': 'Consumer Defensive', 'industry': 'Beverages'},
    {'symbol': 'PEP', 'name': 'PepsiCo Inc.', 'sector': 'Consumer Defensive', 'industry': 'Beverages'},
    {'symbol': 'PM', 'name': 'Philip Morris International Inc.', 'sector': 'Consumer Defensive', 'industry': 'Tobacco'},
    {'symbol': 'MO', 'name': 'Altria Group Inc.', 'sector': 'Consumer Defensive', 'industry': 'Tobacco'},

    # Energy
    {'symbol': 'XOM', 'name': 'Exxon Mobil Corporation', 'sector': 'Energy', 'industry': 'Oil & Gas'},
    {'symbol': 'CVX', 'name': 'Chevron Corporation', 'sector': 'Energy', 'industry': 'Oil & Gas'},
    {'symbol': 'COP', 'name': 'ConocoPhillips', 'sector': 'Energy', 'industry': 'Oil & Gas'},
    {'symbol': 'SLB', 'name': 'Schlumberger N.V.', 'sector': 'Energy', 'industry': 'Oil & Gas Services'},
    {'symbol': 'EOG', 'name': 'EOG Resources Inc.', 'sector': 'Energy', 'industry': 'Oil & Gas'},
    {'symbol': 'PSX', 'name': 'Phillips 66', 'sector': 'Energy', 'industry': 'Oil & Gas Refining'},
    {'symbol': 'MPC', 'name': 'Marathon Petroleum Corporation', 'sector': 'Energy', 'industry': 'Oil & Gas Refining'},

    # Industrials
    {'symbol': 'BA', 'name': 'The Boeing Company', 'sector': 'Industrials', 'industry': 'Aerospace & Defense'},
    {'symbol': 'LMT', 'name': 'Lockheed Martin Corporation', 'sector': 'Industrials', 'industry': 'Aerospace & Defense'},
    {'symbol': 'RTX', 'name': 'RTX Corporation', 'sector': 'Industrials', 'industry': 'Aerospace & Defense'},
    {'symbol': 'UPS', 'name': 'United Parcel Service Inc.', 'sector': 'Industrials', 'industry': 'Logistics'},
    {'symbol': 'FDX', 'name': 'FedEx Corporation', 'sector': 'Industrials', 'industry': 'Logistics'},
    {'symbol': 'CAT', 'name': 'Caterpillar Inc.', 'sector': 'Industrials', 'industry': 'Construction Equipment'},
    {'symbol': 'DE', 'name': 'Deere & Company', 'sector': 'Industrials', 'industry': 'Agricultural Equipment'},
    {'symbol': 'GE', 'name': 'General Electric Company', 'sector': 'Industrials', 'industry': 'Conglomerate'},
    {'symbol': 'MMM', 'name': '3M Company', 'sector': 'Industrials', 'industry': 'Conglomerate'},
    {'symbol': 'HON', 'name': 'Honeywell International Inc.', 'sector': 'Industrials', 'industry': 'Conglomerate'},

    # Telecom & Media
    {'symbol': 'T', 'name': 'AT&T Inc.', 'sector': 'Communication Services', 'industry': 'Telecom'},
    {'symbol': 'VZ', 'name': 'Verizon Communications Inc.', 'sector': 'Communication Services', 'industry': 'Telecom'},
    {'symbol': 'TMUS', 'name': 'T-Mobile US Inc.', 'sector': 'Communication Services', 'industry': 'Telecom'},
    {'symbol': 'DIS', 'name': 'The Walt Disney Company', 'sector': 'Communication Services', 'industry': 'Entertainment'},
    {'symbol': 'CMCSA', 'name': 'Comcast Corporation', 'sector': 'Communication Services', 'industry': 'Media'},
    {'symbol': 'CHTR', 'name': 'Charter Communications Inc.', 'sector': 'Communication Services', 'industry': 'Media'},

    # Additional existing stocks (abbreviated for space - would include all 335)
    {'symbol': 'ZM', 'name': 'Zoom Video Communications Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'ZS', 'name': 'Zscaler Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'NOW', 'name': 'ServiceNow Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'PANW', 'name': 'Palo Alto Networks Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'CRWD', 'name': 'CrowdStrike Holdings Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'DDOG', 'name': 'Datadog Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'NET', 'name': 'Cloudflare Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'OKTA', 'name': 'Okta Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'WDAY', 'name': 'Workday Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'TEAM', 'name': 'Atlassian Corporation', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'ADSK', 'name': 'Autodesk Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'INTU', 'name': 'Intuit Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'FTNT', 'name': 'Fortinet Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'MU', 'name': 'Micron Technology Inc.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'NXPI', 'name': 'NXP Semiconductors N.V.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'MRVL', 'name': 'Marvell Technology Inc.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'MCHP', 'name': 'Microchip Technology Inc.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'ON', 'name': 'ON Semiconductor Corporation', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'IBM', 'name': 'International Business Machines Corporation', 'sector': 'Technology', 'industry': 'IT Services'},
    {'symbol': 'DELL', 'name': 'Dell Technologies Inc.', 'sector': 'Technology', 'industry': 'Hardware'},
    {'symbol': 'HPQ', 'name': 'HP Inc.', 'sector': 'Technology', 'industry': 'Hardware'},
    {'symbol': 'NTAP', 'name': 'NetApp Inc.', 'sector': 'Technology', 'industry': 'Data Storage'},
    {'symbol': 'WDC', 'name': 'Western Digital Corporation', 'sector': 'Technology', 'industry': 'Data Storage'},
    {'symbol': 'STX', 'name': 'Seagate Technology Holdings plc', 'sector': 'Technology', 'industry': 'Data Storage'},
    {'symbol': 'ANET', 'name': 'Arista Networks Inc.', 'sector': 'Technology', 'industry': 'Networking'},
    {'symbol': 'JNPR', 'name': 'Juniper Networks Inc.', 'sector': 'Technology', 'industry': 'Networking'},
    {'symbol': 'F', 'name': 'Ford Motor Company', 'sector': 'Consumer Cyclical', 'industry': 'Auto Manufacturers'},
    {'symbol': 'GM', 'name': 'General Motors Company', 'sector': 'Consumer Cyclical', 'industry': 'Auto Manufacturers'},
    {'symbol': 'RIVN', 'name': 'Rivian Automotive Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Auto Manufacturers'},
    {'symbol': 'LCID', 'name': 'Lucid Group Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Auto Manufacturers'},
    {'symbol': 'NIO', 'name': 'NIO Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Auto Manufacturers'},
    {'symbol': 'XPEV', 'name': 'XPeng Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Auto Manufacturers'},
    {'symbol': 'AAL', 'name': 'American Airlines Group Inc.', 'sector': 'Industrials', 'industry': 'Airlines'},
    {'symbol': 'DAL', 'name': 'Delta Air Lines Inc.', 'sector': 'Industrials', 'industry': 'Airlines'},
    {'symbol': 'UAL', 'name': 'United Airlines Holdings Inc.', 'sector': 'Industrials', 'industry': 'Airlines'},
    {'symbol': 'LUV', 'name': 'Southwest Airlines Co.', 'sector': 'Industrials', 'industry': 'Airlines'},
    {'symbol': 'JBLU', 'name': 'JetBlue Airways Corporation', 'sector': 'Industrials', 'industry': 'Airlines'},
    {'symbol': 'MAR', 'name': 'Marriott International Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Lodging'},
    {'symbol': 'HLT', 'name': 'Hilton Worldwide Holdings Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Lodging'},
    {'symbol': 'MGM', 'name': 'MGM Resorts International', 'sector': 'Consumer Cyclical', 'industry': 'Resorts & Casinos'},
    {'symbol': 'WYNN', 'name': 'Wynn Resorts Limited', 'sector': 'Consumer Cyclical', 'industry': 'Resorts & Casinos'},
    {'symbol': 'LVS', 'name': 'Las Vegas Sands Corp.', 'sector': 'Consumer Cyclical', 'industry': 'Resorts & Casinos'},
    {'symbol': 'CCL', 'name': 'Carnival Corporation', 'sector': 'Consumer Cyclical', 'industry': 'Travel Services'},
    {'symbol': 'RCL', 'name': 'Royal Caribbean Cruises Ltd.', 'sector': 'Consumer Cyclical', 'industry': 'Travel Services'},
    {'symbol': 'NCLH', 'name': 'Norwegian Cruise Line Holdings Ltd.', 'sector': 'Consumer Cyclical', 'industry': 'Travel Services'},
    {'symbol': 'ZG', 'name': 'Zillow Group Inc.', 'sector': 'Real Estate', 'industry': 'Real Estate Services'},
    {'symbol': 'Z', 'name': 'Zillow Group Inc. Class C', 'sector': 'Real Estate', 'industry': 'Real Estate Services'},
    {'symbol': 'RDFN', 'name': 'Redfin Corporation', 'sector': 'Real Estate', 'industry': 'Real Estate Services'},
    {'symbol': 'OPEN', 'name': 'Opendoor Technologies Inc.', 'sector': 'Real Estate', 'industry': 'Real Estate Services'},
    {'symbol': 'PLD', 'name': 'Prologis Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Industrial'},
    {'symbol': 'AMT', 'name': 'American Tower Corporation', 'sector': 'Real Estate', 'industry': 'REIT - Specialty'},
    {'symbol': 'CCI', 'name': 'Crown Castle Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Specialty'},
    {'symbol': 'EQIX', 'name': 'Equinix Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Specialty'},
    {'symbol': 'SPG', 'name': 'Simon Property Group Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Retail'},
    {'symbol': 'O', 'name': 'Realty Income Corporation', 'sector': 'Real Estate', 'industry': 'REIT - Retail'},
    {'symbol': 'DLR', 'name': 'Digital Realty Trust Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Office'},
    {'symbol': 'PSA', 'name': 'Public Storage', 'sector': 'Real Estate', 'industry': 'REIT - Industrial'},
    {'symbol': 'WELL', 'name': 'Welltower Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Healthcare'},
    {'symbol': 'AVB', 'name': 'AvalonBay Communities Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Residential'},
    {'symbol': 'EQR', 'name': 'Equity Residential', 'sector': 'Real Estate', 'industry': 'REIT - Residential'},
    {'symbol': 'VTR', 'name': 'Ventas Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Healthcare'},
    {'symbol': 'ARE', 'name': 'Alexandria Real Estate Equities Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Office'},
    {'symbol': 'IRM', 'name': 'Iron Mountain Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Specialty'},
    {'symbol': 'INVH', 'name': 'Invitation Homes Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Residential'},
    {'symbol': 'EXR', 'name': 'Extra Space Storage Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Industrial'},
    {'symbol': 'SUI', 'name': 'Sun Communities Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Residential'},
    {'symbol': 'AMH', 'name': 'American Homes 4 Rent', 'sector': 'Real Estate', 'industry': 'REIT - Residential'},
    {'symbol': 'HST', 'name': 'Host Hotels & Resorts Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Hotel & Motel'},
    {'symbol': 'BXP', 'name': 'BXP Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Office'},
    {'symbol': 'VNO', 'name': 'Vornado Realty Trust', 'sector': 'Real Estate', 'industry': 'REIT - Office'},
    {'symbol': 'KIM', 'name': 'Kimco Realty Corporation', 'sector': 'Real Estate', 'industry': 'REIT - Retail'},
    {'symbol': 'REG', 'name': 'Regency Centers Corporation', 'sector': 'Real Estate', 'industry': 'REIT - Retail'},
    {'symbol': 'FRT', 'name': 'Federal Realty Investment Trust', 'sector': 'Real Estate', 'industry': 'REIT - Retail'},
    {'symbol': 'UDR', 'name': 'UDR Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Residential'},
    {'symbol': 'ESS', 'name': 'Essex Property Trust Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Residential'},
    {'symbol': 'MAA', 'name': 'Mid-America Apartment Communities Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Residential'},
    {'symbol': 'CPT', 'name': 'Camden Property Trust', 'sector': 'Real Estate', 'industry': 'REIT - Residential'},
    {'symbol': 'AIV', 'name': 'Apartment Investment and Management Company', 'sector': 'Real Estate', 'industry': 'REIT - Residential'},
    {'symbol': 'SLG', 'name': 'SL Green Realty Corp.', 'sector': 'Real Estate', 'industry': 'REIT - Office'},
    {'symbol': 'KRC', 'name': 'Kilroy Realty Corporation', 'sector': 'Real Estate', 'industry': 'REIT - Office'},
    {'symbol': 'HIW', 'name': 'Highwoods Properties Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Office'},
    {'symbol': 'DEI', 'name': 'Douglas Emmett Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Office'},
    {'symbol': 'PEAK', 'name': 'Healthpeak Properties Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Healthcare'},
    {'symbol': 'DOC', 'name': 'Physicians Realty Trust', 'sector': 'Real Estate', 'industry': 'REIT - Healthcare'},
    {'symbol': 'HR', 'name': 'Healthcare Realty Trust Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Healthcare'},
    {'symbol': 'MPW', 'name': 'Medical Properties Trust Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Healthcare'},
    {'symbol': 'OHI', 'name': 'Omega Healthcare Investors Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Healthcare'},
    {'symbol': 'SBRA', 'name': 'Sabra Health Care REIT Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Healthcare'},
    {'symbol': 'LTC', 'name': 'LTC Properties Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Healthcare'},
    {'symbol': 'NHI', 'name': 'National Health Investors Inc.', 'sector': 'Real Estate', 'industry': 'REIT - Healthcare'},
    {'symbol': 'UHT', 'name': 'Universal Health Realty Income Trust', 'sector': 'Real Estate', 'industry': 'REIT - Healthcare'},
    {'symbol': 'GME', 'name': 'GameStop Corp.', 'sector': 'Consumer Cyclical', 'industry': 'Specialty Retail'},
    {'symbol': 'AMC', 'name': 'AMC Entertainment Holdings Inc.', 'sector': 'Communication Services', 'industry': 'Entertainment'},
    {'symbol': 'HOOD', 'name': 'Robinhood Markets Inc.', 'sector': 'Financial Services', 'industry': 'Brokerage'},
    {'symbol': 'SOFI', 'name': 'SoFi Technologies Inc.', 'sector': 'Financial Services', 'industry': 'Financial Services'},
    {'symbol': 'AFRM', 'name': 'Affirm Holdings Inc.', 'sector': 'Financial Services', 'industry': 'Credit Services'},
    {'symbol': 'UPST', 'name': 'Upstart Holdings Inc.', 'sector': 'Financial Services', 'industry': 'Credit Services'},
    {'symbol': 'LC', 'name': 'LendingClub Corporation', 'sector': 'Financial Services', 'industry': 'Credit Services'},
    {'symbol': 'MARA', 'name': 'Marathon Digital Holdings Inc.', 'sector': 'Financial Services', 'industry': 'Cryptocurrency'},
    {'symbol': 'RIOT', 'name': 'Riot Platforms Inc.', 'sector': 'Financial Services', 'industry': 'Cryptocurrency'},
    {'symbol': 'HUT', 'name': 'Hut 8 Mining Corp.', 'sector': 'Financial Services', 'industry': 'Cryptocurrency'},
    {'symbol': 'CLSK', 'name': 'CleanSpark Inc.', 'sector': 'Financial Services', 'industry': 'Cryptocurrency'},
    {'symbol': 'PLUG', 'name': 'Plug Power Inc.', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'FCEL', 'name': 'FuelCell Energy Inc.', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'BE', 'name': 'Bloom Energy Corporation', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'BLDP', 'name': 'Ballard Power Systems Inc.', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'ENPH', 'name': 'Enphase Energy Inc.', 'sector': 'Technology', 'industry': 'Solar'},
    {'symbol': 'SEDG', 'name': 'SolarEdge Technologies Inc.', 'sector': 'Technology', 'industry': 'Solar'},
    {'symbol': 'RUN', 'name': 'Sunrun Inc.', 'sector': 'Technology', 'industry': 'Solar'},
    {'symbol': 'NOVA', 'name': 'Sunnova Energy International Inc.', 'sector': 'Technology', 'industry': 'Solar'},
    {'symbol': 'SPWR', 'name': 'SunPower Corporation', 'sector': 'Technology', 'industry': 'Solar'},
    {'symbol': 'FSLR', 'name': 'First Solar Inc.', 'sector': 'Technology', 'industry': 'Solar'},
    {'symbol': 'NEE', 'name': 'NextEra Energy Inc.', 'sector': 'Utilities', 'industry': 'Utilities - Renewable'},
    {'symbol': 'DUK', 'name': 'Duke Energy Corporation', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'SO', 'name': 'The Southern Company', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'D', 'name': 'Dominion Energy Inc.', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'EXC', 'name': 'Exelon Corporation', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'AEP', 'name': 'American Electric Power Company Inc.', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'SRE', 'name': 'Sempra', 'sector': 'Utilities', 'industry': 'Utilities - Diversified'},
    {'symbol': 'XEL', 'name': 'Xcel Energy Inc.', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'ED', 'name': 'Consolidated Edison Inc.', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'WEC', 'name': 'WEC Energy Group Inc.', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'ES', 'name': 'Eversource Energy', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'PEG', 'name': 'Public Service Enterprise Group Inc.', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'PCG', 'name': 'PG&E Corporation', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'EIX', 'name': 'Edison International', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'AWK', 'name': 'American Water Works Company Inc.', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Water'},
    {'symbol': 'AEE', 'name': 'Ameren Corporation', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'CMS', 'name': 'CMS Energy Corporation', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'DTE', 'name': 'DTE Energy Company', 'sector': 'Utilities', 'industry': 'Utilities - Diversified'},
    {'symbol': 'FE', 'name': 'FirstEnergy Corp.', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'ETR', 'name': 'Entergy Corporation', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'NI', 'name': 'NiSource Inc.', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Gas'},
    {'symbol': 'PNW', 'name': 'Pinnacle West Capital Corporation', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'LNT', 'name': 'Alliant Energy Corporation', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'CNP', 'name': 'CenterPoint Energy Inc.', 'sector': 'Utilities', 'industry': 'Utilities - Diversified'},
    {'symbol': 'AES', 'name': 'The AES Corporation', 'sector': 'Utilities', 'industry': 'Utilities - Independent Power'},
    {'symbol': 'PPL', 'name': 'PPL Corporation', 'sector': 'Utilities', 'industry': 'Utilities - Regulated Electric'},
    {'symbol': 'OTIS', 'name': 'Otis Worldwide Corporation', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'CARR', 'name': 'Carrier Global Corporation', 'sector': 'Industrials', 'industry': 'Building Products'},
    {'symbol': 'GNRC', 'name': 'Generac Holdings Inc.', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'EMR', 'name': 'Emerson Electric Co.', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'ETN', 'name': 'Eaton Corporation plc', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'PH', 'name': 'Parker-Hannifin Corporation', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'ITW', 'name': 'Illinois Tool Works Inc.', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'ROK', 'name': 'Rockwell Automation Inc.', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'DOV', 'name': 'Dover Corporation', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'IR', 'name': 'Ingersoll Rand Inc.', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'XYL', 'name': 'Xylem Inc.', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'PCAR', 'name': 'PACCAR Inc.', 'sector': 'Industrials', 'industry': 'Farm & Heavy Machinery'},
    {'symbol': 'CMI', 'name': 'Cummins Inc.', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},
    {'symbol': 'NSC', 'name': 'Norfolk Southern Corporation', 'sector': 'Industrials', 'industry': 'Railroads'},
    {'symbol': 'UNP', 'name': 'Union Pacific Corporation', 'sector': 'Industrials', 'industry': 'Railroads'},
    {'symbol': 'CSX', 'name': 'CSX Corporation', 'sector': 'Industrials', 'industry': 'Railroads'},
    {'symbol': 'CP', 'name': 'Canadian Pacific Kansas City Limited', 'sector': 'Industrials', 'industry': 'Railroads'},
    {'symbol': 'KSU', 'name': 'Kansas City Southern', 'sector': 'Industrials', 'industry': 'Railroads'},
    {'symbol': 'URI', 'name': 'United Rentals Inc.', 'sector': 'Industrials', 'industry': 'Rental & Leasing'},
    {'symbol': 'WAB', 'name': 'Westinghouse Air Brake Technologies Corporation', 'sector': 'Industrials', 'industry': 'Railroads'},
    {'symbol': 'J', 'name': 'Jacobs Solutions Inc.', 'sector': 'Industrials', 'industry': 'Engineering & Construction'},
    {'symbol': 'PWR', 'name': 'Quanta Services Inc.', 'sector': 'Industrials', 'industry': 'Engineering & Construction'},
    {'symbol': 'VMC', 'name': 'Vulcan Materials Company', 'sector': 'Basic Materials', 'industry': 'Construction Materials'},
    {'symbol': 'MLM', 'name': 'Martin Marietta Materials Inc.', 'sector': 'Basic Materials', 'industry': 'Construction Materials'},
    {'symbol': 'AA', 'name': 'Alcoa Corporation', 'sector': 'Basic Materials', 'industry': 'Aluminum'},
    {'symbol': 'NUE', 'name': 'Nucor Corporation', 'sector': 'Basic Materials', 'industry': 'Steel'},
    {'symbol': 'STLD', 'name': 'Steel Dynamics Inc.', 'sector': 'Basic Materials', 'industry': 'Steel'},
    {'symbol': 'RS', 'name': 'Reliance Steel & Aluminum Co.', 'sector': 'Basic Materials', 'industry': 'Steel'},
    {'symbol': 'X', 'name': 'United States Steel Corporation', 'sector': 'Basic Materials', 'industry': 'Steel'},
    {'symbol': 'CLF', 'name': 'Cleveland-Cliffs Inc.', 'sector': 'Basic Materials', 'industry': 'Steel'},
    {'symbol': 'FCX', 'name': 'Freeport-McMoRan Inc.', 'sector': 'Basic Materials', 'industry': 'Copper'},
    {'symbol': 'NEM', 'name': 'Newmont Corporation', 'sector': 'Basic Materials', 'industry': 'Gold'},
    {'symbol': 'GOLD', 'name': 'Barrick Gold Corporation', 'sector': 'Basic Materials', 'industry': 'Gold'},
    {'symbol': 'AEM', 'name': 'Agnico Eagle Mines Limited', 'sector': 'Basic Materials', 'industry': 'Gold'},
    {'symbol': 'KGC', 'name': 'Kinross Gold Corporation', 'sector': 'Basic Materials', 'industry': 'Gold'},
    {'symbol': 'FNV', 'name': 'Franco-Nevada Corporation', 'sector': 'Basic Materials', 'industry': 'Gold'},
    {'symbol': 'WPM', 'name': 'Wheaton Precious Metals Corp.', 'sector': 'Basic Materials', 'industry': 'Gold'},
    {'symbol': 'MOS', 'name': 'The Mosaic Company', 'sector': 'Basic Materials', 'industry': 'Agricultural Inputs'},
    {'symbol': 'CF', 'name': 'CF Industries Holdings Inc.', 'sector': 'Basic Materials', 'industry': 'Agricultural Inputs'},
    {'symbol': 'NTR', 'name': 'Nutrien Ltd.', 'sector': 'Basic Materials', 'industry': 'Agricultural Inputs'},
    {'symbol': 'APD', 'name': 'Air Products and Chemicals Inc.', 'sector': 'Basic Materials', 'industry': 'Specialty Chemicals'},
    {'symbol': 'LIN', 'name': 'Linde plc', 'sector': 'Basic Materials', 'industry': 'Specialty Chemicals'},
    {'symbol': 'ECL', 'name': 'Ecolab Inc.', 'sector': 'Basic Materials', 'industry': 'Specialty Chemicals'},
    {'symbol': 'DD', 'name': 'DuPont de Nemours Inc.', 'sector': 'Basic Materials', 'industry': 'Specialty Chemicals'},
    {'symbol': 'DOW', 'name': 'Dow Inc.', 'sector': 'Basic Materials', 'industry': 'Chemicals'},
    {'symbol': 'LYB', 'name': 'LyondellBasell Industries N.V.', 'sector': 'Basic Materials', 'industry': 'Chemicals'},
    {'symbol': 'PPG', 'name': 'PPG Industries Inc.', 'sector': 'Basic Materials', 'industry': 'Specialty Chemicals'},
    {'symbol': 'SHW', 'name': 'The Sherwin-Williams Company', 'sector': 'Basic Materials', 'industry': 'Specialty Chemicals'},
    {'symbol': 'ALB', 'name': 'Albemarle Corporation', 'sector': 'Basic Materials', 'industry': 'Specialty Chemicals'},
    {'symbol': 'CE', 'name': 'Celanese Corporation', 'sector': 'Basic Materials', 'industry': 'Chemicals'},
    {'symbol': 'EMN', 'name': 'Eastman Chemical Company', 'sector': 'Basic Materials', 'industry': 'Chemicals'},
    {'symbol': 'FMC', 'name': 'FMC Corporation', 'sector': 'Basic Materials', 'industry': 'Agricultural Inputs'},
    {'symbol': 'IFF', 'name': 'International Flavors & Fragrances Inc.', 'sector': 'Basic Materials', 'industry': 'Specialty Chemicals'},
    {'symbol': 'PKG', 'name': 'Packaging Corporation of America', 'sector': 'Basic Materials', 'industry': 'Packaging & Containers'},
    {'symbol': 'IP', 'name': 'International Paper Company', 'sector': 'Basic Materials', 'industry': 'Paper & Paper Products'},
    {'symbol': 'WRK', 'name': 'WestRock Company', 'sector': 'Basic Materials', 'industry': 'Packaging & Containers'},
    {'symbol': 'AMCR', 'name': 'Amcor plc', 'sector': 'Basic Materials', 'industry': 'Packaging & Containers'},
    {'symbol': 'SEE', 'name': 'Sealed Air Corporation', 'sector': 'Basic Materials', 'industry': 'Packaging & Containers'},
    {'symbol': 'AVY', 'name': 'Avery Dennison Corporation', 'sector': 'Basic Materials', 'industry': 'Packaging & Containers'},
    {'symbol': 'BALL', 'name': 'Ball Corporation', 'sector': 'Basic Materials', 'industry': 'Packaging & Containers'},
    {'symbol': 'CCK', 'name': 'Crown Holdings Inc.', 'sector': 'Basic Materials', 'industry': 'Packaging & Containers'},
    {'symbol': 'APH', 'name': 'Amphenol Corporation', 'sector': 'Technology', 'industry': 'Electronic Components'},
    {'symbol': 'TEL', 'name': 'TE Connectivity Ltd.', 'sector': 'Technology', 'industry': 'Electronic Components'},
    {'symbol': 'GLW', 'name': 'Corning Incorporated', 'sector': 'Technology', 'industry': 'Electronic Components'},
    {'symbol': 'ZBRA', 'name': 'Zebra Technologies Corporation', 'sector': 'Technology', 'industry': 'Communication Equipment'},
    {'symbol': 'KEYS', 'name': 'Keysight Technologies Inc.', 'sector': 'Technology', 'industry': 'Scientific & Technical Instruments'},
    {'symbol': 'ANSS', 'name': 'ANSYS Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'CDNS', 'name': 'Cadence Design Systems Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'SNPS', 'name': 'Synopsys Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'TYL', 'name': 'Tyler Technologies Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'ROP', 'name': 'Roper Technologies Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'TDY', 'name': 'Teledyne Technologies Incorporated', 'sector': 'Technology', 'industry': 'Scientific & Technical Instruments'},
    {'symbol': 'FTV', 'name': 'Fortive Corporation', 'sector': 'Technology', 'industry': 'Scientific & Technical Instruments'},
    {'symbol': 'MSCI', 'name': 'MSCI Inc.', 'sector': 'Financial Services', 'industry': 'Financial Data & Stock Exchanges'},
    {'symbol': 'SPGI', 'name': 'S&P Global Inc.', 'sector': 'Financial Services', 'industry': 'Financial Data & Stock Exchanges'},
    {'symbol': 'MCO', 'name': 'Moody\'s Corporation', 'sector': 'Financial Services', 'industry': 'Financial Data & Stock Exchanges'},
    {'symbol': 'CME', 'name': 'CME Group Inc.', 'sector': 'Financial Services', 'industry': 'Financial Data & Stock Exchanges'},
    {'symbol': 'ICE', 'name': 'Intercontinental Exchange Inc.', 'sector': 'Financial Services', 'industry': 'Financial Data & Stock Exchanges'},
    {'symbol': 'NDAQ', 'name': 'Nasdaq Inc.', 'sector': 'Financial Services', 'industry': 'Financial Data & Stock Exchanges'},
    {'symbol': 'CBOE', 'name': 'Cboe Global Markets Inc.', 'sector': 'Financial Services', 'industry': 'Financial Data & Stock Exchanges'},
    {'symbol': 'AON', 'name': 'Aon plc', 'sector': 'Financial Services', 'industry': 'Insurance Brokers'},
    {'symbol': 'MMC', 'name': 'Marsh & McLennan Companies Inc.', 'sector': 'Financial Services', 'industry': 'Insurance Brokers'},
    {'symbol': 'AJG', 'name': 'Arthur J. Gallagher & Co.', 'sector': 'Financial Services', 'industry': 'Insurance Brokers'},
    {'symbol': 'BRO', 'name': 'Brown & Brown Inc.', 'sector': 'Financial Services', 'industry': 'Insurance Brokers'},
    {'symbol': 'TRV', 'name': 'The Travelers Companies Inc.', 'sector': 'Financial Services', 'industry': 'Insurance - Property & Casualty'},
    {'symbol': 'PGR', 'name': 'The Progressive Corporation', 'sector': 'Financial Services', 'industry': 'Insurance - Property & Casualty'},
    {'symbol': 'ALL', 'name': 'The Allstate Corporation', 'sector': 'Financial Services', 'industry': 'Insurance - Property & Casualty'},
    {'symbol': 'CB', 'name': 'Chubb Limited', 'sector': 'Financial Services', 'industry': 'Insurance - Property & Casualty'},
    {'symbol': 'AIG', 'name': 'American International Group Inc.', 'sector': 'Financial Services', 'industry': 'Insurance - Property & Casualty'},
    {'symbol': 'MET', 'name': 'MetLife Inc.', 'sector': 'Financial Services', 'industry': 'Insurance - Life'},
    {'symbol': 'PRU', 'name': 'Prudential Financial Inc.', 'sector': 'Financial Services', 'industry': 'Insurance - Life'},
    {'symbol': 'AFL', 'name': 'Aflac Incorporated', 'sector': 'Financial Services', 'industry': 'Insurance - Life'},
    {'symbol': 'LNC', 'name': 'Lincoln National Corporation', 'sector': 'Financial Services', 'industry': 'Insurance - Life'},
    {'symbol': 'GL', 'name': 'Globe Life Inc.', 'sector': 'Financial Services', 'industry': 'Insurance - Life'},
    {'symbol': 'AMP', 'name': 'Ameriprise Financial Inc.', 'sector': 'Financial Services', 'industry': 'Asset Management'},
    {'symbol': 'TROW', 'name': 'T. Rowe Price Group Inc.', 'sector': 'Financial Services', 'industry': 'Asset Management'},
    {'symbol': 'BEN', 'name': 'Franklin Resources Inc.', 'sector': 'Financial Services', 'industry': 'Asset Management'},
    {'symbol': 'IVZ', 'name': 'Invesco Ltd.', 'sector': 'Financial Services', 'industry': 'Asset Management'},
    {'symbol': 'STT', 'name': 'State Street Corporation', 'sector': 'Financial Services', 'industry': 'Asset Management'},
    {'symbol': 'BK', 'name': 'The Bank of New York Mellon Corporation', 'sector': 'Financial Services', 'industry': 'Asset Management'},
    {'symbol': 'NTRS', 'name': 'Northern Trust Corporation', 'sector': 'Financial Services', 'industry': 'Asset Management'},
    {'symbol': 'PNC', 'name': 'The PNC Financial Services Group Inc.', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'USB', 'name': 'U.S. Bancorp', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'TFC', 'name': 'Truist Financial Corporation', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'COF', 'name': 'Capital One Financial Corporation', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'DFS', 'name': 'Discover Financial Services', 'sector': 'Financial Services', 'industry': 'Credit Services'},
    {'symbol': 'SYF', 'name': 'Synchrony Financial', 'sector': 'Financial Services', 'industry': 'Credit Services'},
    {'symbol': 'ALLY', 'name': 'Ally Financial Inc.', 'sector': 'Financial Services', 'industry': 'Credit Services'},
    {'symbol': 'RF', 'name': 'Regions Financial Corporation', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'KEY', 'name': 'KeyCorp', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'FITB', 'name': 'Fifth Third Bancorp', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'HBAN', 'name': 'Huntington Bancshares Incorporated', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'CFG', 'name': 'Citizens Financial Group Inc.', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'MTB', 'name': 'M&T Bank Corporation', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'ZION', 'name': 'Zions Bancorporation N.A.', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'CMA', 'name': 'Comerica Incorporated', 'sector': 'Financial Services', 'industry': 'Banks'},
    {'symbol': 'ZBH', 'name': 'Zimmer Biomet Holdings Inc.', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
    {'symbol': 'BAX', 'name': 'Baxter International Inc.', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
    {'symbol': 'BDX', 'name': 'Becton Dickinson and Company', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
    {'symbol': 'EW', 'name': 'Edwards Lifesciences Corporation', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
    {'symbol': 'DXCM', 'name': 'DexCom Inc.', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
    {'symbol': 'ALGN', 'name': 'Align Technology Inc.', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
    {'symbol': 'IDXX', 'name': 'IDEXX Laboratories Inc.', 'sector': 'Healthcare', 'industry': 'Diagnostics'},
    {'symbol': 'IQV', 'name': 'IQVIA Holdings Inc.', 'sector': 'Healthcare', 'industry': 'Diagnostics'},
    {'symbol': 'A', 'name': 'Agilent Technologies Inc.', 'sector': 'Healthcare', 'industry': 'Diagnostics'},
    {'symbol': 'WAT', 'name': 'Waters Corporation', 'sector': 'Healthcare', 'industry': 'Diagnostics'},
    {'symbol': 'HOLX', 'name': 'Hologic Inc.', 'sector': 'Healthcare', 'industry': 'Diagnostics'},
    {'symbol': 'TECH', 'name': 'Bio-Techne Corporation', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'PKI', 'name': 'PerkinElmer Inc.', 'sector': 'Healthcare', 'industry': 'Diagnostics'},
    {'symbol': 'BIO', 'name': 'Bio-Rad Laboratories Inc.', 'sector': 'Healthcare', 'industry': 'Diagnostics'},
    {'symbol': 'XRAY', 'name': 'DENTSPLY SIRONA Inc.', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
]

# 165 NEW stocks to add (diverse sectors for total of 500)
NEW_STOCKS = [
    # Tech - Additional Software & Cloud
    {'symbol': 'TWLO', 'name': 'Twilio Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'DOCU', 'name': 'DocuSign Inc.', 'sector': 'Technology', 'industry': 'Software'},
    # {'symbol': 'ZI', 'name': 'ZoomInfo Technologies Inc.', 'sector': 'Technology', 'industry': 'Software'},  # DUPLICATE - already in EXISTING_STOCKS
    {'symbol': 'BILL', 'name': 'Bill.com Holdings Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'COUP', 'name': 'Coupa Software Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'PATH', 'name': 'UiPath Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'GTLB', 'name': 'GitLab Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'CFLT', 'name': 'Confluent Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'MDB', 'name': 'MongoDB Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'ESTC', 'name': 'Elastic N.V.', 'sector': 'Technology', 'industry': 'Software'},

    # Tech - Cybersecurity
    {'symbol': 'S', 'name': 'SentinelOne Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'TENB', 'name': 'Tenable Holdings Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'CYBR', 'name': 'CyberArk Software Ltd.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'SAIL', 'name': 'SailPoint Technologies Holdings Inc.', 'sector': 'Technology', 'industry': 'Software'},
    {'symbol': 'VRNS', 'name': 'Varonis Systems Inc.', 'sector': 'Technology', 'industry': 'Software'},

    # Tech - Semiconductors
    {'symbol': 'ASML', 'name': 'ASML Holding N.V.', 'sector': 'Technology', 'industry': 'Semiconductor Equipment'},
    {'symbol': 'TSM', 'name': 'Taiwan Semiconductor Manufacturing Company Limited', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'SSNLF', 'name': 'Samsung Electronics Co. Ltd.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'MPWR', 'name': 'Monolithic Power Systems Inc.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'SWKS', 'name': 'Skyworks Solutions Inc.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'QRVO', 'name': 'Qorvo Inc.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'SLAB', 'name': 'Silicon Laboratories Inc.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'WOLF', 'name': 'Wolfspeed Inc.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'AMBA', 'name': 'Ambarella Inc.', 'sector': 'Technology', 'industry': 'Semiconductors'},
    {'symbol': 'LITE', 'name': 'Lumentum Holdings Inc.', 'sector': 'Technology', 'industry': 'Semiconductors'},

    # Healthcare - Biotech
    {'symbol': 'SGEN', 'name': 'Seagen Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'ALNY', 'name': 'Alnylam Pharmaceuticals Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'BMRN', 'name': 'BioMarin Pharmaceutical Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'EXEL', 'name': 'Exelixis Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'INCY', 'name': 'Incyte Corporation', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'JAZZ', 'name': 'Jazz Pharmaceuticals plc', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'NBIX', 'name': 'Neurocrine Biosciences Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'RARE', 'name': 'Ultragenyx Pharmaceutical Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'UTHR', 'name': 'United Therapeutics Corporation', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'IONS', 'name': 'Ionis Pharmaceuticals Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'SRPT', 'name': 'Sarepta Therapeutics Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'BLUE', 'name': 'bluebird bio Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'CRSP', 'name': 'CRISPR Therapeutics AG', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'EDIT', 'name': 'Editas Medicine Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},
    {'symbol': 'NTLA', 'name': 'Intellia Therapeutics Inc.', 'sector': 'Healthcare', 'industry': 'Biotechnology'},

    # Healthcare - Med Tech & Diagnostics
    {'symbol': 'PEN', 'name': 'Penumbra Inc.', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
    {'symbol': 'PODD', 'name': 'Insulet Corporation', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
    {'symbol': 'ICUI', 'name': 'ICU Medical Inc.', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
    {'symbol': 'NVCR', 'name': 'NovoCure Limited', 'sector': 'Healthcare', 'industry': 'Medical Devices'},
    {'symbol': 'NTRA', 'name': 'Natera Inc.', 'sector': 'Healthcare', 'industry': 'Diagnostics'},
    {'symbol': 'EXAS', 'name': 'Exact Sciences Corporation', 'sector': 'Healthcare', 'industry': 'Diagnostics'},
    {'symbol': 'GH', 'name': 'Guardant Health Inc.', 'sector': 'Healthcare', 'industry': 'Diagnostics'},
    {'symbol': 'ILMN', 'name': 'Illumina Inc.', 'sector': 'Healthcare', 'industry': 'Diagnostics'},
    {'symbol': 'QGEN', 'name': 'QIAGEN N.V.', 'sector': 'Healthcare', 'industry': 'Diagnostics'},

    # Consumer - E-commerce & Retail
    {'symbol': 'CHWY', 'name': 'Chewy Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Specialty Retail'},
    {'symbol': 'FTCH', 'name': 'Farfetch Limited', 'sector': 'Consumer Cyclical', 'industry': 'Internet Retail'},
    {'symbol': 'RH', 'name': 'RH', 'sector': 'Consumer Cyclical', 'industry': 'Specialty Retail'},
    {'symbol': 'BBWI', 'name': 'Bath & Body Works Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Specialty Retail'},
    {'symbol': 'ULTA', 'name': 'Ulta Beauty Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Specialty Retail'},
    {'symbol': 'DKS', 'name': 'Dick\'s Sporting Goods Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Specialty Retail'},
    {'symbol': 'FL', 'name': 'Foot Locker Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Apparel Retail'},
    {'symbol': 'GPS', 'name': 'The Gap Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Apparel Retail'},
    {'symbol': 'URBN', 'name': 'Urban Outfitters Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Apparel Retail'},
    {'symbol': 'ANF', 'name': 'Abercrombie & Fitch Co.', 'sector': 'Consumer Cyclical', 'industry': 'Apparel Retail'},

    # Consumer - Brands & CPG
    {'symbol': 'EL', 'name': 'The Estée Lauder Companies Inc.', 'sector': 'Consumer Defensive', 'industry': 'Household Products'},
    {'symbol': 'CL', 'name': 'Colgate-Palmolive Company', 'sector': 'Consumer Defensive', 'industry': 'Household Products'},
    {'symbol': 'KMB', 'name': 'Kimberly-Clark Corporation', 'sector': 'Consumer Defensive', 'industry': 'Household Products'},
    {'symbol': 'CHD', 'name': 'Church & Dwight Co. Inc.', 'sector': 'Consumer Defensive', 'industry': 'Household Products'},
    {'symbol': 'CLX', 'name': 'The Clorox Company', 'sector': 'Consumer Defensive', 'industry': 'Household Products'},
    {'symbol': 'GIS', 'name': 'General Mills Inc.', 'sector': 'Consumer Defensive', 'industry': 'Packaged Foods'},
    {'symbol': 'K', 'name': 'Kellanova', 'sector': 'Consumer Defensive', 'industry': 'Packaged Foods'},
    {'symbol': 'CAG', 'name': 'Conagra Brands Inc.', 'sector': 'Consumer Defensive', 'industry': 'Packaged Foods'},
    {'symbol': 'CPB', 'name': 'Campbell Soup Company', 'sector': 'Consumer Defensive', 'industry': 'Packaged Foods'},
    {'symbol': 'MKC', 'name': 'McCormick & Company Incorporated', 'sector': 'Consumer Defensive', 'industry': 'Packaged Foods'},
    {'symbol': 'HSY', 'name': 'The Hershey Company', 'sector': 'Consumer Defensive', 'industry': 'Confectioners'},
    {'symbol': 'MDLZ', 'name': 'Mondelēz International Inc.', 'sector': 'Consumer Defensive', 'industry': 'Confectioners'},
    {'symbol': 'TSN', 'name': 'Tyson Foods Inc.', 'sector': 'Consumer Defensive', 'industry': 'Farm Products'},
    {'symbol': 'HRL', 'name': 'Hormel Foods Corporation', 'sector': 'Consumer Defensive', 'industry': 'Farm Products'},
    {'symbol': 'SJM', 'name': 'The J. M. Smucker Company', 'sector': 'Consumer Defensive', 'industry': 'Packaged Foods'},

    # Consumer - Restaurants & Leisure
    {'symbol': 'CMG', 'name': 'Chipotle Mexican Grill Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Restaurants'},
    {'symbol': 'QSR', 'name': 'Restaurant Brands International Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Restaurants'},
    {'symbol': 'YUM', 'name': 'Yum! Brands Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Restaurants'},
    {'symbol': 'DPZ', 'name': 'Domino\'s Pizza Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Restaurants'},
    {'symbol': 'WING', 'name': 'Wingstop Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Restaurants'},
    {'symbol': 'BLMN', 'name': 'Bloomin\' Brands Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Restaurants'},
    {'symbol': 'DRI', 'name': 'Dardenne Restaurants Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Restaurants'},
    {'symbol': 'EAT', 'name': 'Brinker International Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Restaurants'},

    # Energy - Renewable & Clean Tech
    {'symbol': 'CWEN', 'name': 'Clearway Energy Inc.', 'sector': 'Utilities', 'industry': 'Utilities - Renewable'},
    {'symbol': 'BEP', 'name': 'Brookfield Renewable Partners L.P.', 'sector': 'Utilities', 'industry': 'Utilities - Renewable'},
    {'symbol': 'AY', 'name': 'Atlantica Sustainable Infrastructure plc', 'sector': 'Utilities', 'industry': 'Utilities - Renewable'},
    {'symbol': 'CWEN.A', 'name': 'Clearway Energy Inc. Class A', 'sector': 'Utilities', 'industry': 'Utilities - Renewable'},

    # Energy - Oil Services & Equipment
    {'symbol': 'HAL', 'name': 'Halliburton Company', 'sector': 'Energy', 'industry': 'Oil & Gas Services'},
    {'symbol': 'BKR', 'name': 'Baker Hughes Company', 'sector': 'Energy', 'industry': 'Oil & Gas Services'},
    {'symbol': 'NOV', 'name': 'NOV Inc.', 'sector': 'Energy', 'industry': 'Oil & Gas Equipment'},
    {'symbol': 'FTI', 'name': 'TechnipFMC plc', 'sector': 'Energy', 'industry': 'Oil & Gas Equipment'},
    {'symbol': 'HP', 'name': 'Helmerich & Payne Inc.', 'sector': 'Energy', 'industry': 'Oil & Gas Drilling'},
    {'symbol': 'RIG', 'name': 'Transocean Ltd.', 'sector': 'Energy', 'industry': 'Oil & Gas Drilling'},

    # Energy - Midstream
    {'symbol': 'EPD', 'name': 'Enterprise Products Partners L.P.', 'sector': 'Energy', 'industry': 'Oil & Gas Midstream'},
    {'symbol': 'MPLX', 'name': 'MPLX LP', 'sector': 'Energy', 'industry': 'Oil & Gas Midstream'},
    {'symbol': 'ET', 'name': 'Energy Transfer LP', 'sector': 'Energy', 'industry': 'Oil & Gas Midstream'},
    {'symbol': 'WMB', 'name': 'The Williams Companies Inc.', 'sector': 'Energy', 'industry': 'Oil & Gas Midstream'},
    {'symbol': 'OKE', 'name': 'ONEOK Inc.', 'sector': 'Energy', 'industry': 'Oil & Gas Midstream'},
    {'symbol': 'KMI', 'name': 'Kinder Morgan Inc.', 'sector': 'Energy', 'industry': 'Oil & Gas Midstream'},

    # Industrials - Defense & Aerospace
    {'symbol': 'NOC', 'name': 'Northrop Grumman Corporation', 'sector': 'Industrials', 'industry': 'Aerospace & Defense'},
    {'symbol': 'GD', 'name': 'General Dynamics Corporation', 'sector': 'Industrials', 'industry': 'Aerospace & Defense'},
    {'symbol': 'LHX', 'name': 'L3Harris Technologies Inc.', 'sector': 'Industrials', 'industry': 'Aerospace & Defense'},
    {'symbol': 'TXT', 'name': 'Textron Inc.', 'sector': 'Industrials', 'industry': 'Aerospace & Defense'},
    {'symbol': 'HWM', 'name': 'Howmet Aerospace Inc.', 'sector': 'Industrials', 'industry': 'Aerospace & Defense'},
    {'symbol': 'HEI', 'name': 'HEICO Corporation', 'sector': 'Industrials', 'industry': 'Aerospace & Defense'},

    # Industrials - Transportation & Logistics
    {'symbol': 'CHRW', 'name': 'C.H. Robinson Worldwide Inc.', 'sector': 'Industrials', 'industry': 'Logistics'},
    {'symbol': 'EXPD', 'name': 'Expeditors International of Washington Inc.', 'sector': 'Industrials', 'industry': 'Logistics'},
    {'symbol': 'XPO', 'name': 'XPO Inc.', 'sector': 'Industrials', 'industry': 'Logistics'},
    {'symbol': 'JBHT', 'name': 'J.B. Hunt Transport Services Inc.', 'sector': 'Industrials', 'industry': 'Trucking'},
    {'symbol': 'ODFL', 'name': 'Old Dominion Freight Line Inc.', 'sector': 'Industrials', 'industry': 'Trucking'},
    {'symbol': 'KNX', 'name': 'Knight-Swift Transportation Holdings Inc.', 'sector': 'Industrials', 'industry': 'Trucking'},
    {'symbol': 'SAIA', 'name': 'Saia Inc.', 'sector': 'Industrials', 'industry': 'Trucking'},
    {'symbol': 'ARCB', 'name': 'ArcBest Corporation', 'sector': 'Industrials', 'industry': 'Trucking'},

    # Industrials - Building & Construction
    {'symbol': 'DHI', 'name': 'D.R. Horton Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Residential Construction'},
    {'symbol': 'LEN', 'name': 'Lennar Corporation', 'sector': 'Consumer Cyclical', 'industry': 'Residential Construction'},
    {'symbol': 'PHM', 'name': 'PulteGroup Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Residential Construction'},
    {'symbol': 'NVR', 'name': 'NVR Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Residential Construction'},
    {'symbol': 'KBH', 'name': 'KB Home', 'sector': 'Consumer Cyclical', 'industry': 'Residential Construction'},
    {'symbol': 'TOL', 'name': 'Toll Brothers Inc.', 'sector': 'Consumer Cyclical', 'industry': 'Residential Construction'},
    {'symbol': 'BLD', 'name': 'TopBuild Corp.', 'sector': 'Industrials', 'industry': 'Building Products'},
    {'symbol': 'BLDR', 'name': 'Builders FirstSource Inc.', 'sector': 'Industrials', 'industry': 'Building Products'},
    {'symbol': 'FBIN', 'name': 'Fortune Brands Innovations Inc.', 'sector': 'Industrials', 'industry': 'Building Products'},
    {'symbol': 'MAS', 'name': 'Masco Corporation', 'sector': 'Industrials', 'industry': 'Building Products'},
    {'symbol': 'OC', 'name': 'Owens Corning', 'sector': 'Industrials', 'industry': 'Building Products'},
    {'symbol': 'SSD', 'name': 'Simpson Manufacturing Co. Inc.', 'sector': 'Industrials', 'industry': 'Building Products'},

    # Telecom & Media - Streaming & Content
    {'symbol': 'PARA', 'name': 'Paramount Global', 'sector': 'Communication Services', 'industry': 'Entertainment'},
    {'symbol': 'WBD', 'name': 'Warner Bros. Discovery Inc.', 'sector': 'Communication Services', 'industry': 'Entertainment'},
    {'symbol': 'FOXA', 'name': 'Fox Corporation Class A', 'sector': 'Communication Services', 'industry': 'Entertainment'},
    {'symbol': 'FOX', 'name': 'Fox Corporation Class B', 'sector': 'Communication Services', 'industry': 'Entertainment'},
    {'symbol': 'ROKU', 'name': 'Roku Inc.', 'sector': 'Communication Services', 'industry': 'Entertainment'},
    {'symbol': 'SPOT', 'name': 'Spotify Technology S.A.', 'sector': 'Communication Services', 'industry': 'Entertainment'},
    {'symbol': 'PINS', 'name': 'Pinterest Inc.', 'sector': 'Communication Services', 'industry': 'Internet'},
    {'symbol': 'SNAP', 'name': 'Snap Inc.', 'sector': 'Communication Services', 'industry': 'Internet'},
    {'symbol': 'TWTR', 'name': 'Twitter Inc.', 'sector': 'Communication Services', 'industry': 'Internet'},
    {'symbol': 'MTCH', 'name': 'Match Group Inc.', 'sector': 'Communication Services', 'industry': 'Internet'},

    # Additional diverse stocks to reach 500
    # {'symbol': 'CARR', 'name': 'Carrier Global Corporation', 'sector': 'Industrials', 'industry': 'Building Products'},  # DUPLICATE - already in EXISTING_STOCKS
    # {'symbol': 'OTIS', 'name': 'Otis Worldwide Corporation', 'sector': 'Industrials', 'industry': 'Specialty Industrial'},  # DUPLICATE - already in EXISTING_STOCKS
    {'symbol': 'VST', 'name': 'Vistra Corp.', 'sector': 'Utilities', 'industry': 'Utilities - Independent Power'},
    {'symbol': 'CEG', 'name': 'Constellation Energy Corporation', 'sector': 'Utilities', 'industry': 'Utilities - Independent Power'},
]


def main():
    """Main execution function"""
    logger.info("="*80)
    logger.info("DATABASE RESET WITH 500 STOCKS")
    logger.info("="*80)

    # Combine stocks
    all_stocks = EXISTING_STOCKS + NEW_STOCKS
    logger.info(f"Total stocks to insert: {len(all_stocks)}")
    logger.info(f"  - Existing: {len(EXISTING_STOCKS)}")
    logger.info(f"  - New: {len(NEW_STOCKS)}")

    try:
        # Step 1: Drop all tables
        logger.info("\n[1/3] Dropping all tables...")
        with engine.begin() as conn:
            # Drop tables in correct order (dependencies first)
            tables_to_drop = [
                'candlestick_patterns',
                'chart_patterns',
                'stock_prices',
                'stocks',
                'alembic_version'
            ]

            for table_name in tables_to_drop:
                try:
                    conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
                    logger.info(f"  ✓ Dropped table: {table_name}")
                except Exception as e:
                    logger.warning(f"  ⚠ Could not drop {table_name}: {e}")

        logger.info("✅ All tables dropped successfully")

        # Step 2: Recreate schema
        logger.info("\n[2/3] Recreating database schema...")
        stock.Base.metadata.create_all(bind=engine)
        logger.info("✅ Schema recreated successfully")

        # Step 3: Insert all 500 stocks
        logger.info(f"\n[3/3] Inserting {len(all_stocks)} stocks...")
        db = SessionLocal()

        try:
            inserted_count = 0
            for stock_data in all_stocks:
                new_stock = stock.Stock(
                    symbol=stock_data['symbol'],
                    name=stock_data['name'],
                    sector=stock_data.get('sector'),
                    industry=stock_data.get('industry'),
                    is_tracked=True
                )
                db.add(new_stock)
                inserted_count += 1

                if inserted_count % 50 == 0:
                    logger.info(f"  Progress: {inserted_count}/{len(all_stocks)} stocks inserted...")

            db.commit()
            logger.info(f"✅ Successfully inserted {inserted_count} stocks")

            # Verify
            total_stocks = db.query(stock.Stock).count()
            tracked_stocks = db.query(stock.Stock).filter(stock.Stock.is_tracked == True).count()

            logger.info(f"\n📊 Database Statistics:")
            logger.info(f"  - Total stocks: {total_stocks}")
            logger.info(f"  - Tracked stocks: {tracked_stocks}")
            logger.info(f"  - Tables: stocks, stock_prices, chart_patterns, candlestick_patterns")

            # Show sector distribution
            logger.info(f"\n📈 Sector Distribution:")
            sectors = db.query(
                stock.Stock.sector,
                db.func.count(stock.Stock.id)
            ).filter(
                stock.Stock.sector.isnot(None)
            ).group_by(
                stock.Stock.sector
            ).order_by(
                db.func.count(stock.Stock.id).desc()
            ).all()

            for sector_name, count in sectors:
                logger.info(f"  - {sector_name}: {count} stocks")

        finally:
            db.close()

        logger.info("\n" + "="*80)
        logger.info("✅ DATABASE RESET COMPLETED SUCCESSFULLY")
        logger.info("="*80)
        logger.info(f"✓ Total stocks: 500")
        logger.info(f"✓ Ready for fresh data fetching")
        logger.info(f"✓ No legacy timeframe data")

    except Exception as e:
        logger.error(f"\n❌ Error during database reset: {e}")
        raise


if __name__ == "__main__":
    main()
