import sys
import json

data = json.load(sys.stdin)
patterns = data.get('patterns', [])

print(f'Total patterns in database: {len(patterns)}')

if patterns:
    print('\nFirst pattern example:')
    p = patterns[0]
    print(f"  ID: {p.get('id')}")
    print(f"  Name: {p.get('pattern_name')}")
    print(f"  Primary Timeframe: {p.get('primary_timeframe', 'N/A')}")
    print(f"  Detected On: {p.get('detected_on_timeframes', 'N/A')}")
    print(f"  Start: {p.get('start_date')}")
    print(f"  End: {p.get('end_date')}")
    print(f"  Confirmation Level: {p.get('confirmation_level', 'N/A')}")

print('\nPatterns by primary timeframe:')
timeframes = {}
for p in patterns:
    tf = p.get('primary_timeframe', 'unknown')
    timeframes[tf] = timeframes.get(tf, 0) + 1

for tf, count in sorted(timeframes.items()):
    print(f"  {tf}: {count} patterns")
