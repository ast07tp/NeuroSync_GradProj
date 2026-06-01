"""
Stage 3 STEP 2 — 고정 T vs workload 전체 소요 사이클

데이터 소스(권위): 각 고정 T 실행 로그
  runspace/brunel_si/brunel_si_peri<T>_10pretrace_eng/log
  의 마지막 "<ts> / <max> ... cyc <누적cyc>" 의 누적 cyc 값
  (= STAGE3_PLAN.md 메트릭 정의. SWEEP_total_cycles.txt 는 교차검증용으로만 사용)

x = 고정 T (1,2,4,8,16,32,64,128, log2 스케일)
y = workload 전체 소요 사이클 (= 로그 최종 누적 cyc)
최소점(= 전역 단일 최적 T = Oracle-B)을 강조 표시.

usage:  python3 plot_stage3_fixedT.py
"""
import os, re, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT   = "/home/heechan/26_GRADPROJ/NeuroSync_GradProj"
RUNDIR = os.path.join(ROOT, "runspace/brunel_si")
TS     = [1, 2, 4, 8, 16, 32, 64, 128]
PAT    = re.compile(r"(\d+)\s*/\s*\d+\s*\.\.\.\s*cyc\s*(\d+)")
OUT    = os.path.join(ROOT, "research/result_img/stage3_brunel_si_fixedT_total_cycles.png")


def final_cyc(T):
    """고정 T 로그의 마지막 누적 cyc, 최종 ts. 미완/부재 시 (None,None)."""
    log = os.path.join(RUNDIR, f"brunel_si_peri{T}_10pretrace_eng", "log")
    if not os.path.isfile(log):
        return None, None
    last_ts = last_cy = None
    done = False
    for line in open(log):
        if "Simulation Done" in line:
            done = True
        m = PAT.search(line)
        if m:
            last_ts, last_cy = int(m.group(1)), int(m.group(2))
    if not done or last_cy is None:
        return None, None
    return last_ts, last_cy


def main():
    rows = []
    for T in TS:
        ft, fc = final_cyc(T)
        rows.append((T, ft, fc))

    have = [(T, ft, fc) for (T, ft, fc) in rows if fc is not None]
    if not have:
        sys.exit("[error] 완료된 고정-T 로그가 하나도 없음 — 스윕 미완.")

    xs = np.array([r[0] for r in have], float)
    ys = np.array([r[2] for r in have], float)
    imin = int(np.argmin(ys))
    Tbest, ybest = int(xs[imin]), ys[imin]

    # ---- durable 표 출력 ----
    print("=== Stage 3 STEP2 — fixed-T total workload cycles ===")
    print(f"{'T':>5} {'final_ts':>9} {'total_cyc':>14}  {'vs T=16':>9}  {'vs best':>9}")
    cyc16 = next((fc for (T, ft, fc) in rows if T == 16 and fc), None)
    for (T, ft, fc) in rows:
        if fc is None:
            print(f"{T:>5} {'NA':>9} {'NA(미완/실패)':>14}")
            continue
        v16 = f"{cyc16/fc:6.3f}x" if cyc16 else "   --   "
        vb  = f"{ybest/fc:6.3f}x"
        star = "  <== best (Oracle-B)" if T == Tbest else ""
        print(f"{T:>5} {ft:>9} {fc:>14,}  {v16:>9}  {vb:>9}{star}")
    print(f"\n  best fixed T (Oracle-B) = {Tbest}  ({ybest:,.0f} cyc)")
    if cyc16:
        print(f"  T=16 baseline           = {cyc16:,.0f} cyc")
        print(f"  best fixed-T speedup vs T=16 = {cyc16/ybest:.4f}x")

    # ---- 그래프 ----
    plt.rcParams.update({"font.size": 11, "axes.grid": True,
                         "grid.alpha": 0.3, "figure.dpi": 110})
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    ax.plot(xs, ys, "-o", color="#1565c0", lw=1.8, ms=7, zorder=3,
            label="workload total HW cycles (fixed T)")
    ax.scatter([Tbest], [ybest], s=170, facecolor="none",
               edgecolor="#c62828", lw=2.4, zorder=4,
               label=f"best fixed T = {Tbest} (Oracle-B, global single best)")
    if cyc16:
        ax.axhline(cyc16, color="#6a1b9a", ls="--", lw=1.2, alpha=0.8,
                   label=f"T=16 baseline ({cyc16:,.0f})")
    for x, y in zip(xs, ys):
        ax.annotate(f"{y/1e6:.2f}M", (x, y), textcoords="offset points",
                    xytext=(0, 9), ha="center", fontsize=8.5,
                    color="#444")
    ax.set_xscale("log", base=2)
    ax.set_xticks(xs)
    ax.set_xticklabels([str(int(t)) for t in xs])
    ax.set_xlabel("fixed sync period T  (log2 scale)")
    ax.set_ylabel("workload total HW cycles  (final cumulative cyc)")
    ax.set_title("Stage 3 - workload total cycles vs fixed sync period T "
                 "(brunel_si v1)", fontsize=12.5)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    print(f"\n[saved] {OUT}")


if __name__ == "__main__":
    main()
