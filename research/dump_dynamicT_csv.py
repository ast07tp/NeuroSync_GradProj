"""
Dump per-block Oracle-A schedule for Dynamic T Balancing poster figure.
  result_img/dynamicT_per_block.csv  — for each 128-ts block, cost at every T
                                       + best T (Oracle-A choice) + best cycles
"""
import os, sys, re
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from oracle_analysis import load_log, build, oracle_A, ALL_T

OUT = os.path.join(ROOT, "research/result_img", "dynamicT_per_block.csv")

logs = {T: r for T in ALL_T if (r := load_log(T)) is not None}
d = build(128, logs, {})
At, Asch = oracle_A(d)
Ts = sorted(d["Ts"])
nb = d["nb"]
bn = d["bn"]

with open(OUT, "w") as f:
    f.write("block_id,start_ts,end_ts,best_T,best_cycles," +
            ",".join(f"cyc_T{T}" for T in Ts) + "\n")
    for b in range(nb):
        row = [b, int(bn[b]), int(bn[b + 1]),
               int(Asch[b]), int(min(d["cost"][T][b] for T in Ts))]
        row += [int(d["cost"][T][b]) for T in Ts]
        f.write(",".join(str(x) for x in row) + "\n")

print(f"[saved] {OUT}")
print(f"blocks={nb}  Ts={Ts}")
print(f"per-block best T schedule: {list(map(int, Asch))}")
print(f"Oracle-A total = {int(At):,} cyc  (vs fixed T=64 = "
      f"{int(d['total_fixed'][64]):,}; speedup +"
      f"{(d['total_fixed'][64]/At - 1)*100:.2f}%)")
