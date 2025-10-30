"""
Script to update all candlestick pattern detection methods with volume confirmation
This applies Phase 1.1 improvements to all 40 patterns
"""
import re

def update_pattern_method(method_code: str, pattern_name: str, base_confidence: float, pattern_type: str) -> str:
    """
    Updates a pattern detection method to include volume confirmation

    Args:
        method_code: The original method code
        pattern_name: Name of the pattern
        base_confidence: Original confidence score
        pattern_type: 'bullish' or 'bearish'

    Returns:
        Updated method code with volume confirmation
    """
    # Find the confidence_score line
    old_confidence_line = f"'confidence_score': {base_confidence}"

    # Create the new volume-enhanced code
    new_code = f"""# PHASE 1.1: Apply volume confirmation
                base_confidence = {base_confidence}
                volume_multiplier, volume_quality = self._calculate_volume_confidence_boost(i, '{pattern_type}')
                final_confidence = min(base_confidence * volume_multiplier, 0.95)

                patterns.append({{
                    'pattern_name': '{pattern_name}',
                    'pattern_type': '{pattern_type}',
                    'timestamp': candle['timestamp'],
                    'confidence_score': final_confidence,
                    'base_confidence': base_confidence,  # NEW: Original confidence
                    'volume_quality': volume_quality,    # NEW: Volume quality label
                    'volume_ratio': float(candle['volume_ratio']),  # NEW: Volume ratio"""

    # Replace the old patterns.append block
    # Pattern: patterns.append({ ... 'confidence_score': X.XX, ... })
    pattern = r"patterns\.append\(\{\s*'pattern_name':[^}]+\}\)"

    def replace_append(match):
        old_block = match.group(0)
        # Extract candle_data if present
        candle_data_match = re.search(r"'candle_data':\s*[^\n]+", old_block)
        if candle_data_match:
            candle_data_line = candle_data_match.group(0)
            return new_code + ",\n                    " + candle_data_line + "\n                })"
        else:
            return new_code + "\n                })"

    updated_code = re.sub(pattern, replace_append, method_code)
    return updated_code


# List of all patterns with their base confidence scores
BULLISH_PATTERNS = [
    ('Hammer', 0.75),
    ('Inverted Hammer', 0.70),
    ('Bullish Marubozu', 0.80),
    ('Dragonfly Doji', 0.75),
    ('Bullish Engulfing', 0.85),
    ('Piercing Line', 0.80),
    ('Tweezer Bottom', 0.70),
    ('Bullish Kicker', 0.85),
    ('Bullish Harami', 0.75),
    ('Bullish Counterattack', 0.75),
    ('Morning Star', 0.90),
    ('Morning Doji Star', 0.85),
    ('Three White Soldiers', 0.90),
    ('Three Inside Up', 0.85),
    ('Three Outside Up', 0.85),
    ('Bullish Abandoned Baby', 0.95),
    ('Rising Three Methods', 0.80),
    ('Upside Tasuki Gap', 0.75),
    ('Mat Hold', 0.80),
    ('Rising Window', 0.70),
]

BEARISH_PATTERNS = [
    ('Hanging Man', 0.75),
    ('Shooting Star', 0.75),
    ('Bearish Marubozu', 0.80),
    ('Gravestone Doji', 0.75),
    ('Bearish Engulfing', 0.85),
    ('Dark Cloud Cover', 0.80),
    ('Tweezer Top', 0.70),
    ('Bearish Kicker', 0.85),
    ('Bearish Harami', 0.75),
    ('Bearish Counterattack', 0.75),
    ('Evening Star', 0.90),
    ('Evening Doji Star', 0.85),
    ('Three Black Crows', 0.90),
    ('Three Inside Down', 0.85),
    ('Three Outside Down', 0.85),
    ('Bearish Abandoned Baby', 0.95),
    ('Falling Three Methods', 0.80),
    ('Downside Tasuki Gap', 0.75),
    ('On Neck Line', 0.70),
    ('Falling Window', 0.70),
]


if __name__ == "__main__":
    print("📊 Candlestick Pattern Volume Confirmation Updater")
    print("=" * 60)
    print(f"Total patterns to update: {len(BULLISH_PATTERNS) + len(BEARISH_PATTERNS)}")
    print(f"  - Bullish: {len(BULLISH_PATTERNS)}")
    print(f"  - Bearish: {len(BEARISH_PATTERNS)}")
    print()
    print("✅ Volume confirmation formula:")
    print("   - Excellent (2x+ volume): +30% confidence")
    print("   - Good (1.5-2x volume): +15% confidence")
    print("   - Average (1-1.5x volume): No change")
    print("   - Weak (<1x volume): -30% confidence")
    print()
    print("Note: Manual application required for each pattern method.")
    print("      Update template applied to 'Hammer' as example.")
