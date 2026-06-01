"""
Stage 1 — 스파이크 시계열 분석 (research_roadmap.md 1단계)  [정정판]

★ 소스 파일이 측정하는 "단위(granularity)"를 정확히 구분한다 ★

[A] 스파이크 *생성*(generation) 수준 — "각 뉴런이 몇 번 발화했나" (per source neuron)
    - multicore_spike_out_clean.dat : 롤백 보정이 끝난 *최종 올바른* 발화 (양수)
    - multicore_spike_out_raw.dat   : 위 + 투기로 잘못 생성됐다 취소된 발화(+t,-t쌍)
        => raw - clean = 2 x (취소된 발화수). 본 run 에선 취소 247개(0.016x)뿐.
        => raw.dat 은 "in-flight" 가 아니다. 'belated'(수신측 지연 도착)는
           생성 기록엔 존재할 수 없는 개념 → raw.dat 으로 #2 를 만들 수 없음.

[B] 시냅스 *전달/롤백 이벤트*(delivery/event) 수준 — "늦게 도착해 롤백을 유발한 전달"
    - rollback_events.dat : belated 시냅스 전달마다 1행 (시뮬레이터 계측 신규)
        한 발화가 fan-out(out-degree~200, 64코어) → 발화 1개당 belated 다수.

따라서 현재 *출력 파일만으로* 정확히 그릴 수 있는 것:
    #1 FINAL  (생성수준)   = clean.dat               ← roadmap "생성된 스파이크 수"
    #3 BELATED(전달수준)   = rollback_events.dat
#2 "모든 in-flight"(전달수준, #3 의 상위집합)는 현재 출력에 없음 → 별도 정의/복원 필요
(아래 그래프는 #1·#3 만, 단위를 명시해서 그린다. #2 는 사용자 정의 확정 후 추가.)

usage:  python3 plot_activity.py [run_folder] [bin_width] [analysis_end]
"""
import sys, os, ast
import numpy as np
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


def parse_spike_dat(path):
    out = {}
    with open(path) as f:
        for line in f:
            if ":" not in line:
                continue
            g, r = line.split(":", 1)
            r = r.strip()
            out[int(g)] = np.asarray(ast.literal_eval(r) if r else [], dtype=np.int64)
    return out


def bin_series(values, max_ts):
    n = max_ts // BIN_W + 1
    c = np.zeros(n, dtype=np.int64)
    if len(values):
        idx = np.abs(values) // BIN_W
        idx = idx[idx < n]
        np.add.at(c, idx, 1)
    return c


def stats(arr, t):
    """CV = std/mean of per-bin counts within the analysis window [WARMUP, ANALYSIS_END].
       (population std, numpy ddof=0).  단위 없는 상대 변동성 지표."""
    v = arr[(t >= WARMUP) & (t <= ANALYSIS_END)]
    m = v.mean()
    sd = v.std()                       # ddof=0 (population)
    return v.sum(), m, sd, (sd / m if m else 0.0)


def main():
    clean = parse_spike_dat(os.path.join(RUN_DIR, "multicore_spike_out_clean.dat"))
    raw   = parse_spike_dat(os.path.join(RUN_DIR, "multicore_spike_out_raw.dat"))
    rb_p  = os.path.join(RUN_DIR, "rollback_events.dat")
    rb = (np.loadtxt(rb_p, dtype=np.int64, comments="#")
          if os.path.isfile(rb_p) else np.empty((0, 6), np.int64))
    if rb.ndim == 1:
        rb = rb.reshape(1, -1)

    max_ts = max((int(np.abs(a).max()) for a in clean.values() if a.size), default=0)

    final_gen = np.zeros(max_ts // BIN_W + 1, np.int64)   # #1 생성수준 (clean +)
    raw_gen   = np.zeros_like(final_gen)                   # 참고: raw 전체(생성수준)
    for g in range(N_NET):
        a = clean.get(g)
        if a is not None and a.size:
            final_gen += bin_series(a[a >= 0], max_ts)
        b = raw.get(g)
        if b is not None and b.size:
            raw_gen += bin_series(b, max_ts)               # |t|: +생성 & -anti 모두

    belated_dlv = (bin_series(rb[:, 0], max_ts) if rb.size      # #3 전달/이벤트수준
                   else np.zeros_like(final_gen))

    t = np.arange(len(final_gen)) * BIN_W
    f_sum, f_m, f_sd, f_cv = stats(final_gen, t)
    r_sum, r_m, r_sd, r_cv = stats(raw_gen, t)
    b_sum, b_m, b_sd, b_cv = stats(belated_dlv, t)

    plt.rcParams.update({"font.size": 11, "axes.grid": True,
                         "grid.alpha": 0.3, "figure.dpi": 110})
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 7.6), sharex=True)

    # Panel 1 : #1 generation-level network activity
    ax1.fill_between(t, final_gen, color="#1f3b73", alpha=0.22, step="mid")
    ax1.plot(t, final_gen, color="#1f3b73", lw=1.4,
             label=f"#1 FINAL correct spikes  (clean.dat, sum={f_sum:,})")
    ax1.plot(t, raw_gen, color="#b71c1c", lw=0.8, ls="--", alpha=0.8,
             label=f"raw.dat all entries  (sum={r_sum:,}, +247 anti only)")
    ax1.set_ylabel(f"spikes / {BIN_W} ts")
    ax1.set_title("[A] GENERATION level  (per source neuron: 몇 번 발화했나)  "
                   "— roadmap '생성된 스파이크 수'", fontsize=11.5, loc="left")
    ax1.text(0.012, 0.95, f"analysis[{WARMUP},{ANALYSIS_END}]  "
             f"#1 mean={f_m:.1f}  CV={f_cv:.2f}   (raw≈#1: 투기낭비 단 {r_sum/f_sum:.3f}x)",
             transform=ax1.transAxes, fontsize=9, va="top",
             bbox=dict(boxstyle="round", fc="#fffde7", ec="#bbb"))
    ax1.legend(loc="upper right", fontsize=9)

    # Panel 2 : #3 delivery/event-level belated rollback triggers
    ax2.fill_between(t, belated_dlv, color="#e65100", alpha=0.30, step="mid")
    ax2.plot(t, belated_dlv, color="#e65100", lw=1.3,
             label=f"#3 BELATED rollback-trigger deliveries  "
                   f"(rollback_events.dat, sum={b_sum:,})")
    ax2.set_ylabel(f"events / {BIN_W} ts")
    ax2.set_title("[B] DELIVERY / ROLLBACK-EVENT level  (belated 시냅스 전달 = "
                   "발화 1개가 fan-out~200 → 다수 belated)", fontsize=11.5, loc="left")
    ax2.text(0.012, 0.95, f"analysis[{WARMUP},{ANALYSIS_END}]  "
             f"#3 mean={b_m:.1f}  CV={b_cv:.2f}   "
             f"(#3/#1 = {b_sum/max(f_sum,1):.1f}x : 단위가 다름!)",
             transform=ax2.transAxes, fontsize=9, va="top",
             bbox=dict(boxstyle="round", fc="#fff3e0", ec="#bbb"))
    ax2.set_xlabel("timestep  (dt=0.1ms,  1971 = 50 + 128x15)")
    ax2.legend(loc="upper right", fontsize=9)

    for ax in (ax1, ax2):
        ax.axvspan(0, WARMUP, color="grey", alpha=0.18)
        ax.axvline(WARMUP, color="grey", ls=":", lw=1)
        ax.axvline(ANALYSIS_END, color="black", ls="--", lw=1)

    fig.suptitle("Stage 1 (corrected) - brunel_si  |  #2 'all in-flight' is "
                 "NOT in raw.dat (generation vs delivery granularity)", fontsize=12.5)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    os.makedirs(OUT_DIR, exist_ok=True)
    fp = os.path.join(OUT_DIR, f"stage1_brunel_si_spike_timeseries_T{BIN_W}.png")
    fig.savefig(fp, bbox_inches="tight")
    print(f"[saved] {fp}")
    print(f"  #1 FINAL  (gen)      sum={f_sum:,}  mean={f_m:.2f}  CV={f_cv:.3f}")
    print(f"  raw.dat   (gen)      sum={r_sum:,}  (= #1 + 2x247 anti; in-flight 아님)")
    print(f"  #3 BELATED(delivery) sum={b_sum:,}  mean={b_m:.2f}  CV={b_cv:.3f}")
    print(f"  단위 불일치: #1/raw=생성수준, #3=전달수준 → 직접 비교 불가, #2 별도 정의 필요")


if __name__ == "__main__":
    main()
