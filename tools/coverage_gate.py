#!/usr/bin/env python
"""
Adaptive coverage gate: never allow total coverage to drop more than 1%
below the recorded baseline, with a hard floor of 40%.
When coverage improves, update the baseline in .coverage_target.
"""

import os
import sys
from pathlib import Path

from coverage import Coverage

target_file = Path(".coverage_target")
cov = Coverage()
cov.load()
total = cov.report(show_missing=False, file=open(os.devnull, "w"))

current = round(total, 1)
prev = float(target_file.read_text()) if target_file.exists() else 0.0
allowed = max(prev - 1.0, 40.0)

if current + 1e-9 < allowed:
    print(f"❌ Coverage {current:.1f}% < allowed minimum {allowed:.1f}% (previous {prev:.1f}%)")
    sys.exit(1)

if current > prev:
    target_file.write_text(f"{current:.1f}")
    print(f"✅ Coverage improved to {current:.1f}% (previous {prev:.1f}%) — baseline updated")
else:
    print(f"✅ Coverage {current:.1f}% (allowed ≥ {allowed:.1f}%) — OK")
