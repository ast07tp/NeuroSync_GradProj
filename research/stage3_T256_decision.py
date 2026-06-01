"""
Task1 — 고정 T=256 포함 fixed-T 총사이클 그래프 + Oracle-A only 비교 + 글로벌 동적-T 판정.

판정 규칙(사용자 지정): per-block 최적 T∈{1..256} 를 골라도(Oracle-A, B=128)
  Oracle-A 가 최적 고정 T 대비 ≤ ~5% → 글로벌 동적-T 알고리즘 깔끔히 포기.

oracle_analysis.py 의 load_log/build/oracle_A/oracle_B 재사용(중복 구현 없음).
산출:
  result_img/stage3_fixedT_total_cycles_with_T256.png
  result_img/stage3_oracleA_only_comparison_T256.png
  stdout + runspace/brunel_si/stage3_T256_decision.txt
usage: python3 stage3_T256_decision.py
"""
import os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import oracle_analysis as oa

ROOT = "/home/heechan/26_GRADPROJ/NeuroSync_GradProj"
TS   = [1, 2, 4, 8, 16, 32, 64, 128, 256]
THR  = 1.05   # 5% 판정 임계


def read_partial(T):
    """완료 여부 무관 로그 스캔 → (last_ts, last_cyc, done). 없으면 None."""
    import re
    p = f"{ROOT}/runspace/brunel_si/brunel_si_peri{T}_10pretrace_eng/log"
    if not os.path.isfile(p):
        return None
    pat = re.compile(r"(\d+)\s*/\s*\d+\s*\.\.\.\s*cyc\s*(\d+)")
    ts = cy = None
    done = False
    for ln in open(p):
        if "Simulation Done" in ln:
            done = True
        m = pat.search(ln)
        if m:
            ts, cy = int(m.group(1)), int(m.group(2))
    return (ts, cy, done) if cy is not None else None


def main():
    logs = {T: r for T in TS if (r := oa.load_log(T)) is not None}
    intens = {}   # Oracle-A only → intensity 불필요
    miss = [T for T in TS if T not in logs]
    p256 = read_partial(256)   # T=256: 병리적(미완) — 별도 마커로 표기
    out = []
    def P(s=""):
        print(s); out.append(s)

    P("=" * 64)
    P("Task1 — fixed T(1..256) + Oracle-A only + 글로벌 동적-T 판정")
    P("=" * 64)
    if p256 is not None and not p256[2]:
        P(f"[T=256 병리적] ts {p256[0]}/1971 에서 cyc {p256[1]:,} 도달 후 "
          f"rollback-explosion(100%CPU 63min, >31min/block 무진척)으로 비종료 "
          f"→ kill. total ≫ 모든 T, Oracle-A 후보서 제외(완료 T 만으로 포락선).")
    elif miss:
        P(f"[note] 아직 미완 T: {miss} (완료분으로 진행)")
    d = oa.build(128, logs, intens)            # B=128 (Stage3 1차 입도)
    At, Asch = oa.oracle_A(d)
    Bt, BT = oa.oracle_B(d)
    cyc16 = d["total_fixed"].get(16)

    P(f"\n{'T':>5} {'total_cyc':>14} {'vs T=16':>9} {'vs best':>9}")
    for T in sorted(logs):
        tf = d["total_fixed"][T]
        v16 = f"{cyc16/tf:6.3f}x" if cyc16 else "  --  "
        star = "  <== best (Oracle-B)" if T == BT else ""
        P(f"{T:>5} {tf:>14,.0f} {v16:>9} {Bt/tf:>8.3f}x{star}")

    spdAB = Bt / At
    gain_pct = (spdAB - 1) * 100
    P(f"\nOracle-B 최적 고정 T = {BT}  ({Bt:,.0f} cyc)")
    P(f"Oracle-A per-block 포락선 (T∈{sorted(logs)}, B=128) = {At:,.0f} cyc")
    P(f"Oracle-A vs 최적 고정 T  = {spdAB:.4f}x  (= {gain_pct:.2f}% 이득)")
    verdict = ("글로벌 동적-T 깔끔히 포기 (≤5% — per-block 최적 T 라도 미미)"
               if spdAB <= THR else
               "동적-T 여지 ≥5% (재검토)")
    P(f"\n>>> 판정: {verdict}")
    P(">>> 대체 본선 = 코어별 speculative-advance + 예측 stall "
      "(측정 oracle 천장 T64=10.4%, T128=18.1%)")

    # ── 공통 곡선 + T=256 병리 마커 ──
    plt.rcParams.update({"font.size": 11, "axes.grid": True,
                         "grid.alpha": 0.3, "figure.dpi": 110})
    xs = np.array(sorted(logs), float)
    ys = np.array([d["total_fixed"][int(t)] for t in xs])
    xticks = list(xs) + ([256.0] if p256 is not None else [])

    def draw_curve(ax, line_label):
        ax.plot(xs, ys, "-o", color="#1565c0", lw=1.8, ms=7, zorder=3,
                label=line_label)
        for x, y in zip(xs, ys):
            ax.annotate(f"{y/1e6:.2f}M", (x, y), textcoords="offset points",
                        xytext=(0, 9), ha="center", fontsize=8, color="#555")
        if p256 is not None:
            pt_ts, pt_cy, pdone = p256
            ax.scatter([256], [pt_cy], marker="X", s=150, color="#c62828",
                       zorder=6,
                       label=("T=256 PATHOLOGICAL "
                              f"(>={pt_cy/1e6:.2f}M @ts{pt_ts}/1971, "
                              "rollback-explosion, non-terminating)"))
            ax.annotate(f">={pt_cy/1e6:.2f}M\n(ts{pt_ts}, diverged)",
                        (256, pt_cy), textcoords="offset points",
                        xytext=(-4, 10), ha="center", fontsize=8,
                        color="#c62828", fontweight="bold")
            ax.annotate("", xy=(256, pt_cy * 1.18), xytext=(256, pt_cy),
                        arrowprops=dict(arrowstyle="-|>", color="#c62828",
                                        lw=2))
        ax.set_xscale("log", base=2)
        ax.set_xticks(xticks)
        ax.set_xticklabels([str(int(t)) for t in xticks])
        ax.set_xlabel("fixed sync period T  (log2)")
        ax.set_ylabel("workload total HW cycles")

    # ── fig1: fixed-T total (incl 256 pathological) ──
    fig, ax = plt.subplots(figsize=(9.6, 5.5))
    draw_curve(ax, "workload total HW cycles (fixed T)")
    ax.scatter([BT], [Bt], s=170, facecolor="none", edgecolor="#2e7d32",
               lw=2.4, zorder=5, label=f"best fixed T={BT} (Oracle-B)")
    if cyc16:
        ax.axhline(cyc16, color="#6a1b9a", ls="--", lw=1.1, alpha=.8,
                   label=f"T=16 baseline ({cyc16/1e6:.2f}M)")
    ax.set_title("Task1 - fixed-T total cycles incl. T=256 (brunel_si v1)",
                 fontsize=12.5)
    ax.legend(loc="lower left", fontsize=8.2)
    fig.tight_layout()
    f1 = f"{ROOT}/research/result_img/stage3_fixedT_total_cycles_with_T256.png"
    fig.savefig(f1, bbox_inches="tight"); P(f"\n[saved] {f1}")

    # ── fig2: Oracle-A only comparison ──
    fig2, ax = plt.subplots(figsize=(9.6, 5.5))
    draw_curve(ax, "fixed T (total cycles)")
    ax.scatter([BT], [Bt], s=170, facecolor="none", edgecolor="#2e7d32",
               lw=2.4, zorder=5, label=f"Oracle-B best fixed T={BT}")
    ax.axhline(At, color="#ef6c00", ls="--", lw=1.8,
               label=f"Oracle-A envelope ({At/1e6:.3f}M, "
                     f"{spdAB:.3f}x = {gain_pct:.1f}% vs best fixed T)")
    ax.set_title("Task1 - Oracle-A (per-block envelope T in {1..128}, B=128) "
                 "vs fixed T\n"
                 f"verdict: only {gain_pct:.1f}% over best fixed T (<=5%) "
                 "-> drop global dynamic-T"
                 if spdAB <= THR else
                 "Task1 - Oracle-A vs fixed T", fontsize=11)
    ax.legend(loc="lower left", fontsize=8.2)
    fig2.tight_layout()
    f2 = f"{ROOT}/research/result_img/stage3_oracleA_only_comparison_T256.png"
    fig2.savefig(f2, bbox_inches="tight"); P(f"[saved] {f2}")

    with open(f"{ROOT}/runspace/brunel_si/stage3_T256_decision.txt", "w") as fp:
        fp.write("\n".join(out) + "\n")
    P(f"[saved] runspace/brunel_si/stage3_T256_decision.txt")


if __name__ == "__main__":
    main()
