"""
각 16-timestep(= sync_period T) 동안 소모된 시뮬 HW cycle 시계열

소스: runspace/<...>/log  의  "<ts> / <max> ... cyc <누적cyc>, elapsed <s>" 라인
  - cyc 는 *누적* 값 → 16-ts 경계마다 np.interp 로 값을 구해 차분하면
    각 16-ts 구간의 *소모* cycle 이 된다 (warmup=per-ts, speculation=per-T
    샘플링이 섞여 있어도 보간으로 동일 격자 처리).

usage:  python3 plot_cycle_per16ts.py [run_folder] [bin_width] [analysis_end]
"""
import sys, os, re
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUN_DIR = sys.argv[1] if len(sys.argv) > 1 else \
          "runspace/brunel_si/brunel_si_peri16_10pretrace_eng"
BIN_W   = int(sys.argv[2]) if len(sys.argv) > 2 else 16
WARMUP  = 50
ANALYSIS_END = int(sys.argv[3]) if len(sys.argv) > 3 else 1971
OUT_DIR = "research/result_img"
PAT = re.compile(r"(\d+)\s*/\s*\d+\s*\.\.\.\s*cyc\s*(\d+)")


def main():
    log = os.path.join(RUN_DIR, "log")
    ts, cyc = [], []
    for line in open(log):
        m = PAT.search(line)
        if m:
            ts.append(int(m.group(1)))
            cyc.append(int(m.group(2)))
    if not ts:
        sys.exit(f"[error] 파싱 실패: {log}")
    ts = np.asarray(ts, float)
    cyc = np.asarray(cyc, float)
    # 단조 증가 정리 (혹시 모를 중복/역행 방지)
    order = np.argsort(ts)
    ts, cyc = ts[order], cyc[order]

    max_ts = int(ts[-1])
    grid = np.arange(0, max_ts + BIN_W, BIN_W)          # 0,16,32,...
    cyc_at = np.interp(grid, ts, cyc)                    # 경계별 누적 cyc
    consumed = np.diff(cyc_at)                           # 각 16-ts 구간 소모 cyc
    x = grid[:-1]                                        # 각 bin 시작 ts

    mask = (x >= WARMUP) & (x <= ANALYSIS_END)
    v = consumed[mask]
    mean_v, cv = v.mean(), (v.std() / v.mean() if v.mean() else 0)

    plt.rcParams.update({"font.size": 11, "axes.grid": True,
                         "grid.alpha": 0.3, "figure.dpi": 110})
    fig, ax = plt.subplots(figsize=(13, 4.4))
    ax.fill_between(x, consumed, color="#00695c", alpha=0.25, step="mid")
    ax.plot(x, consumed, color="#00695c", lw=1.3,
            label=f"consumed cycles / {BIN_W} ts")
    ax.axvspan(0, WARMUP, color="grey", alpha=0.18)
    ax.axvline(WARMUP, color="grey", ls=":", lw=1)
    ax.axvline(ANALYSIS_END, color="black", ls="--", lw=1,
               label=f"analysis end ts={ANALYSIS_END}")
    ax.set_xlabel("timestep  (dt=0.1ms,  1971 = 50 + 128x15)")
    ax.set_ylabel(f"HW cycles / {BIN_W} ts")
    ax.set_title(f"brunel_si - consumed simulated HW cycles per {BIN_W}-timestep "
                 f"window (T={BIN_W})", fontsize=12.5)
    ax.text(0.012, 0.94,
            f"analysis[{WARMUP},{ANALYSIS_END}]  mean={mean_v:,.0f} cyc/{BIN_W}ts  "
            f"CV={cv:.2f}", transform=ax.transAxes, fontsize=9, va="top",
            bbox=dict(boxstyle="round", fc="#e0f2f1", ec="#bbb"))
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    os.makedirs(OUT_DIR, exist_ok=True)
    fp = os.path.join(OUT_DIR, f"brunel_si_cycle_per{BIN_W}ts_T{BIN_W}.png")
    fig.savefig(fp, bbox_inches="tight")
    print(f"[saved] {fp}")
    print(f"  analysis[{WARMUP},{ANALYSIS_END}]  mean={mean_v:,.1f} cyc/{BIN_W}ts  "
          f"CV={cv:.3f}  total={v.sum():,.0f} cyc")


if __name__ == "__main__":
    main()
