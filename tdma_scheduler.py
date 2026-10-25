#!/usr/bin/env python3
"""TDMA Schedule Planner & Optimizer - command-line entry point (Part 1).

Example:
    python tdma_scheduler.py '{"Node_01":[0.0,0.0],"Node_02":[300.0,0.0], ... ,"Node_16":[900.0,900.0]}'
    python tdma_scheduler.py --file inputs/grid_4x4.json --verbose --simulate 100
"""

import sys

from tdma_brain.cli import main

if __name__ == "__main__":
    sys.exit(main())
