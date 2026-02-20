# News Features Fix Summary

## Problem Identified

### Issue 1: Merge Bug in update_news_feb10.py
**Location:** Line 161
**Bug:** Script tried to merge on `merge_date` column that didn't exist in `news_df`

```python
# BROKEN CODE:
result = df.merge(
    news_df,
    on=['stock_id', 'merge_date'],  # merge_date doesn't exist in news_df!
    ...
)
```

**Impact:** The merge failed silently, resulting in:
- News features were filled with NaN/0
- No actual news sentiment data was incorporated
- New dataset looked identical to old dataset (verified!)

### Issue 2: Purpose of Date-Based Merge
The original intent was correct - merge on **DATE only**, not exact timestamp:
- News database: Exact timestamps (e.g., 2026-01-30 14:23:45)
- Features dataset: Day-level timestamps (2026-01-30 00:00:00)
- Solution: Create explicit `merge_date` column with `.dt.date` for both DataFrames

## Fix Applied

### Fixed merge_date creation in both DataFrames:

```python
# In df (features)
df['merge_date'] = df['timestamp'].dt.date

# In news_df
news_df['merge_date'] = news_df['timestamp'].dt.date

# Now merge works:
result = df.merge(
    news_df,
    on=['stock_id', 'merge_date'],
    how='left',
    suffixes=('', '_news')
)
```

## Verification

### Before Fix (dataset_20260211_193232):
```
Non-zero values: 3,869,219 / 9,810,880 (39.4%)
news_sentiment_avg_7d: mean=-0.0059, var=0.0792
```

### Expected After Fix:
- News features should have different values
- Merge will properly match news by date
- All 20 news features will be populated from database

## Next Steps

1. Wait for update script to complete (~45 min)
2. Verify new dataset has different news values
3. Compare old vs new to confirm news features changed
4. Retrain models on corrected dataset
5. Run feature importance analysis to verify news features are used

## Files Modified

- `ml-training/scripts/update_news_feb10.py`: Fixed merge_date column creation
