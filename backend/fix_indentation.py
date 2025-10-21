#!/usr/bin/env python3
"""
Fix indentation of chart pattern methods
"""

# Read the extended methods file
with open('app/services/chart_patterns_extended.py', 'r') as f:
    extended_content = f.read()

# Read the main chart_patterns file
with open('app/services/chart_patterns.py', 'r') as f:
    main_content = f.read()

# Skip the header comments in extended file and get just the method definitions
lines = extended_content.split('\n')
method_lines = []
in_methods = False

for line in lines:
    if line.startswith('def detect_'):
        in_methods = True
    if in_methods:
        # Add 4 spaces of indentation for class methods
        method_lines.append('    ' + line)

# Append to main file
with open('app/services/chart_patterns.py', 'w') as f:
    f.write(main_content)
    if not main_content.endswith('\n'):
        f.write('\n')
    f.write('\n'.join(method_lines))
    f.write('\n')

print(f"Added {len(method_lines)} lines with proper indentation")
