"""
Poster figure — Idea #2 (Proxy Prediction is Unusable)
2-panel side-by-side:
  [LEFT]  Temporal proxy:  network activity (spike count / 16-ts)
                           vs rollback load (Sigma delta_t / 16-ts)
                           -> R^2 ~ 0.09 (T=16 run, the canonical Stage-2 figure)
  [RIGHT] Spatial proxy :  NoC hop distance (src-core -> dst-core)
                           vs mean rollback depth (Delta t)
                           -> r ~ 0 (T=64 and T=128 overlaid; mean Delta t
                              clamped at T/2 regardless of distance)

Data: rollback_events.dat (T=16 for left; T=64, T=128 for right)
      + clean.dat (left)  + mapping_4100_64.npz (right)
No re-simulation. Outputs result_img/poster_proxy_unusable.png.
"""
import os, ast, sys
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, "research/result_img", "poster_proxy_unusable.png")

# ---------- topology (matches stage4_predict.py) ----------
GRID = 8
def core_xy(c): return c % GRID, c // GRID
def hop_dist(a, b):
    ax, ay = core_xy(a); bx, by = core_xy(b)
    return abs(ax - bx) + abs(ay - by)

def load_gid2core():
    nl = np.load(f"{ROOT}/mapping/brunel_si/mapping_4100_64.npz",
                 allow_pickle=True)["node_list"]
    n = sum(len(c) for c in nl)
    g2c = np.full(n, -1, dtype=np.int16)
    for core, gids in enumerate(nl):
        for g in gids: g2c[g] = core
    return g2c

# ---------- LEFT panel data (T=16, Stage-2 canonical) ----------
def left_panel_data():
    BIN_W = 16
    WARMUP, END, N_NET = 50, 1971, 4000
    run = f"{ROOT}/runspace/brunel_si/brunel_si_peri16_10pretrace_eng"
    clean_p = f"{run}/multicore_spike_out_clean.dat"
    rb_p    = f"{run}/rollback_events.dat"
    ev = np.loadtxt(rb_p, dtype=np.int64, comments="#")
    if ev.ndim == 1: ev = ev.reshape(1, -1)
    max_ts = int(max(ev[:, 0].max(), END))
    nb = max_ts // BIN_W + 1

    # spike count (network activity)
    spk = np.zeros(nb, np.int64)
    with open(clean_p) as f:
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

    # rollback intensity Sigma delta_t per bin
    intst = np.zeros(nb, np.float64)
    idx = ev[:, 0] // BIN_W
    ok  = idx < nb
    np.add.at(intst, idx[ok], ev[ok, 2])

    t = np.arange(nb) * BIN_W
    win = (t >= WARMUP) & (t <= END)
    return spk[win].astype(float), intst[win]

# ---------- RIGHT panel data (T=64, T=128 hop vs Delta t) ----------
def right_panel_data(T):
    SETUP, END = 50, 1971
    p = f"{ROOT}/runspace/brunel_si/brunel_si_peri{T}_10pretrace_eng/rollback_events.dat"
    ev = np.loadtxt(p, dtype=np.int64, comments="#")
    sp, _af, dt, src, _anti, rgid = (ev[:, i] for i in range(6))
    g2c = load_gid2core()
    sc, dc = g2c[src], g2c[rgid]
    m = (sp >= SETUP) & (sp <= END)
    sc, dc, dt = sc[m], dc[m], dt[m]
    hops = np.array([hop_dist(int(s), int(d)) for s, d in zip(sc, dc)])

    hmax = int(hops.max())
    rows = []
    for h in range(hmax + 1):
        sel = (hops == h)
        if sel.any():
            rows.append((h, int(sel.sum()),
                         float(dt[sel].mean()), float(dt[sel].std())))
    rows = np.array(rows, dtype=float)   # h, n, mean, std
    corr = float(np.corrcoef(hops, dt)[0, 1])
    return rows, corr

# ---------- plot ----------
def main():
    sp, it = left_panel_data()
    pear_r, _ = stats.pearsonr(sp, it)
    spr_r,  _ = stats.spearmanr(sp, it)
    slope, intcpt = np.polyfit(sp, it, 1)
    R2 = pear_r ** 2

    rows64,  c64  = right_panel_data(64)
    rows128, c128 = right_panel_data(128)

    plt.rcParams.update({"font.size": 12, "axes.grid": True,
                         "grid.alpha": 0.3, "figure.dpi": 130})
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(14.5, 5.6))

    # =================== LEFT — Temporal proxy ===================
    axL.scatter(sp, it, s=22, color="#6a1b9a", alpha=0.55, edgecolor="none",
                label=f"per-16ts bin  (n={len(sp)})")
    xs = np.linspace(sp.min(), sp.max(), 100)
    axL.plot(xs, slope * xs + intcpt, color="#b71c1c", lw=2.2,
             label=f"linear fit  (slope={slope:.1f}, intercept={intcpt:.0f})")

    axL.set_xlabel("network activity   spike count  per 16-ts bin")
    axL.set_ylabel(r"rollback load   $\Sigma\,\Delta t$  per 16-ts bin")
    axL.set_title("[ Temporal ]   spikes  $\\to$  rollback",
                  fontsize=14, loc="left", pad=10)
    axL.text(0.035, 0.965,
             f"$R^2 = {R2:.2f}$\n"
             f"Pearson  r = {pear_r:+.2f}\n"
             f"Spearman ρ = {spr_r:+.2f}\n"
             "large activity-independent floor",
             transform=axL.transAxes, fontsize=12.5, va="top", ha="left",
             bbox=dict(boxstyle="round,pad=0.5", fc="#fff8e1",
                       ec="#c0392b", lw=1.4))
    axL.text(0.965, 0.045, "✗  unusable as a predictor",
             transform=axL.transAxes, fontsize=13, va="bottom", ha="right",
             color="#b71c1c", fontweight="bold",
             bbox=dict(boxstyle="round,pad=0.35", fc="#fdecea",
                       ec="#c0392b", lw=1.2))
    axL.legend(loc="lower right", fontsize=10,
               bbox_to_anchor=(1.0, 0.16))

    # =================== RIGHT — Spatial proxy ===================
    # T=64
    h64, n64, m64, s64 = rows64.T
    se64 = s64 / np.sqrt(n64)
    axR.errorbar(h64, m64, yerr=se64, fmt="o-", color="#1565c0",
                 ms=7, lw=2, capsize=3,
                 label=f"T = 64    (n_events = {int(n64.sum()):,})")
    axR.axhline(64 / 2, color="#1565c0", ls=":", lw=1.3, alpha=0.7,
                label="T/2 = 32  (geometry-independent ceiling)")
    # T=128
    h128, n128, m128, s128 = rows128.T
    se128 = s128 / np.sqrt(n128)
    axR.errorbar(h128, m128, yerr=se128, fmt="s-", color="#2e7d32",
                 ms=7, lw=2, capsize=3,
                 label=f"T = 128  (n_events = {int(n128.sum()):,})")
    axR.axhline(128 / 2, color="#2e7d32", ls=":", lw=1.3, alpha=0.7,
                label="T/2 = 64")

    axR.set_xlabel("NoC hop distance   (src-core → dst-core, Manhattan)")
    axR.set_ylabel(r"mean rollback depth   $\overline{\Delta t}$")
    axR.set_title("[ Spatial ]   distance  $\\to$  rollback depth",
                  fontsize=14, loc="left", pad=10)
    axR.text(0.035, 0.965,
             f"$R^2 \\approx 0.00$\n"
             f"corr(hop, Δt)  =  {c64:+.3f}   (T=64)\n"
             f"corr(hop, Δt)  =  {c128:+.3f}  (T=128)\n"
             "Δt is set by sync window, not distance",
             transform=axR.transAxes, fontsize=12.5, va="top", ha="left",
             bbox=dict(boxstyle="round,pad=0.5", fc="#fff8e1",
                       ec="#c0392b", lw=1.4))
    axR.text(0.965, 0.045, "✗  unusable as a predictor",
             transform=axR.transAxes, fontsize=13, va="bottom", ha="right",
             color="#b71c1c", fontweight="bold",
             bbox=dict(boxstyle="round,pad=0.35", fc="#fdecea",
                       ec="#c0392b", lw=1.2))
    axR.legend(loc="center right", fontsize=10, framealpha=0.92)
    axR.set_ylim(0, 75)
    axR.set_xticks(np.arange(0, max(int(h64.max()), int(h128.max())) + 1, 2))

    fig.suptitle(
        "Idea #2 — Proxy prediction is unusable :  "
        "the obvious surrogates carry no predictive signal",
        fontsize=15, y=1.02, x=0.005, ha="left", fontweight="bold")
    fig.tight_layout()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    print(f"[saved] {OUT}")
    print(f"[left]  R^2={R2:.4f}  r={pear_r:.4f}  rho={spr_r:.4f}  "
          f"slope={slope:.3f}  intcpt={intcpt:.1f}  n_bins={len(sp)}")
    print(f"[right] T=64  corr(hop,Δt)={c64:+.4f}  "
          f"mean_Δt[hop=0]={m64[0]:.1f}  mean_Δt[hop={int(h64[-1])}]={m64[-1]:.1f}")
    print(f"[right] T=128 corr(hop,Δt)={c128:+.4f}  "
          f"mean_Δt[hop=0]={m128[0]:.1f}  mean_Δt[hop={int(h128[-1])}]={m128[-1]:.1f}")

if __name__ == "__main__":
    main()
