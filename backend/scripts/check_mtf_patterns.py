import sys
import json

data = json.load(sys.stdin)
patterns = data.get('patterns', [])

print(f'Total patterns: {len(patterns)}')

mtf_2 = [p for p in patterns if p.get('confirmation_level', 1) == 2]
mtf_3 = [p for p in patterns if p.get('confirmation_level', 1) == 3]
single = [p for p in patterns if p.get('confirmation_level', 1) == 1]

print(f'  3TF: {len(mtf_3)} patterns')
print(f'  2TF: {len(mtf_2)} patterns')
print(f'  1TF: {len(single)} patterns')

if mtf_2:
    print(f'\nExample 2TF pattern:')
    p = mtf_2[0]
    print(f'  Name: {p.get("pattern_name")}')
    print(f'  Primary TF: {p.get("primary_timeframe")}')
    print(f'  Detected on: {p.get("detected_on_timeframes")}')
    print(f'  Confidence: {p.get("confidence_score"):.2f}')
