import sys
import json

data = json.load(sys.stdin)
patterns = data.get('patterns', [])

print(f'Total patterns: {len(patterns)}')

# Count by primary timeframe
primary_counts = {}
for p in patterns:
    primary = p.get('primary_timeframe', '1d')
    primary_counts[primary] = primary_counts.get(primary, 0) + 1

print('\nPrimary timeframe distribution:')
for tf in ['1h', '4h', '1d']:
    count = primary_counts.get(tf, 0)
    print(f'  {tf}: {count}')

# Count patterns detected on each timeframe
detected_counts = {'1h': 0, '4h': 0, '1d': 0}
for p in patterns:
    detected_on = p.get('detected_on_timeframes', ['1d'])
    for tf in detected_on:
        if tf in detected_counts:
            detected_counts[tf] += 1

print('\nDetected on timeframes:')
for tf in ['1h', '4h', '1d']:
    print(f'  {tf}: {detected_counts[tf]}')

# Confirmation levels
conf_counts = {1: 0, 2: 0, 3: 0}
for p in patterns:
    level = p.get('confirmation_level', 1)
    conf_counts[level] = conf_counts.get(level, 0) + 1

print('\nConfirmation levels:')
print(f'  1TF: {conf_counts[1]}')
print(f'  2TF: {conf_counts[2]}')
print(f'  3TF: {conf_counts[3]}')
