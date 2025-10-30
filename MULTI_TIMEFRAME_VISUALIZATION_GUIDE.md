# Multi-Timeframe Pattern Visualization Guide

## Overview

Multi-timeframe pattern confirmations are visualized in **THREE locations**:

1. **Pattern List Badges** (Left sidebar)
2. **Chart Markers** (On the price chart)
3. **Pattern Details** (Expanded view)

---

## 1. Pattern List Badges (ChartPatterns.jsx)

### Location
Left sidebar panel → Chart Patterns tab → Pattern cards

### What's Shown

Each pattern card displays:

```
┌──────────────────────────────────────────┐
│ 📉 Head and Shoulders                    │
│ ┌─────────┐ ┌─────────┐                 │
│ │ reversal│ │ bearish │                 │
│ └─────────┘ └─────────┘                 │
│                                          │
│ Start: 10/1/2025                        │
│ End: 10/20/2025                         │
│ Confidence: 94%                         │
│ ✅ 2TF (1d, 4h)  ← MULTI-TIMEFRAME BADGE│
└──────────────────────────────────────────┘
```

### Badge Types

| Badge | Meaning | Confidence Boost |
|-------|---------|------------------|
| 🔥 3TF | Pattern on all 3 timeframes (1h, 4h, 1d) | +80% (1.8x multiplier) |
| ✅ 2TF | Pattern on 2 timeframes | +40% (1.4x multiplier) |
| (none) | Pattern on single timeframe | No boost (1.0x) |

### CSS Styling

**File**: `frontend/src/App.css` (lines 562-601)

```css
.multi-timeframe-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  border-radius: 20px;
  font-weight: 600;
  color: white;
  box-shadow: 0 2px 6px rgba(245, 87, 108, 0.3);
  animation: pulse-glow 2s ease-in-out infinite;
}

@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 2px 6px rgba(245, 87, 108, 0.3); }
  50% { box-shadow: 0 2px 12px rgba(245, 87, 108, 0.6); }
}
```

### Hover Tooltip

Hovering over the badge shows:
```
Detected on: 1d, 4h
```

### Code Reference

**File**: `frontend/src/components/ChartPatterns.jsx` (lines 518-531)

```jsx
{pattern.confirmation_level && pattern.confirmation_level >= 2 && (
  <div className="info-item multi-timeframe-badge">
    <span className="mtf-badge-icon">
      {pattern.confirmation_level === 3 ? '🔥' : '✅'}
    </span>
    <span className="mtf-badge-text">
      {pattern.confirmation_level}TF
    </span>
    <span className="mtf-badge-detail" title={...}>
      {pattern.detected_on_timeframes && `(${pattern.detected_on_timeframes.join(', ')})`}
    </span>
  </div>
)}
```

---

## 2. Chart Markers (StockChart.jsx)

### Location
Right panel → Chart tab → Price chart visualization

### What's Shown

Patterns are drawn on the chart with:

#### A. Color Intensity

| Pattern Type | 1TF Color | 2TF Color | 3TF Color |
|--------------|-----------|-----------|-----------|
| Bullish | #28a745 (green) | #33cc33 (bright green) | #00ff00 (neon green) |
| Bearish | #dc3545 (red) | #ff3333 (bright red) | #ff0000 (neon red) |
| Neutral | #6c757d (gray) | #4488ff (bright blue) | #0066ff (neon blue) |

**Visual Effect**: Multi-timeframe patterns "pop" more on the chart with brighter colors!

#### B. Marker Labels

Start/End markers include multi-timeframe badges:

```
1TF Pattern:
  ↓ Head and Shoulders START
  ↓ Head and Shoulders END

2TF Pattern:
  ↓ Head and Shoulders ✅2TF START
  ↓ Head and Shoulders ✅2TF END

3TF Pattern:
  ↓ Head and Shoulders 🔥3TF START
  ↓ Head and Shoulders 🔥3TF END
```

#### C. Marker Size

- **1TF patterns**: Size 3 (standard)
- **2TF patterns**: Size 4 (larger)
- **3TF patterns**: Size 4 (larger)

Multi-timeframe patterns are 33% larger for easier visibility!

### Code Reference

**File**: `frontend/src/components/StockChart.jsx` (lines 448-514)

```jsx
// Enhanced color for multi-timeframe patterns
const confirmationLevel = pattern.confirmation_level || 1;
let primaryColor = /* base color */;

if (confirmationLevel >= 3) {
  primaryColor = /* bright/neon color */;
} else if (confirmationLevel >= 2) {
  primaryColor = /* moderately bright color */;
}

// Add multi-timeframe indicator to marker text
const mtfLabel = confirmationLevel >= 3 ? ' 🔥3TF' :
                 confirmationLevel >= 2 ? ' ✅2TF' : '';

allMarkers.push({
  text: `${pattern.pattern_name}${mtfLabel} START`,
  size: confirmationLevel >= 2 ? 4 : 3,
  color: primaryColor,
  ...
});
```

---

## 3. Pattern Details (Expanded View)

### Location
Left sidebar → Click expand button (▶) on any pattern card

### What's Shown

When a pattern card is expanded, you see:

```
┌──────────────────────────────────────────┐
│ 📉 Head and Shoulders                    │
│ ✅ 2TF (1d, 4h)                          │
├──────────────────────────────────────────┤
│ Pattern Visualization:                   │
│   [ASCII diagram of pattern]             │
├──────────────────────────────────────────┤
│ Pattern Description:                     │
│   A Head and Shoulders pattern is a...   │
├──────────────────────────────────────────┤
│ Key Price Levels:                        │
│   Breakout: $150.25                      │
│   Target: $145.00                        │
│   Stop Loss: $152.50                     │
├──────────────────────────────────────────┤
│ Pattern Metrics:                         │
│   ✅ Base Confidence: 65%                │
│   ✅ Adjusted Confidence: 91%            │
│   ✅ Confirmation Level: 2TF             │
│   ✅ Alignment Score: 0.85               │
│   ✅ Detected on: 1d, 4h                 │
└──────────────────────────────────────────┘
```

### Multi-Timeframe Metadata

The expanded view shows detailed multi-timeframe information:

- **Base Confidence**: Original confidence before boost (e.g., 65%)
- **Adjusted Confidence**: After multi-timeframe boost (e.g., 91%)
- **Confirmation Level**: 1TF, 2TF, or 3TF
- **Alignment Score**: How well pattern aligns across timeframes (0.0-1.0)
- **Detected On**: List of timeframes (e.g., "1d, 4h")

---

## Summary: Where to Look

### Quick Reference

| What You Want | Where to Look |
|---------------|---------------|
| See which patterns are multi-timeframe | Left sidebar badges (🔥 or ✅) |
| See multi-timeframe patterns on chart | Chart tab - brighter colors + larger markers |
| Understand confidence boost details | Expand pattern card |
| See detected timeframes | Badge hover tooltip or expanded view |
| Compare before/after confidence | Expanded view (Base vs Adjusted) |

---

## Visual Example Walkthrough

### Scenario: ABNB Stock with 2TF Pattern

1. **Detect Patterns**
   ```
   Click "🔍 Detect Chart Patterns"
   → Analyzing 1h, 4h, 1d timeframes
   → Found: Rounding Bottom on 1d and 4h
   ```

2. **Left Sidebar Shows**
   ```
   📈 Rounding Bottom
   reversal | bullish
   Start: 10/1/2025
   End: 10/20/2025
   Confidence: 94%
   ✅ 2TF (1d, 4h)  ← LOOK HERE!
   ```

3. **Switch to Chart Tab**
   ```
   Pattern markers on chart:
   ↓ Rounding Bottom ✅2TF START (bright green, size 4)
   ↓ Rounding Bottom ✅2TF END (bright green, size 4)

   Trendlines drawn in bright green (#33cc33)
   ```

4. **Expand Pattern Card**
   ```
   Base Confidence: 65%
   Adjusted Confidence: 94% (+45% boost!)
   Confirmation Level: 2TF
   Alignment Score: 0.92 (excellent)
   Detected on: 1d, 4h
   ```

---

## API Response Structure

The multi-timeframe data comes from the backend API:

```json
{
  "patterns": [
    {
      "pattern_name": "Rounding Bottom",
      "confidence_score": 0.94,

      // Multi-timeframe fields
      "primary_timeframe": "1d",
      "detected_on_timeframes": ["1d", "4h"],
      "confirmation_level": 2,
      "base_confidence": 0.65,
      "adjusted_confidence": 0.94,
      "alignment_score": 0.92,
      "is_multi_timeframe_confirmed": true
    }
  ]
}
```

---

## Confidence Boost Calculation

### Formula

```
Base Confidence: 65%
↓
Timeframe Multiplier (2TF): × 1.4
↓
Alignment Bonus: × 1.12 (based on 0.92 alignment score)
↓
Adjusted Confidence: 65% × 1.4 × 1.12 = 101.9%
↓
Capped at MAX_CONFIDENCE: 95%
↓
Final: 94%
```

### Visual Representation

```
┌──────────────────────────────────────┐
│ Single Timeframe (1TF)               │
│ Confidence: 65%                      │
│ [████████████░░░░░░░░] 65%           │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ Multi-Timeframe (2TF) ✅             │
│ Base: 65% → Adjusted: 94%           │
│ [██████████████████░░] 94%           │
│ Boost: +45%                          │
└──────────────────────────────────────┘
```

---

## User Actions

### How to See Multi-Timeframe Patterns

1. **Fetch 1h data** for at least 3 months
   ```
   Period: 3mo, 6mo, or 1y
   Interval: 1h
   ```

2. **Detect patterns** with reasonable settings
   ```
   min_pattern_length: 15-20
   peak_order: 4-5
   min_confidence: 0.0 (to see all patterns)
   remove_overlaps: false (to see all matches)
   ```

3. **Look for badges** in pattern list
   - 🔥 3TF = Ultra-reliable (rarely seen)
   - ✅ 2TF = Very reliable (common with good data)
   - No badge = Single timeframe (standard)

4. **Switch to Chart tab** to see visual highlighting

5. **Expand pattern** to see detailed metrics

---

## Filtering by Confirmation Level

### Future Enhancement

Could add filter buttons:
```
[All Patterns] [3TF Only 🔥] [2TF+ ✅] [1TF Only]
```

This would help focus on the highest-quality multi-timeframe patterns.

---

## Testing Multi-Timeframe Visualization

### Test Checklist

- [ ] Badge appears on 2TF patterns in pattern list
- [ ] Badge shows correct emoji (✅ for 2TF, 🔥 for 3TF)
- [ ] Badge shows timeframes on hover
- [ ] Chart markers include "2TF" or "3TF" in text
- [ ] Chart markers are brighter/larger for multi-timeframe
- [ ] Expanded view shows all multi-timeframe metrics
- [ ] Confidence boost is visible (base vs adjusted)

### Example Test Case

**Setup**:
1. Stock: ABNB (stock_id: 27)
2. Data: 6 months of 1h data
3. Settings: min_pattern_length=15, peak_order=4

**Expected**:
- Multiple patterns detected
- Some with ✅ 2TF badges
- Chart shows bright colors for multi-timeframe
- Expanded view shows confidence boost details

---

## Status

✅ **Implemented** - October 29, 2025

Multi-timeframe patterns are now fully visualized in:
1. Pattern list badges (with pulsing animation)
2. Chart markers (with brighter colors and labels)
3. Pattern detail view (with full metrics)

Users can easily identify high-confidence multi-timeframe patterns at a glance!
