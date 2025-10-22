# Polygon.io Setup Guide

## Why Polygon.io?

Polygon.io is a reliable, professional-grade financial data provider with excellent free tier options:

- **5 API requests per minute** (free tier)
- **No daily request limit** on free tier
- Official API with stable, fast access
- Real-time and historical market data
- Excellent documentation and Python SDK
- Used by professional traders and developers

## Quick Setup (3 minutes)

### Step 1: Get Your Free API Key

1. Visit: https://polygon.io/dashboard/signup
2. Create a free account (GitHub or Google sign-in available)
3. Verify your email address
4. Navigate to your dashboard: https://polygon.io/dashboard/api-keys
5. Copy your API key (looks like: `ABCD1234EFGH5678IJKL`)

**Free Tier Includes:**
- ✅ Unlimited stocks, options, forex, crypto data
- ✅ 5 requests per minute
- ✅ 2 years of historical data
- ✅ Previous day's OHLC data
- ✅ Real-time quotes (15-minute delayed for free tier)

### Step 2: Configure Your Application

**Option A: Using .env file** (Recommended)

```bash
# In the StockAnalyzer directory, create a .env file
cp .env.example .env

# Edit .env file and replace with your key
POLYGON_API_KEY=YOUR_ACTUAL_KEY_HERE
```

**Option B: Set environment variable directly**

Windows PowerShell:
```powershell
$env:POLYGON_API_KEY="YOUR_ACTUAL_KEY_HERE"
```

Windows CMD:
```cmd
set POLYGON_API_KEY=YOUR_ACTUAL_KEY_HERE
```

Linux/Mac:
```bash
export POLYGON_API_KEY="YOUR_ACTUAL_KEY_HERE"
```

### Step 3: Restart the Application

```bash
# Stop containers
docker-compose down

# Rebuild and start with new configuration
docker-compose up --build
```

## Testing Polygon.io Integration

Once running, test the API:

```bash
# Test stock data fetch (AAPL = Apple)
curl -X POST http://localhost:8000/api/v1/stocks/1/fetch \
  -H "Content-Type: application/json" \
  -d '{"period":"1mo","interval":"1d"}'
```

Expected response:
```json
{
  "success": true,
  "message": "Successfully fetched and stored data for AAPL",
  "records_fetched": 21,
  "records_saved": 21
}
```

Then open http://localhost:3000, click "View Details" on AAPL, and see the chart!

## Rate Limits

**Free Tier Limits:**
- 5 API calls per minute
- No daily limit

**Tips to stay within limits:**
- Fetch data for one stock at a time (our app already does this)
- The backend automatically adds delays between requests
- Store data in database and refresh periodically instead of constantly

**Rate Limit Handling:**
Our implementation automatically:
- Adds 12-second delays between requests (5 requests/minute = 12s intervals)
- Retries with exponential backoff if rate limits are hit
- Logs clear messages when rate limits occur

## Supported Period and Interval Combinations

### Periods
- `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max`

### Intervals
- `1d` or `daily` - Daily data (default, most common)
- `1wk` or `weekly` - Weekly data
- `1mo` or `monthly` - Monthly data

**Note:** Intraday intervals (1m, 5m, 1h) are not included in the free tier for historical data, but can be added to paid plans.

## Troubleshooting

### "Using demo key" warning

This means you haven't set your API key. The demo key has **very limited** access.

**Solution:** Follow Step 2 above to set your API key.

### "Rate limit reached" error

You've hit the 5 requests/minute limit.

**Solutions:**
- Wait 1 minute and try again
- The app automatically handles this with delays
- If fetching multiple stocks, do them one at a time

### "Invalid API key" error

Your API key is incorrect or expired.

**Solutions:**
- Check for typos in your .env file
- Make sure there are no extra spaces or quotes
- Verify your API key in Polygon.io dashboard
- Generate a new API key if needed

### Data not appearing in charts

**Check:**
1. API key is set correctly in .env file
2. Backend logs show "Successfully fetched" message: `docker-compose logs backend`
3. No error messages in logs
4. Database has data:
   ```bash
   docker-compose exec database psql -U stockuser -d stock_analyzer -c "SELECT COUNT(*) FROM stock_prices;"
   ```

### Authentication errors

**Problem:** `401 Unauthorized` or similar errors

**Solutions:**
- Verify your API key is active in Polygon.io dashboard
- Check if your free trial has expired (shouldn't happen with free tier)
- Ensure you've verified your email address

## API Key Security

**Important Security Notes:**

1. **Never commit .env to git** - It's already in .gitignore
2. **Don't share your API key publicly**
3. **Rotate your key** if accidentally exposed (you can generate new keys in dashboard)
4. **Monitor usage** in Polygon.io dashboard to detect unauthorized use

The .env file is automatically ignored by git, so your key stays private.

## Free vs Paid Comparison

| Feature | Free Tier | Starter ($29/mo) | Developer ($99/mo) |
|---------|-----------|------------------|-------------------|
| Requests/min | 5 | 100 | 1000 |
| Historical data | 2 years | Unlimited | Unlimited |
| Real-time data | 15-min delayed | Real-time | Real-time |
| Support | Community | Email | Priority |

**Free tier is perfect for this project!** You get everything you need to build and test your stock analysis application.

## Advanced Features

### Available Data (Free Tier)

- ✅ Daily OHLC (Open, High, Low, Close) bars
- ✅ Stock splits and dividends
- ✅ Previous day's close
- ✅ Ticker details (name, sector, industry)
- ✅ 2 years of historical data

### Future Enhancements (When Ready)

Once you're ready to expand, Polygon.io supports:
- Technical indicators
- Real-time WebSocket feeds
- Options data
- Forex and crypto markets
- News and sentiment analysis

## Performance Tips

**Optimize API Usage:**

1. **Batch operations wisely** - Fetch longer periods (1y) instead of multiple short periods
2. **Cache in database** - Store data and refresh once daily
3. **Use previous close endpoint** - For current price without full historical fetch
4. **Monitor dashboard** - Check your usage at https://polygon.io/dashboard/usage

**Database Strategy:**

```bash
# Fetch initial data (one-time)
curl -X POST http://localhost:8000/api/v1/stocks/1/fetch \
  -H "Content-Type: application/json" \
  -d '{"period":"1y","interval":"1d"}'

# Daily updates (fetch only new data)
curl -X POST http://localhost:8000/api/v1/stocks/1/fetch \
  -H "Content-Type: application/json" \
  -d '{"period":"1d","interval":"1d"}'
```

## Next Steps

Once Polygon.io is working:

1. ✅ Fetch historical data for all 5 pre-loaded stocks
2. ✅ Explore the interactive charts in the frontend
3. ✅ Move to Phase 3: Technical indicators and ML predictions
4. ✅ Build automated daily data updates
5. ✅ Create your stock analysis and prediction system!

## Resources

- **Polygon.io Dashboard:** https://polygon.io/dashboard
- **Official Documentation:** https://polygon.io/docs/stocks/getting-started
- **Python SDK Docs:** https://polygon-api-client.readthedocs.io/
- **API Status:** https://status.polygon.io/
- **Community Support:** https://polygon.io/community

## Application Support

- **Application Issues:** Check `docker-compose logs backend`
- **Database Issues:** Review DEBUGGING.md in this project
- **Questions:** See README.md for troubleshooting guide

## Summary

**Polygon.io provides everything you need for this project:**
- ✅ 5 requests per minute (sufficient for personal use)
- ✅ No daily request limit
- ✅ Professional-grade, reliable API
- ✅ Excellent Python SDK
- ✅ Free tier perfect for learning and development
- ✅ Easy upgrade path when you need more features

Get your free API key now and start analyzing stocks! 📈

## Quick Reference

```bash
# Environment setup
POLYGON_API_KEY=your_key_here

# Test connection
curl http://localhost:8000/health

# Fetch data
curl -X POST http://localhost:8000/api/v1/stocks/1/fetch \
  -H "Content-Type: application/json" \
  -d '{"period":"1mo","interval":"1d"}'

# View logs
docker-compose logs -f backend

# Restart backend
docker-compose restart backend
```

Happy analyzing! 🚀
