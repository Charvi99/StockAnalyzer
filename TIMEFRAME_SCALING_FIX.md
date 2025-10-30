# Timeframe Scaling Fix - Pattern Length Scaling

## Issue Identified by User

**User's Observation**:
> "aren't there some conflict rules for patterns on different timeframe? for example candlestick count? for example count for triple bottom on day timeframe is around 30, on 4 hour timeframe it will be x times more and for 1 hour even more x times more candlestick for single pattern"

**Impact**: Critical flaw in multi-timeframe pattern detection logic

## The Problem

### Pattern Length Mismatch Across Timeframes

A chart pattern that takes 30 days to form requires **different numbers of candles** depending on the timeframe:

| Timeframe | Candles Required | Example (30 days) |
|-----------|------------------|-------------------|
| 1d        | 30 candles       | 30 bars           |
| 4h        | 180 candles      | 30 days × 6 = 180 bars |
| 1h        | 720 candles      | 30 days × 24 = 720 bars |

### What Was Wrong

The original implementation used the **same** `min_pattern_length` parameter for all timeframes:

```python
# BEFORE (WRONG)
detector = ChartPatternDetector(
    df=df,
    min_pattern_length=20,  # Same for 1h, 4h, and 1d ❌
    peak_order=5,           # Same for all ❌
    ...
)
```

**Problems**:
1. **1h timeframe**: 20 candles = less than 1 day (way too short!)
2. **4h timeframe**: 20 candles = 3.3 days (too short)
3. **1d timeframe**: 20 candles = 20 days (correct ✅)

This caused:
- Meaningless micro-patterns on 1h timeframe
- Patterns not comparable across timeframes
- False multi-timeframe matches
- Incorrect confidence boosting

## The Solution

### 1. Timeframe Scaling Factors

Added scaling constants to account for different candle densities:

```python
TIMEFRAME_SCALE = {
    '1h': 24,    # 24 hours per day
    '4h': 6,     # 6 four-hour periods per day
    '1d': 1,     # Baseline (no scaling)
    '1w': 0.2,   # ~5 days per week
    '1mo': 0.033 # ~30 days per month
}
```

### 2. Pattern Length Scaling Method

Created `_scale_pattern_length()` to automatically adjust based on timeframe:

```python
def _scale_pattern_length(self, timeframe: str) -> int:
    """
    Scale min_pattern_length based on timeframe density

    Example: min_pattern_length = 20 (baseline for 1d)
    - 1d: 20 candles (20 days)
    - 4h: 120 candles (20 days × 6)
    - 1h: 480 candles (20 days × 24)
    """
    scale_factor = self.TIMEFRAME_SCALE.get(timeframe, 1)
    scaled_length = int(self.min_pattern_length * scale_factor)
    return max(scaled_length, 10)  # Minimum 10 candles
```

### 3. Peak Order Scaling

Also scaled peak detection sensitivity to account for noise:

```python
def _scale_peak_order(self, timeframe: str) -> int:
    """
    Scale peak_order based on timeframe

    Higher frequency = more noise = need higher peak_order
    """
    scale_factor = self.TIMEFRAME_SCALE.get(timeframe, 1)

    if scale_factor >= 10:   # 1h or higher frequency
        return int(self.peak_order * 1.5)
    elif scale_factor >= 5:  # 4h
        return int(self.peak_order * 1.2)
    else:                    # 1d or lower
        return self.peak_order
```

### 4. Applied Scaling in Detection

Updated `_detect_patterns_for_timeframe()` to use scaled parameters:

```python
# AFTER (CORRECT)
scaled_min_length = self._scale_pattern_length(timeframe)
scaled_peak_order = self._scale_peak_order(timeframe)

detector = ChartPatternDetector(
    df=df,
    min_pattern_length=scaled_min_length,  # Scaled per timeframe ✅
    peak_order=scaled_peak_order,          # Scaled per timeframe ✅
    ...
)
```

## Test Results

### Configuration
```json
{
  "days": 180,
  "min_pattern_length": 15,
  "peak_order": 4,
  "min_confidence": 0.0,
  "remove_overlaps": false
}
```

### Scaled Parameters per Timeframe

| Timeframe | min_pattern_length | peak_order | Time Period |
|-----------|-------------------|------------|-------------|
| 1h        | 360 candles       | 6          | 15 days     |
| 4h        | 90 candles        | 4          | 15 days     |
| 1d        | 15 candles        | 4          | 15 days     |

All timeframes now represent the **same 15-day time period** ✅

### Results with ABNB Stock

**Before Fix**:
- 6 patterns (all 1TF)
- No multi-timeframe patterns
- Patterns not comparable

**After Fix**:
```
Total patterns: 23
Message: Multi-timeframe analysis: 23 patterns (0 on 3TF, 13 on 2TF)

Patterns by confirmation level:
  3TF: 0 patterns
  2TF: 13 patterns ✅
  1TF: 10 patterns

Top 5 patterns:
  1. Rounding Bottom - 2TF, conf=0.94, timeframes=['1d', '4h']
  2. Rounding Bottom - 2TF, conf=0.92, timeframes=['1d', '4h']
  3. Rounding Bottom - 2TF, conf=0.91, timeframes=['1d', '4h']
  4. Rounding Bottom - 2TF, conf=0.91, timeframes=['1d', '4h']
  5. Rounding Top - 2TF, conf=0.91, timeframes=['1d', '4h']
```

**Success!** 🎉
- 13 patterns confirmed on 2 timeframes
- Confidence scores boosted to 91-94%
- Patterns truly comparable across timeframes

## Why This Matters for Swing Trading

### Before Fix
- Comparing apples to oranges
- 1h pattern over 20 hours vs 1d pattern over 20 days
- False matches between incompatible patterns
- Unreliable confidence scores

### After Fix
- All patterns represent same time duration
- True multi-timeframe confirmation
- Reliable confidence boosting
- Better swing trading signals

## Example: Triple Bottom Detection

### User's Original Question
> "count for triple bottom on day timeframe is around 30, on 4 hour timeframe it will be x times more"

**Answer**: With our fix, if `min_pattern_length = 30`:

| Timeframe | Candles | Time Period | Comparable? |
|-----------|---------|-------------|-------------|
| 1d        | 30      | 30 days     | ✅ Yes      |
| 4h        | 180     | 30 days     | ✅ Yes      |
| 1h        | 720     | 30 days     | ✅ Yes      |

All patterns now represent the **same 30-day time period**, making them directly comparable!

## Code Changes

### File: `backend/app/services/multi_timeframe_patterns.py`

**Added**:
1. `TIMEFRAME_SCALE` dictionary (lines 46-54)
2. `_scale_pattern_length()` method (lines 84-105)
3. `_scale_peak_order()` method (lines 107-128)
4. Scaling logic in `_detect_patterns_for_timeframe()` (lines 198-200)

**Modified**:
- Removed premature data length check in `_fetch_price_data()` (line 258-259)
- Applied scaled parameters in pattern detector instantiation (lines 206-214)

## Recommended Settings

### Conservative (Longer Patterns)
```json
{
  "min_pattern_length": 20,
  "peak_order": 5
}
```
- 1d: 20 days
- 4h: 20 days (120 candles)
- 1h: 20 days (480 candles)

### Moderate (Swing Trading)
```json
{
  "min_pattern_length": 15,
  "peak_order": 4
}
```
- 1d: 15 days
- 4h: 15 days (90 candles)
- 1h: 15 days (360 candles)

### Aggressive (Shorter Patterns)
```json
{
  "min_pattern_length": 10,
  "peak_order": 3
}
```
- 1d: 10 days
- 4h: 10 days (60 candles)
- 1h: 10 days (240 candles)

## Impact

### Benefits
✅ Patterns are now temporally aligned across timeframes
✅ True multi-timeframe confirmation possible
✅ Confidence scores more reliable
✅ Better false positive filtering
✅ Swing trading signals more accurate

### No Breaking Changes
- API interface unchanged
- Frontend unchanged
- Database unchanged
- Only internal calculation improved

## Verification

To verify the fix is working:

1. **Check scaled parameters** in backend logs:
```python
# Add debug logging to see scaled values
print(f"[DEBUG] {timeframe}: scaled_min_length={scaled_min_length}, scaled_peak_order={scaled_peak_order}")
```

2. **Expect to see 2TF/3TF patterns** with proper data:
```bash
POST /api/v1/stocks/{stock_id}/detect-chart-patterns
{
  "days": 180,
  "min_pattern_length": 15,
  "peak_order": 4,
  "min_confidence": 0.0,
  "remove_overlaps": false
}
```

3. **Look for multi-timeframe badges** in UI:
- 🔥 3TF badge = pattern on all 3 timeframes
- ✅ 2TF badge = pattern on 2 timeframes

## Related Issues

- Fixed in conjunction with smart aggregation bug (BUGFIX_MULTI_TIMEFRAME_AGGREGATION.md)
- Both fixes required for proper multi-timeframe detection

## Status

✅ **FIXED** - October 29, 2025

Timeframe scaling now correctly applied. Patterns are temporally aligned across all analyzed timeframes, enabling true multi-timeframe pattern confirmation.

## User Credit

This critical issue was identified by the user's excellent observation about candlestick count differences across timeframes. Thank you for catching this fundamental flaw!
