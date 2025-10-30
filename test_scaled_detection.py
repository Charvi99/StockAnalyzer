import sys
import json

data = json.load(sys.stdin)

print(f"Total patterns: {data.get('total_patterns', 0)}")
print(f"Message: {data.get('message', 'N/A')}")

patterns = data.get('patterns', [])

print(f"\nPatterns by confirmation level:")
for level in [3, 2, 1]:
    count = sum(1 for p in patterns if p.get('confirmation_level', 1) == level)
    print(f"  {level}TF: {count} patterns")

print(f"\nFirst 5 patterns:")
for i, p in enumerate(patterns[:5]):
    print(f"  {i+1}. {p.get('pattern_name')} - {p.get('confirmation_level',1)}TF, conf={p.get('confidence_score',0):.2f}, timeframes={p.get('detected_on_timeframes', ['unknown'])}")

# Show scaling info if available
if patterns:
    print(f"\nTotal patterns detected: {len(patterns)}")
