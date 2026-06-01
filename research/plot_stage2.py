"""
Stage 2 — 롤백 강도 분석 (research_roadmap.md 2단계)

롤백 강도(rollback intensity) = 고정 기간(= 16-ts = sync_period T) 동안
                                rollback 거리(delta_t)의 총합  Σ delta_t
  소스: rollback_events.dat  (col0 spiked_timestep, col2 delta_t=롤백거리)
       → spiked_timestep 으로 16-ts bin 집계(스파이크 수와 동일 시간기준)

스파이크 수(network activity) = clean.dat 양수 발화, network gid 0..3999, 16-ts bin
  (= Stage 1 #1, roadmap "전체 스파이크의 수")

산출:
  fig1  result_img/stage2_brunel_si_rollback_intensity_T16.png
        (A) 롤백 강도 vs time      (B) 롤백 강도 + 스파이크 수 겹침(twin-y)
  fig2  result_img/stage2_brunel_si_rollback_vs_spike_scatter_T16.png
        bin별 (스파이크 수 → 롤백 강도) 산점도 + 회귀선 + 상관계수
  stdout: Pearson r / Spearman ρ / lag 분석

usage:  python3 plot_stage2.py [run_folder] [bin_width] [analysis_end]
"""
import sys, os, ast, re
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUN_DIR = sys.argv[1] if len(sys.argv) > 1 else \
          "runspace/brunel_si/brunel_si_peri16_10pretrace_eng"
BIN_W   = int(sys.argv[2]) if len(sys.argv) > 2 else 16
WARMUP  = 50
ANALYSIS_END = int(sys.argv[3]) if len(sys.argv) > 3 else 1971
N_NET   = 4000
OUT_DIR = "research/result_img"


def spike_count_per_bin(path, max_ts):
    n = max_ts // BIN_W + 1
    c = np.zeros(n, np.int64)
    with open(path) as f:
        for line in f:
            if ":" not in line:
                continue
            g, r = line.split(":", 1)
            if int(g) >= N_NET:
                continue
            r = r.strip()
            arr = np.asarray(ast.literal_eval(r) if r else [], np.int64)
            arr = arr[arr >= 0]
            if arr.size:
                idx = arr // BIN_W
                idx = idx[idx < n]
                np.add.at(c, idx, 1)
    return c


def rollback_intensity_per_bin(ev, max_ts):
    """Σ delta_t per 16-ts bin, binned by spiked_timestep (col0)."""
    n = max_ts // BIN_W + 1
    c = np.zeros(n, np.float64)
    st, dt = ev[:, 0], ev[:, 2]
    idx = st // BIN_W
    ok = idx < n
    np.add.at(c, idx[ok], dt[ok])
    return c


def consumed_cycles_per_bin(log_path, max_ts):
    """log 의 누적 cyc 를 16-ts 격자로 보간·차분 → 각 16-ts 소모 cycle."""
    pat = re.compile(r"(\d+)\s*/\s*\d+\s*\.\.\.\s*cyc\s*(\d+)")
    ts, cy = [], []
    for line in open(log_path):
        mm = pat.search(line)
        if mm:
            ts.append(int(mm.group(1)))
            cy.append(int(mm.group(2)))
    ts = np.asarray(ts, float)
    cy = np.asarray(cy, float)
    o = np.argsort(ts)
    ts, cy = ts[o], cy[o]
    grid = np.arange(0, max_ts + BIN_W, BIN_W)
    cons = np.diff(np.interp(grid, ts, cy))
    n = max_ts // BIN_W + 1
    out = np.zeros(n, np.float64)
    k = min(n, len(cons))
    out[:k] = cons[:k]
    return out


def main():
    clean_p = os.path.join(RUN_DIR, "multicore_spike_out_clean.dat")
    rb_p    = os.path.join(RUN_DIR, "rollback_events.dat")
    ev = np.loadtxt(rb_p, dtype=np.int64, comments="#")
    if ev.ndim == 1:
        ev = ev.reshape(1, -1)

    max_ts = int(max(ev[:, 0].max(), ANALYSIS_END))
    spikes    = spike_count_per_bin(clean_p, max_ts)
    intensity = rollback_intensity_per_bin(ev, max_ts)
    cyc16     = consumed_cycles_per_bin(os.path.join(RUN_DIR, "log"), max_ts)
    m = min(len(spikes), len(intensity), len(cyc16))
    spikes, intensity, cyc16 = spikes[:m], intensity[:m], cyc16[:m]
    t = np.arange(m) * BIN_W

    win = (t >= WARMUP) & (t <= ANALYSIS_END)
    sp, it = spikes[win].astype(float), intensity[win]
    cy = cyc16[win].astype(float)

    # ---- 상관분석 ----
    pear_r, pear_p = stats.pearsonr(sp, it)
    spr_r,  spr_p  = stats.spearmanr(sp, it)
    # lag 교차상관 (it 가 sp 보다 lag bin 만큼 뒤따르는지; +lag = rollback 지연)
    sp_z = (sp - sp.mean()) / sp.std()
    it_z = (it - it.mean()) / it.std()
    lags = range(-6, 7)
    xcorr = {L: float(np.mean(np.roll(it_z, L) * sp_z)) for L in lags}
    best_lag = max(xcorr, key=lambda k: xcorr[k])
    slope, intcpt = np.polyfit(sp, it, 1)
    per_spike = it.sum() / sp.sum() if sp.sum() else 0.0
    rc_r, rc_p = stats.pearsonr(it, cy)        # rollback intensity ↔ consumed cycle (검증용)

    plt.rcParams.update({"font.size": 11, "axes.grid": True,
                         "grid.alpha": 0.3, "figure.dpi": 110})

    # ===== fig1 : (A) intensity vs t   (B) intensity + spikes overlaid =====
    fig, (axA, axB) = plt.subplots(2, 1, figsize=(13, 7.6), sharex=True)
    axA.fill_between(t, intensity, color="#6a1b9a", alpha=0.28, step="mid")
    axA.plot(t, intensity, color="#6a1b9a", lw=1.3,
             label=r"rollback intensity  $\Sigma\,\Delta t$ / 16 ts")
    axA.set_ylabel(r"$\Sigma\,\Delta t$  / 16 ts")
    axA.set_title("[A] Stage 2 - rollback intensity over time  "
                  "(brunel_si, T=16)", fontsize=12, loc="left")
    axA.text(0.012, 0.94,
             f"analysis[{WARMUP},{ANALYSIS_END}]  mean={it.mean():,.0f}  "
             f"CV={it.std()/it.mean():.2f}  total={it.sum():,.0f}",
             transform=axA.transAxes, fontsize=9, va="top",
             bbox=dict(boxstyle="round", fc="#f3e5f5", ec="#bbb"))
    axA.legend(loc="upper right", fontsize=9)

    axB.plot(t, intensity, color="#6a1b9a", lw=1.3,
             label=r"rollback intensity $\Sigma\Delta t$ (left)")
    axB.set_ylabel(r"$\Sigma\,\Delta t$ / 16 ts", color="#6a1b9a")
    axB.tick_params(axis="y", labelcolor="#6a1b9a")
    axB2 = axB.twinx()
    axB2.plot(t, cyc16, color="#00695c", lw=1.1, alpha=0.85,
              label="consumed HW cycles (right)")
    axB2.set_ylabel("cycles / 16 ts", color="#00695c")
    axB2.tick_params(axis="y", labelcolor="#00695c")
    axB2.grid(False)
    axB.set_title("[B] rollback intensity + consumed HW cycles overlaid  "
                  f"(Pearson r={rc_r:.2f})",
                  fontsize=12, loc="left")
    axB.set_xlabel("timestep  (dt=0.1ms,  1971 = 50 + 128x15)")
    h1, l1 = axB.get_legend_handles_labels()
    h2, l2 = axB2.get_legend_handles_labels()
    axB.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=9)

    for ax in (axA, axB):
        ax.axvspan(0, WARMUP, color="grey", alpha=0.18)
        ax.axvline(WARMUP, color="grey", ls=":", lw=1)
        ax.axvline(ANALYSIS_END, color="black", ls="--", lw=1)
    fig.tight_layout()
    os.makedirs(OUT_DIR, exist_ok=True)
    fp1 = os.path.join(OUT_DIR, f"stage2_brunel_si_rollback_intensity_T{BIN_W}.png")
    fig.savefig(fp1, bbox_inches="tight")

    # ===== fig2 : scatter spike count vs rollback intensity =====
    fig2, ax = plt.subplots(figsize=(7.4, 6))
    ax.scatter(sp, it, s=16, color="#6a1b9a", alpha=0.55, edgecolor="none")
    xs = np.linspace(sp.min(), sp.max(), 100)
    ax.plot(xs, slope * xs + intcpt, color="#b71c1c", lw=2,
            label=f"linear fit: y = {slope:.1f}x + {intcpt:.0f}")
    ax.set_xlabel("spike count / 16 ts  (network activity)")
    ax.set_ylabel(r"rollback intensity  $\Sigma\,\Delta t$ / 16 ts")
    ax.set_title("Stage 2 - rollback intensity vs spike count  (per 16-ts bin)",
                 fontsize=12)
    ax.text(0.03, 0.97,
            f"Pearson r = {pear_r:.3f}  (p={pear_p:.1e})\n"
            f"Spearman rho = {spr_r:.3f}  (p={spr_p:.1e})\n"
            f"n = {win.sum()} bins   slope = {slope:.2f} (Δt per extra spike)",
            transform=ax.transAxes, fontsize=10, va="top",
            bbox=dict(boxstyle="round", fc="#fffde7", ec="#bbb"))
    ax.legend(loc="lower right", fontsize=9)
    fig2.tight_layout()
    fp2 = os.path.join(OUT_DIR,
                       f"stage2_brunel_si_rollback_vs_spike_scatter_T{BIN_W}.png")
    fig2.savefig(fp2, bbox_inches="tight")

    print(f"[saved] {fp1}")
    print(f"[saved] {fp2}")
    print("=== Stage 2 correlation (analysis window, per 16-ts bin) ===")
    print(f"  bins n                 = {win.sum()}")
    print(f"  spike total            = {sp.sum():,.0f}")
    print(f"  rollback intensity tot = {it.sum():,.0f}  (Σdelta_t)")
    print(f"  intensity per spike    = {per_spike:.2f}  Δt/spike")
    print(f"  Pearson  r = {pear_r:.4f}  (p = {pear_p:.2e})")
    print(f"  Spearman rho = {spr_r:.4f}  (p = {spr_p:.2e})")
    print(f"  [validation] rollback intensity vs consumed cycle: "
          f"Pearson r = {rc_r:.4f} (p = {rc_p:.2e})")
    print(f"  regression slope = {slope:.3f}  intercept = {intcpt:.1f}")
    print(f"  best lag = {best_lag} bin ({best_lag*BIN_W} ts), "
          f"xcorr={xcorr[best_lag]:.3f}  (lag0={xcorr[0]:.3f})")


if __name__ == "__main__":
    main()
