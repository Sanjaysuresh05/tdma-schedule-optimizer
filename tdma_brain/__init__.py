"""TDMA Schedule Planner & Optimizer ("the Brain").

Turns static radio coordinates into a collision-free TDMA schedule by
distance-2 colouring the 500 m unit-disk connectivity graph, minimising the
number of slots (frame length) while maximising spatial reuse.
"""

__version__ = "1.0.0"

DEFAULT_RANGE_M = 500.0
