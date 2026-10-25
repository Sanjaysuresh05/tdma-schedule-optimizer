# Benchmark summary

Radio range 500 m; uniform random deployments in squares and jittered rings; fixed seeds. `Excess` = slots used - optimum, where the optimum is the pipeline's final result, which is *proven* optimal (clique bound or exhaustive branch-and-bound) on every instance below. Cells show `-` where a method did not run (pipeline steps run only while a gap to the lower bound remains).

## Mean excess slots over the optimum (lower is better)

| Method | N16-700m | N16-1000m | N16-1300m | N16-1600m | N16-2000m | N50-2000m | N100-3000m | N200-4000m | Ring13-40 |
|---|---|---|---|---|---|---|---|---|---|
| nx largest_first | 0.00 | 0.02 | 0.00 | 0.00 | 0.00 | 0.34 | 0.50 | 0.75 | 0.32 |
| nx largest_first+interchange | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.06 | 0.07 | 0.20 | 0.00 |
| nx smallest_last | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.04 | 0.00 | 0.05 | 0.32 |
| nx DSATUR | 0.00 | 0.01 | 0.00 | 0.00 | 0.00 | 0.14 | 0.05 | 0.10 | 0.32 |
| nx independent_set | 0.00 | 0.32 | 0.44 | 0.42 | 0.20 | 2.06 | 2.10 | 2.75 | 0.07 |
| nx connected_bfs | 0.00 | 0.04 | 0.06 | 0.02 | 0.00 | 0.54 | 0.82 | 1.05 | 0.32 |
| nx random_sequential | 0.00 | 0.14 | 0.23 | 0.26 | 0.10 | 1.58 | 1.70 | 2.65 | 0.64 |
| ours DSATUR | 0.00 | 0.01 | 0.00 | 0.00 | 0.00 | 0.14 | 0.05 | 0.15 | 0.32 |
| ours RLF | 0.00 | 0.02 | 0.00 | 0.00 | 0.00 | 0.10 | 0.00 | 0.10 | 0.00 |
| ours Largest-first | 0.00 | 0.02 | 0.00 | 0.00 | 0.00 | 0.34 | 0.50 | 0.75 | 0.32 |
| ours Smallest-last | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.04 | 0.00 | 0.05 | 0.32 |
| ours Connected-BFS | 0.00 | 0.02 | 0.01 | 0.00 | 0.00 | 0.32 | 0.42 | 0.90 | 0.61 |
| ours Geometric sweep | 0.00 | 0.21 | 0.15 | 0.26 | 0.12 | 1.02 | 1.10 | 1.35 | 0.32 |
| ours Random greedy | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.20 | 0.45 | 0.85 | 0.21 |
| ours final | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| ours Iterated greedy | - | - | - | - | - | - | - | - | 0.00 |
| ours TabuCol | - | - | - | - | - | - | - | - | 0.00 |
| ours Exact B&B | - | - | - | - | - | - | - | - | 0.00 |

## Share of instances on which the method finds the optimum (%)

| Method | N16-700m | N16-1000m | N16-1300m | N16-1600m | N16-2000m | N50-2000m | N100-3000m | N200-4000m | Ring13-40 |
|---|---|---|---|---|---|---|---|---|---|
| nx largest_first | 100 | 98 | 100 | 100 | 100 | 68 | 60 | 45 | 68 |
| nx largest_first+interchange | 100 | 100 | 100 | 100 | 100 | 94 | 92 | 80 | 100 |
| nx smallest_last | 100 | 100 | 100 | 100 | 100 | 96 | 100 | 95 | 68 |
| nx DSATUR | 100 | 99 | 100 | 100 | 100 | 86 | 95 | 95 | 68 |
| nx independent_set | 100 | 71 | 62 | 63 | 83 | 6 | 10 | 0 | 93 |
| nx connected_bfs | 100 | 96 | 94 | 98 | 100 | 58 | 38 | 35 | 68 |
| nx random_sequential | 100 | 87 | 78 | 76 | 90 | 10 | 10 | 0 | 39 |
| ours DSATUR | 100 | 99 | 100 | 100 | 100 | 86 | 95 | 90 | 68 |
| ours RLF | 100 | 98 | 100 | 100 | 100 | 90 | 100 | 90 | 100 |
| ours Largest-first | 100 | 98 | 100 | 100 | 100 | 68 | 60 | 45 | 68 |
| ours Smallest-last | 100 | 100 | 100 | 100 | 100 | 96 | 100 | 95 | 68 |
| ours Connected-BFS | 100 | 98 | 99 | 100 | 100 | 70 | 60 | 40 | 54 |
| ours Geometric sweep | 100 | 80 | 85 | 77 | 88 | 26 | 32 | 20 | 68 |
| ours Random greedy | 100 | 100 | 100 | 100 | 100 | 82 | 58 | 35 | 79 |
| ours final | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 |
| ours Iterated greedy | - | - | - | - | - | - | - | - | 100 |
| ours TabuCol | - | - | - | - | - | - | - | - | 100 |
| ours Exact B&B | - | - | - | - | - | - | - | - | 100 |

## Pipeline result per set

| Set | Inst. | Mean LB | Mean slots (ours) | Mean best nx | Ours < best nx | Optimum > clique LB | Proven optimal | Verified | Mean time | Max time |
|---|---|---|---|---|---|---|---|---|---|---|
| N16-700m | 100 | 15.87 | 15.87 | 15.87 | 0 | 0 | 100% | 100% | 1.6 ms | 2.3 ms |
| N16-1000m | 100 | 12.52 | 12.52 | 12.52 | 0 | 0 | 100% | 100% | 1.5 ms | 1.7 ms |
| N16-1300m | 100 | 9.34 | 9.34 | 9.34 | 0 | 0 | 100% | 100% | 1.3 ms | 2.1 ms |
| N16-1600m | 100 | 7.28 | 7.28 | 7.28 | 0 | 0 | 100% | 100% | 1.1 ms | 1.4 ms |
| N16-2000m | 100 | 5.74 | 5.74 | 5.74 | 0 | 0 | 100% | 100% | 0.9 ms | 1.3 ms |
| N50-2000m | 50 | 15.26 | 15.26 | 15.26 | 0 | 0 | 100% | 100% | 6.1 ms | 7.1 ms |
| N100-3000m | 40 | 16.30 | 16.30 | 16.30 | 0 | 0 | 100% | 100% | 14.4 ms | 17.4 ms |
| N200-4000m | 20 | 18.75 | 18.75 | 18.80 | 1 | 0 | 100% | 100% | 39.7 ms | 42.1 ms |
| Ring13-40 | 28 | 3.00 | 3.68 | 3.68 | 0 | 19 | 100% | 100% | 17.0 ms | 39.1 ms |

## Slot-level simulation (saturated broadcast traffic)

| Set | Deliveries/slot: ours | round-robin | distance-1 colouring | Lost receptions, ours | Lost, distance-1 | Links starved, distance-1 |
|---|---|---|---|---|---|---|
| N16-700m | 11.28 | 11.19 | 9.12 | 0 | 49.3% | 49.3% |
| N16-1000m | 9.17 | 7.19 | 7.40 | 0 | 54.3% | 54.3% |
| N16-1300m | 8.48 | 4.94 | 6.57 | 0 | 52.5% | 52.5% |
| N16-1600m | 7.71 | 3.49 | 6.03 | 0 | 48.3% | 48.3% |
| N16-2000m | 6.66 | 2.39 | 5.51 | 0 | 42.1% | 42.1% |
| N50-2000m | 26.00 | 7.87 | 17.49 | 0 | 63.6% | 63.6% |
| N100-3000m | 47.32 | 7.65 | 30.02 | 0 | 66.0% | 66.0% |
| N200-4000m | 95.22 | 8.89 | 56.06 | 0 | 69.8% | 69.8% |
| Ring13-40 | 14.70 | 2.00 | 1.00 | 0 | 93.6% | 93.6% |

## Which step produced the final schedule

| Step | Instances |
|---|---|
| DSATUR | 617 |
| RLF | 15 |
| Smallest-last | 6 |
