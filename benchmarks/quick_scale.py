"""Quick scaling check: pipeline quality and run time from N=16 to N=500 (Stage 2 report table)."""
import random, sys, time
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from tdma_brain.topology import Topology
from tdma_brain.optimizer import optimize
GRID = {f"Node_{i+1:02d}": (300.0*(i%4), 300.0*(i//4)) for i in range(16)}
s = optimize(Topology(GRID, 500.0))
print("GRID", s.num_slots, s.lower_bound, s.proven_optimal, s.found_by, f"{s.seconds*1000:.1f} ms")
for r in s.runs: print("   ", r.name, r.slots, f"{r.seconds*1000:.2f} ms", r.note)
rng = random.Random(0)
for n, side in [(16, 1000), (16, 1500), (50, 2000), (100, 3000), (200, 4000), (500, 6000)]:
    coords = {f"N{i}": (rng.uniform(0, side), rng.uniform(0, side)) for i in range(n)}
    t0 = time.perf_counter(); topo = Topology(coords, 500.0); tt = time.perf_counter() - t0
    s = optimize(topo, time_limit=5.0)
    print(n, side, "K", s.num_slots, "LB", s.lower_bound, "opt", s.proven_optimal, "by", s.found_by, f"topo {tt:.2f}s opt {s.seconds:.2f}s", [(r.name, r.slots) for r in s.runs])
