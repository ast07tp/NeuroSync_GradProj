"""
Dump minimal CSVs for poster Idea #2 (Proxy is unusable).
  result_img/proxy_temporal.csv  — spike count vs rollback load (per 16-ts bin)
  result_img/proxy_spatial.csv   — NoC hop vs mean rollback depth (T=64, T=128)
"""
import os, ast
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_T = os.path.join(ROOT, "research/result_img", "proxy_temporal.csv")
OUT_S = os.path.join(ROOT, "research/result_img", "proxy_spatial.csv")

GRID = 8
def core_xy(c): return c % GRID, c // GRID
def hop_dist(a, b):
    ax, ay = core_xy(a); bx, by = core_xy(b)
    return abs(ax - bx) + abs(ay - by)

def load_gid2core():
    nl = np.load(f"{ROOT}/mapping/brunel_si/mapping_4100_64.npz",
                 allow_pickle=True)["node_list"]
    g2c = np.full(sum(len(c) for c in nl), -1, dtype=np.int16)
    for core, gids in enumerate(nl):
        for g in gids: g2c[g] = core
    return g2c

# ---------- Temporal (T=16) ----------
BIN_W, WARMUP, END, N_NET = 16, 50, 1971, 4000
run = f"{ROOT}/runspace/brunel_si/brunel_si_peri16_10pretrace_eng"
ev = np.loadtxt(f"{run}/rollback_events.dat", dtype=np.int64, comments="#")
nb = max(int(ev[:, 0].max()), END) // BIN_W + 1
spk = np.zeros(nb, np.int64)
with open(f"{run}/multicore_spike_out_clean.dat") as f:
    for line in f:
        if ":" not in line: continue
        g, r = line.split(":", 1)
        if int(g) >= N_NET: continue
        r = r.strip()
        arr = np.asarray(ast.literal_eval(r) if r else [], np.int64)
        arr = arr[arr >= 0]
        if arr.size:
            idx = arr // BIN_W
            idx = idx[idx < nb]
            np.add.at(spk, idx, 1)
intst = np.zeros(nb, np.float64)
idx = ev[:, 0] // BIN_W; ok = idx < nb
np.add.at(intst, idx[ok], ev[ok, 2])
t = np.arange(nb) * BIN_W
win = (t >= WARMUP) & (t <= END)
sp, it = spk[win].astype(int), intst[win].astype(int)

with open(OUT_T, "w") as f:
    f.write("spike_count,rollback_load_sum_delta_t\n")
    for a, b in zip(sp, it):
        f.write(f"{a},{b}\n")
print(f"[saved] {OUT_T}  rows={len(sp)}  (R^2=0.09, r=+0.29)")

# ---------- Spatial (T=64, T=128) ----------
def hop_table(T):
    p = f"{ROOT}/runspace/brunel_si/brunel_si_peri{T}_10pretrace_eng/rollback_events.dat"
    a = np.loadtxt(p, dtype=np.int64, comments="#")
    sp_ts, _af, dt, src, _anti, rgid = (a[:, i] for i in range(6))
    g2c = load_gid2core()
    sc, dc = g2c[src], g2c[rgid]
    m = (sp_ts >= 50) & (sp_ts <= 1971)
    sc, dc, dt = sc[m], dc[m], dt[m]
    hops = np.array([hop_dist(int(s), int(d)) for s, d in zip(sc, dc)])
    rows = []
    for h in range(int(hops.max()) + 1):
        sel = hops == h
        if sel.any():
            rows.append((h, int(sel.sum()), float(dt[sel].mean())))
    return rows

r64, r128 = hop_table(64), hop_table(128)
hops_all = sorted(set([r[0] for r in r64] + [r[0] for r in r128]))
d64  = {h: (n, m) for h, n, m in r64}
d128 = {h: (n, m) for h, n, m in r128}
with open(OUT_S, "w") as f:
    f.write("hop,n_events_T64,mean_delta_t_T64,n_events_T128,mean_delta_t_T128\n")
    for h in hops_all:
        n64, m64 = d64.get(h, (0, None))
        n128, m128 = d128.get(h, (0, None))
        s64  = "" if m64  is None else f"{m64:.2f}"
        s128 = "" if m128 is None else f"{m128:.2f}"
        f.write(f"{h},{n64},{s64},{n128},{s128}\n")
print(f"[saved] {OUT_S}  hops=0..{hops_all[-1]}  "
      "(corr(hop,Δt) = -0.007 @T=64, -0.002 @T=128)")
