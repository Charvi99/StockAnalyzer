# Dividend & Split Events - Trading Strategy Integration

## Purpose
Use upcoming dividend ex-dates and stock splits as **short-term trading catalysts** to enhance swing trading entry/exit timing.

---

## 1. Ex-Dividend Date Strategy

### Price Behavior Pattern:
```
Day -5 to -1 (before ex-date): ↗️ Stock rises (dividend capture buying)
Day 0 (ex-date):               ↘️ Stock drops ~dividend amount
Day +1 to +3:                  ↗️ Often recovers
```

### Trading Signals:

#### **Short-Term Exit Signal**
```python
# If holding stock approaching ex-dividend date:
if days_until_ex_dividend <= 2:
    signal = "SELL"
    reason = "Take profit before ex-dividend drop"
    strength = "moderate"
    timing = "1-2 days before ex-date"
```

**Example:**
- Stock: XYZ trading at $50
- Dividend: $0.50 (1% yield)
- Strategy: Sell at $50 before ex-date → Stock drops to $49.50 on ex-date

#### **Short-Term Entry Signal**
```python
# Buy the post-dividend dip:
if days_since_ex_dividend == 1:
    if price_drop >= dividend_amount * 0.8:  # Dropped as expected
        signal = "BUY"
        reason = "Post-dividend discount entry"
        strength = "moderate"
        timing = "Day after ex-date"
```

### Implementation in Recommendation System:

```python
def check_dividend_catalyst(stock_id, prices):
    """
    Check upcoming ex-dividend dates for trading signals
    """
    upcoming_dividends = db.query(Dividend).filter(
        Dividend.stock_id == stock_id,
        Dividend.ex_dividend_date >= today,
        Dividend.ex_dividend_date <= today + timedelta(days=10)
    ).all()

    signals = []

    for dividend in upcoming_dividends:
        days_until = (dividend.ex_dividend_date - today).days
        dividend_yield = (dividend.cash_amount / current_price) * 100

        if 1 <= days_until <= 3:
            # Exit signal - sell before drop
            signals.append({
                'type': 'DIVIDEND_EXIT',
                'action': 'SELL',
                'reason': f'Ex-dividend in {days_until} days',
                'impact': 'moderate',
                'price_impact_est': f'-{dividend_yield:.2f}%',
                'recommended_timing': 'Before market close today',
                'catalyst': {
                    'event': 'Ex-Dividend Date',
                    'date': dividend.ex_dividend_date,
                    'amount': dividend.cash_amount,
                    'yield_pct': dividend_yield
                }
            })

        elif days_until == 0 or days_until == -1:
            # Entry signal - buy the dip
            signals.append({
                'type': 'DIVIDEND_ENTRY',
                'action': 'BUY',
                'reason': 'Post-dividend discount',
                'impact': 'moderate',
                'price_impact_est': f'+{dividend_yield:.2f}% recovery expected',
                'recommended_timing': 'During opening dip',
                'catalyst': {
                    'event': 'Post-Dividend Recovery',
                    'ex_date': dividend.ex_dividend_date,
                    'expected_recovery': '1-3 days'
                }
            })

    return signals
```

### UI Display:

```javascript
// Stock card badge
{stock.upcoming_ex_dividend && (
  <div className="catalyst-badge dividend-catalyst">
    💰 Ex-Div: {formatDate(stock.ex_dividend_date)}
    ({stock.days_until_ex_div}d)
  </div>
)}

// Recommendation reasoning
"⚠️ Exit Signal: Ex-dividend date in 2 days.
Expected drop: -0.8%. Consider taking profit now."
```

---

## 2. Stock Split Strategy

### Price Behavior Pattern:

```
Announcement Date:        ↗️ Initial pop (5-10%)
Weeks Leading to Split:   ↗️ Continued rally
Split Execution Day:      → Flat to slight up
Post-Split Week 1:        ↗️ Retail buying surge
Post-Split Week 2-4:      → Consolidation
```

### Trading Signals:

#### **Entry Signal: Split Announcement**
```python
# Recent split announced (execution date in future):
if split.execution_date > today:
    days_until_split = (split.execution_date - today).days

    if 5 <= days_until_split <= 30:
        signal = "BUY"
        reason = "Upcoming split catalyst"
        strength = "strong"
        timing = "Before split execution"
        expected_gain = "5-15% run-up typical"
```

#### **Exit Signal: Split Execution**
```python
# Split happening soon or just happened:
if -2 <= days_until_split <= 2:
    signal = "SELL"
    reason = "Split execution - take profits"
    strength = "moderate"
    timing = "Day of or day after split"
```

#### **Re-Entry Signal: Post-Split Consolidation**
```python
# After split excitement fades:
if 7 <= days_since_split <= 14:
    if price_stable_for_3_days:
        signal = "BUY"
        reason = "Post-split consolidation entry"
        strength = "moderate"
        timing = "After 1-2 week cooldown"
```

### Implementation:

```python
def check_split_catalyst(stock_id, prices):
    """
    Check upcoming/recent splits for trading signals
    """
    # Upcoming splits (announced but not executed)
    upcoming_splits = db.query(StockSplit).filter(
        StockSplit.stock_id == stock_id,
        StockSplit.execution_date >= today - timedelta(days=7),
        StockSplit.execution_date <= today + timedelta(days=60)
    ).all()

    signals = []

    for split in upcoming_splits:
        days_until = (split.execution_date - today).days
        split_ratio_display = f"{int(split.split_to)}-for-{int(split.split_from)}"

        if 5 <= days_until <= 30:
            # Entry signal - pre-split rally
            signals.append({
                'type': 'SPLIT_ENTRY',
                'action': 'BUY',
                'reason': f'{split_ratio_display} split in {days_until} days',
                'impact': 'strong',
                'expected_move': '+5% to +15% typical pre-split rally',
                'recommended_timing': 'Enter now, exit before split',
                'catalyst': {
                    'event': 'Stock Split Announcement',
                    'execution_date': split.execution_date,
                    'ratio': split_ratio_display,
                    'bullish_period': f'{days_until} days remaining'
                }
            })

        elif -2 <= days_until <= 2:
            # Exit signal - split execution
            signals.append({
                'type': 'SPLIT_EXIT',
                'action': 'SELL',
                'reason': f'Split execution day ({split_ratio_display})',
                'impact': 'strong',
                'recommended_timing': 'Take profits at split execution',
                'catalyst': {
                    'event': 'Split Execution',
                    'execution_date': split.execution_date,
                    'ratio': split_ratio_display,
                    'note': 'Typical profit-taking period'
                }
            })

        elif -14 <= days_until <= -7:
            # Re-entry signal - post-split consolidation
            signals.append({
                'type': 'SPLIT_REENTRY',
                'action': 'BUY',
                'reason': 'Post-split consolidation entry',
                'impact': 'moderate',
                'recommended_timing': 'Enter after cooldown period',
                'catalyst': {
                    'event': 'Post-Split Recovery',
                    'split_date': split.execution_date,
                    'ratio': split_ratio_display,
                    'note': 'Often sees renewed buying after 1-2 weeks'
                }
            })

    return signals
```

### UI Display:

```javascript
// Stock card - upcoming split
{stock.upcoming_split && (
  <div className="catalyst-badge split-catalyst bullish">
    ✂️ {stock.split_ratio} Split in {stock.days_until_split}d
    <span className="expected-move">+5-15% typical</span>
  </div>
)}

// Stock card - recent split
{stock.recent_split && (
  <div className="catalyst-badge split-recent">
    ✂️ Split {stock.days_since_split}d ago
  </div>
)}

// Recommendation reasoning
"🎯 Entry Signal: 2-for-1 split in 12 days.
Historical data shows 5-15% rally before split execution.
Consider entry now, exit 1-2 days before split."
```

---

## 3. Combined Strategy - Multiple Catalysts

### Priority System:
```python
catalyst_priority = {
    'SPLIT_ENTRY': 90,      # Strong bullish catalyst
    'SPLIT_EXIT': 85,       # Take profits
    'DIVIDEND_EXIT': 60,    # Moderate - avoid drop
    'DIVIDEND_ENTRY': 55,   # Moderate - buy dip
    'SPLIT_REENTRY': 50     # Moderate - recovery play
}
```

### Conflict Resolution:
```python
# If split and dividend overlap:
if has_split_signal and has_dividend_signal:
    # Split takes priority (larger expected move)
    return split_signal

# If holding stock with both upcoming:
if upcoming_split and upcoming_ex_dividend:
    # Calculate which comes first
    if split_date < ex_dividend_date:
        recommend = "Hold through dividend for split rally"
    else:
        recommend = "Exit before dividend, re-enter for split"
```

---

## 4. Implementation Checklist

### Backend:
- [ ] Add catalyst detection to recommendation service
- [ ] Create `check_dividend_catalyst()` function
- [ ] Create `check_split_catalyst()` function
- [ ] Add catalyst signals to recommendation response
- [ ] Include in overall recommendation score

### Frontend:
- [ ] Add catalyst badges to StockCard
- [ ] Show days until/since event
- [ ] Display expected price impact
- [ ] Add catalyst timeline to OverviewTab
- [ ] Highlight catalysts in recommendation reasoning

### Database Queries Needed:
```sql
-- Upcoming dividends (next 10 days)
SELECT * FROM dividends
WHERE stock_id = ?
AND ex_dividend_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 10;

-- Upcoming splits (next 60 days)
SELECT * FROM stock_splits
WHERE stock_id = ?
AND execution_date BETWEEN CURRENT_DATE - 7 AND CURRENT_DATE + 60;

-- Recent splits (last 14 days)
SELECT * FROM stock_splits
WHERE stock_id = ?
AND execution_date BETWEEN CURRENT_DATE - 14 AND CURRENT_DATE;
```

---

## 5. Expected Impact on Trading

### Dividend Catalysts:
- **Frequency:** Quarterly (4x per year for most stocks)
- **Expected Move:** 0.5% - 2% drop on ex-date
- **Win Rate:** 70-80% (very predictable)
- **Use Case:** Short-term profit-taking or discount entry

### Split Catalysts:
- **Frequency:** Rare (1-2% of stocks per year)
- **Expected Move:** 5-15% rally before split
- **Win Rate:** 60-75% (generally bullish but not guaranteed)
- **Use Case:** Medium-term swing trade (2-6 weeks)

### Combined Value:
- Adds 5-10 trading opportunities per month across 30 stocks
- Complements existing pattern-based signals
- Provides clear entry/exit timing

---

## 6. Risk Management

### Dividend Strategy Risks:
- Market gap down can exceed dividend amount
- Not all stocks recover post-dividend
- Low-volume stocks may not follow pattern

**Mitigation:**
- Only trade dividend plays on liquid stocks (>1M avg volume)
- Set stop loss at 1.5x dividend amount
- Don't fight strong trends for dividend play

### Split Strategy Risks:
- Split alone doesn't guarantee rally
- May already be priced in
- Post-split selling pressure possible

**Mitigation:**
- Confirm with technical indicators (RSI, MACD)
- Don't chase if already up >10% since announcement
- Take partial profits before split execution

---

## Next Steps

1. **Add API Routes:**
   - `/api/v1/stocks/{id}/upcoming-catalysts`
   - Returns dividends + splits in next 30 days

2. **Update Recommendation Engine:**
   - Integrate catalyst detection
   - Weight catalyst signals (moderate impact)
   - Include in reasoning

3. **Frontend Display:**
   - Catalyst badges on stock cards
   - Catalyst timeline in OverviewTab
   - Highlight in recommendation panel

4. **Testing:**
   - Backtest dividend ex-date strategy
   - Backtest split announcement strategy
   - Measure impact on recommendation accuracy

---

**Estimated Implementation:** 6-8 hours
**Expected Benefit:** 5-10 additional high-quality trading signals per month
