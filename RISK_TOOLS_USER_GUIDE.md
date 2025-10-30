# Risk Tools - User Guide

**Date**: October 30, 2025

---

## Overview

The Risk Tools feature provides two powerful calculators to help you manage risk across your trading portfolio:

1. **Trailing Stop Calculator** - Protect your profits with ATR-based trailing stops
2. **Portfolio Heat Monitor** - Track total risk across all open positions

---

## How to Access Risk Tools

### Step 1: Open Stock Detail View
1. Click on any stock in your dashboard
2. The stock detail view will open in side-by-side mode

### Step 2: Navigate to Risk Tools Tab
1. Look at the left panel tabs
2. Click on **"🔥 Risk Tools"** (last tab)
3. The Risk Tools section will display both calculators

### Step 3: Use the Tools
- **Top Section**: Trailing Stop Calculator
- **Bottom Section**: Portfolio Heat Monitor

---

## Trailing Stop Calculator

### What It Does
Calculates dynamic stop-loss levels that follow price upward but never move down, protecting your profits while giving trades room to breathe.

### How to Use

1. **Entry Price**: Enter your original entry price (defaults to current price)
2. **Current Price**: Shows the current market price (read-only)
3. **Direction**: Select "Long" or "Short"
4. **ATR Multiplier**: How many ATRs below/above price to place stop (default: 1.0)
5. Click **"🎯 Calculate Trailing Stop"**

### Understanding the Results

#### Trailing Stop Level
- **Green background**: Your dynamic stop-loss price
- This is where you should place your actual stop-loss order
- Updates as price moves in your favor

#### Current Profit
- Shows your unrealized profit/loss
- 📈 = Profit (green)
- 📉 = Loss (red)

#### Profit in ATRs
- How many ATR multiples you're up
- 🔥 = 3+ ATRs (excellent!)
- ⚡ = 1.5-3 ATRs (good)
- 💤 = <1.5 ATRs (early)

#### Recommendations
- **Move Stop to Breakeven** (1.5 ATR profit): Protect your capital
- **Consider Partial Profit** (3.0 ATR profit): Take some profits off the table

### Example

```
Entry Price: $150.00
Current Price: $155.00
Direction: Long
ATR Multiplier: 1.0

Results:
✅ Trailing Stop: $152.10
✅ Current Profit: $5.00
✅ Profit in ATRs: 1.72x
✅ Recommendation: Move stop to breakeven
```

**What This Means**:
- You're up $5/share
- That's 1.72 times the stock's average volatility
- Move your stop to $150 (breakeven) to protect capital
- Current stop at $152.10 gives room for normal volatility

---

## Portfolio Heat Monitor

### What It Does
Tracks the total risk (heat) across all your open positions, preventing over-leveraging and helping you stay within your risk limits.

### How to Use

1. **Set Account Parameters**:
   - **Account Capital ($)**: Your total trading capital
   - **Max Heat Allowed (%)**: Maximum portfolio risk (default: 6%)

2. **Add Your Positions**:
   - Click **"+ Add Position"** for each open trade
   - Enter for each position:
     - **Symbol**: Stock ticker (e.g., AAPL)
     - **Entry**: Your entry price
     - **Stop Loss**: Your stop-loss price
     - **Size**: Number of shares

3. Click **"🔥 Calculate Portfolio Heat"**

### Understanding the Results

#### Portfolio Heat Gauge
- **Visual gauge**: Shows current risk vs. max allowed
- **Color coding**:
  - ✅ Green (0-50%): Safe - plenty of room
  - 🟡 Blue (50-70%): Caution - getting full
  - ⚠️ Amber (70-90%): Warning - near limit
  - 🔴 Red (90%+): Danger - over-leveraged

#### Risk Metrics

1. **Total Risk Amount**
   - Sum of all position risks: `(Entry - Stop) × Size`
   - This is how much you'd lose if ALL stops hit

2. **Positions at Risk**
   - Number of open positions being tracked

3. **Can Add Position?**
   - ✅ YES: You have room for more positions
   - 🚫 NO: Portfolio heat too high, close positions first

4. **Remaining Capacity**
   - How much more risk you can take
   - Use this to size new positions

### Example

```
Account Capital: $10,000
Max Heat: 6.0%

Open Positions:
1. AAPL: Entry $150, Stop $145, Size 10 → Risk: $50
2. GOOGL: Entry $140, Stop $136, Size 8 → Risk: $32
3. TSLA: Entry $200, Stop $195, Size 6 → Risk: $30

Results:
🔥 Portfolio Heat: 1.12%
💵 Total Risk: $112.00
📊 Positions at Risk: 3
✅ Can Add Position: YES
💰 Remaining Capacity: $488.00
```

**What This Means**:
- Total portfolio risk is only 1.12% (safe)
- If all 3 stops hit, you'd lose $112
- You can add more positions
- You have $488 of remaining risk capacity (4.88% of $10,000)

### Warning Alerts

If portfolio heat exceeds your limit, you'll see:

```
⚠️ Portfolio Heat Too High!
You cannot add more positions. Close existing positions or increase your account capital.
```

**What to Do**:
- Close some positions
- Tighten stops to reduce risk
- Increase account capital
- Wait for some positions to reach targets

---

## Best Practices

### Trailing Stops

1. **Use 1.0-1.5 ATR multiplier** for most trades
   - 1.0 ATR: Tighter, protects profits faster
   - 1.5 ATR: Looser, gives more room

2. **Move to breakeven at 1.5 ATR profit**
   - Protects your capital
   - Lets winners run risk-free

3. **Take partial profits at 3 ATR**
   - Lock in some gains
   - Reduce position size
   - Let remainder run

4. **Never move stops backwards**
   - Only move up (longs) or down (shorts)
   - Trailing stops are one-way only

### Portfolio Heat

1. **Keep portfolio heat under 6%**
   - Industry standard for swing trading
   - Prevents catastrophic losses

2. **Start smaller (2-3%) when learning**
   - Build confidence
   - Learn the system
   - Scale up gradually

3. **Size positions based on remaining capacity**
   - Check "Remaining Capacity"
   - Use half of it for next position
   - Always leave buffer room

4. **Update regularly**
   - Recalculate after each trade
   - Update stops as they trail
   - Monitor throughout the day

---

## Common Questions

### Q: What is ATR?
**A**: Average True Range - measures volatility. Higher ATR = more volatile stock.

### Q: Why 1.5 ATR for breakeven?
**A**: Studies show 1.5 ATR gives high probability the trade will continue in your favor.

### Q: Why 6% max portfolio heat?
**A**: Professional traders use 2-6%. It prevents blowing up your account while allowing multiple positions.

### Q: Can I use different ATR multipliers?
**A**: Yes! Adjust based on:
- Volatile stocks → Higher multiplier (1.5-2.0)
- Less volatile → Lower multiplier (0.8-1.2)
- Your risk tolerance

### Q: What if I have more than 3 positions?
**A**: Keep adding them! The monitor handles any number of positions. Just keep total heat under your max.

---

## Tips for Success

1. **Calculate trailing stops daily**
   - Prices change
   - Your stop should follow
   - Takes 30 seconds

2. **Check portfolio heat before adding positions**
   - Don't over-leverage
   - Stay within your limits
   - Sleep better at night

3. **Honor your stops**
   - If stop hits, exit immediately
   - Don't move stops backwards
   - Trust the system

4. **Review performance weekly**
   - Are you using stops effectively?
   - Is your heat under control?
   - Adjust parameters if needed

---

## Technical Details

### Trailing Stop Formula
```
Long:  Trailing Stop = Current Price - (ATR × Multiplier)
Short: Trailing Stop = Current Price + (ATR × Multiplier)

Stop never moves backwards:
Long:  Stop = max(Calculated Stop, Previous Stop, Entry Price)
Short: Stop = min(Calculated Stop, Previous Stop, Entry Price)
```

### Portfolio Heat Formula
```
Position Risk = |Entry Price - Stop Loss| × Position Size
Total Risk = Sum of all Position Risks
Portfolio Heat % = (Total Risk / Account Capital) × 100
```

---

## Troubleshooting

### "Failed to calculate trailing stop"
- **Cause**: Not enough price data
- **Fix**: Click "Fetch Data" to load more historical prices

### "Position size is 0"
- **Cause**: Stop too close to entry, or account too small
- **Fix**: Use wider stop or increase account capital

### "Portfolio heat too high"
- **Cause**: Too many positions or stops too far
- **Fix**: Close positions or tighten stops

---

## Support

Need help? Check:
1. This user guide
2. Hover tooltips in the UI
3. Visual guide in Trailing Stop Calculator
4. Documentation: `RISK_MANAGEMENT_REFACTORING.md`

---

**Last Updated**: October 30, 2025
**Version**: 1.0
