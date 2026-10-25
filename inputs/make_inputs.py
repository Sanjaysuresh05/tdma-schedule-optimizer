"""Regenerate the example 16-node topologies in this folder (deterministic)."""

import json
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent


def save(name: str, coords: dict) -> None:
    text = json.dumps({k: [round(x, 1), round(y, 1)] for k, (x, y) in coords.items()},
                      separators=(",", ":"))
    (HERE / f"{name}.json").write_text(text + "\n", encoding="utf-8")


def nodes(points):
    return {f"Node_{i + 1:02d}": p for i, p in enumerate(points)}


def main() -> None:
    # 1. The problem statement's sample: 4x4 grid, 300 m spacing, row-major.
    save("grid_4x4", nodes([(300.0 * (i % 4), 300.0 * (i // 4)) for i in range(16)]))

    # 2. Uniform random deployment in a 1500 m x 1500 m square.
    rng = random.Random(2024)
    save("random_16", nodes([(rng.uniform(0, 1500), rng.uniform(0, 1500)) for _ in range(16)]))

    # 3. Three clusters (e.g. three tactical teams) that are mutually far apart.
    rng = random.Random(7)
    centres = [(0, 0), (1400, 200), (600, 1300)]
    pts = []
    for i in range(16):
        cx, cy = centres[i % 3]
        pts.append((cx + rng.uniform(-200, 200), cy + rng.uniform(-200, 200)))
    save("clustered_16", nodes(pts))

    # 4. A convoy: a line with 400 m spacing (each node hears only its neighbours).
    save("line_16", nodes([(400.0 * i, 0.0) for i in range(16)]))

    # 5. A ring of radius 1000 m (circumference spacing ~ 390 m).
    save("ring_16", nodes([(1000 * math.cos(2 * math.pi * i / 16), 1000 * math.sin(2 * math.pi * i / 16))
                           for i in range(16)]))

    # 6. Dense: all 16 radios inside a 300 m square (every pair linked -> 16 slots needed).
    rng = random.Random(3)
    save("dense_16", nodes([(rng.uniform(0, 300), rng.uniform(0, 300)) for _ in range(16)]))


if __name__ == "__main__":
    main()
