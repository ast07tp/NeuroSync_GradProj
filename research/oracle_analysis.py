"""
Stage 3 STEP 3 — Oracle 알고리즘 3종 적용·측정·비교
(설계·관점 설명은 STAGE3_ORACLE_DESIGN.md)

Oracle-A  per-block 최소-사이클 포락선 (자유 T 전환, 전환비용0 → 이론적 최대상한)
Oracle-B  전역 단일 최적 T            (스윕 곡선 최소점 = "고정 T 최소 사이클")
Oracle-C  롤백거리 예산 게이트        (관측가능 신호 ΣΔt 로 per-block T 결정 →
                                       배치 가능한 정책의 천장; Stage4 표적)

데이터:
  cost[T][b]      = peri<T> 로그 누적 cyc 를 블록경계서 보간·차분
  intensity[T][b] = peri<T> rollback_events.dat 의 ΣΔt (col0 spiked_timestep∈블록)
공통전제·블록정의: STAGE3_ORACLE_DESIGN.md §0. 1차 블록폭 B=128(+B=64 민감도).

usage:  python3 oracle_analysis.py
"""
import os, re, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT    = "/home/heechan/26_GRADPROJ/NeuroSync_GradProj"
RUNDIR  = os.path.join(ROOT, "runspace/brunel_si")
ALL_T   = [1, 2, 4, 8, 16, 32, 64, 128]
WARMUP  = 50
PAT     = re.compile(r"(\d+)\s*/\s*\d+\s*\.\.\.\s*cyc\s*(\d+)")
FIG     = os.path.join(ROOT, "research/result_img/stage3_brunel_si_oracle_comparison.png")
TXT     = os.path.join(RUNDIR, "stage3_oracle_results.txt")


def load_log(T):
    """(ts, cum_cyc) 단조정렬. 미완/부재→None."""
    log = os.path.join(RUNDIR, f"brunel_si_peri{T}_10pretrace_eng", "log")
    if not os.path.isfile(log):
        return None
    ts, cy, done = [], [], False
    for line in open(log):
        if "Simulation Done" in line:
            done = True
        m = PAT.search(line)
        if m:
            ts.append(int(m.group(1))); cy.append(int(m.group(2)))
    if not done or len(ts) < 5:
        return None
    ts = np.asarray(ts, float); cy = np.asarray(cy, float)
    o = np.argsort(ts, kind="stable")
    ts, cy = ts[o], cy[o]
    # 단조 비감소 강제(보간 안정)
    cy = np.maximum.accumulate(cy)
    return ts, cy


def load_intensity_raw(T):
    """rollback_events.dat → (spiked_timestep, delta_t). 부재→None."""
    p = os.path.join(RUNDIR, f"brunel_si_peri{T}_10pretrace_eng",
                      "rollback_events.dat")
    if not os.path.isfile(p):
        return None
    # 데이터행 존재 여부 선검사 (T=1: 헤더만 → 투기없음·롤백0, 빈파일 경고 회피)
    has_data = any(ln.strip() and not ln.lstrip().startswith("#")
                   for ln in open(p))
    if not has_data:
        return None
    ev = np.loadtxt(p, dtype=np.int64, comments="#")
    if ev.size == 0:
        return None
    if ev.ndim == 1:
        ev = ev.reshape(1, -1)
    return ev[:, 0].astype(float), ev[:, 2].astype(float)   # spiked_ts, delta_t


def blocks(final_ts, B):
    bn = list(range(WARMUP, int(final_ts) + 1, B))
    if bn[-1] < final_ts:
        bn.append(int(final_ts))
    return np.array(bn, float)                                # 경계 (n_blk+1,)


def build(B, logs, intens):
    """cost/intensity 행렬, fixed 총사이클(로그권위) 등 구성."""
    Ts = sorted(logs.keys())
    final_ts = min(logs[T][0][-1] for T in Ts)
    bn = blocks(final_ts, B)
    nb = len(bn) - 1
    cost = {T: np.diff(np.interp(bn, logs[T][0], logs[T][1])) for T in Ts}
    warm = {T: float(np.interp(WARMUP, logs[T][0], logs[T][1])) for T in Ts}
    total_fixed = {T: float(logs[T][1][-1]) for T in Ts}      # 메트릭=로그 최종 cyc
    recon = {T: warm[T] + cost[T].sum() for T in Ts}          # 재구성 sanity
    inten = {}
    for T in Ts:
        if T in intens:
            st, dt = intens[T]
            idx = np.searchsorted(bn, st, side="right") - 1
            v = np.zeros(nb)
            ok = (idx >= 0) & (idx < nb)
            np.add.at(v, idx[ok], dt[ok])
            inten[T] = v
    return dict(Ts=Ts, bn=bn, nb=nb, cost=cost, warm=warm,
                total_fixed=total_fixed, recon=recon, inten=inten,
                warm_min=min(warm.values()))


def oracle_A(d):
    Ts = d["Ts"]
    M = np.vstack([d["cost"][T] for T in Ts])                 # (|T|, nb)
    ai = M.argmin(axis=0)
    sched = np.array([Ts[i] for i in ai])
    total = d["warm_min"] + M.min(axis=0).sum()
    return total, sched


def oracle_B(d):
    T = min(d["Ts"], key=lambda t: d["total_fixed"][t])
    return d["total_fixed"][T], T


def oracle_C(d):
    """β 그리드=관측 intensity 값집합(실현비용은 β 의 계단함수→정확 최적)."""
    Ts = [T for T in d["Ts"] if T in d["inten"]]
    if len(Ts) < 2:
        return None
    Ts = sorted(Ts)
    nb = d["nb"]
    I = {T: d["inten"][T] for T in Ts}
    C = {T: d["cost"][T] for T in Ts}
    cand = np.unique(np.concatenate([I[T] for T in Ts]))
    cand = np.concatenate([cand, [cand.max() * 1.001 + 1.0]])
    best = None
    for beta in cand:
        chosen, c = np.empty(nb, int), 0.0
        for b in range(nb):
            pick = None
            for T in Ts:                                      # 오름차순 → 최대 T 채택
                if I[T][b] <= beta:
                    pick = T
            if pick is None:
                pick = Ts[0]                                  # 최소 T 폴백
            chosen[b] = pick
            c += C[pick][b]
        tot = d["warm_min"] + c
        if best is None or tot < best[0]:
            best = (tot, float(beta), chosen.copy())
    return best                                               # (total, beta*, sched)


def run(B, logs, intens):
    d = build(B, logs, intens)
    At, Asch = oracle_A(d)
    Bt, BT = oracle_B(d)
    Cres = oracle_C(d)
    return d, At, Asch, Bt, BT, Cres


def fmt(x): return f"{x:,.0f}"


def main():
    logs = {T: r for T in ALL_T if (r := load_log(T)) is not None}
    if 16 not in logs or len(logs) < 2:
        sys.exit(f"[error] 사용가능 로그 부족: {sorted(logs)}")
    intens = {T: r for T in logs if (r := load_intensity_raw(T)) is not None}

    d, At, Asch, Bt, BT, Cres = run(128, logs, intens)
    cyc16 = d["total_fixed"][16]
    lines = []
    def P(s=""):
        print(s); lines.append(s)

    P("=" * 72)
    P("Stage 3 STEP3 — Oracle 3종 (brunel_si v1, primary block B=128 ts)")
    P("=" * 72)
    P(f"available fixed-T : {sorted(logs)}")
    P(f"intensity 가용 T  : {sorted(intens)}   blocks={d['nb']}  "
      f"final_ts={int(d['bn'][-1])}")
    P("")
    P("-- fixed-T 총사이클 (메트릭=로그 최종 누적 cyc) & 재구성 sanity --")
    P(f"{'T':>4} {'total_cyc':>14} {'recon(Σblk+warm)':>18} {'err%':>7} "
      f"{'cyc/T16':>8}")
    for T in sorted(logs):
        tf, rc = d["total_fixed"][T], d["recon"][T]
        err = 100 * (rc - tf) / tf
        P(f"{T:>4} {fmt(tf):>14} {fmt(rc):>18} {err:>6.2f}% "
          f"{cyc16/tf:>7.3f}x")

    P("")
    P("-- Oracle 결과 --")
    spdA16, spdAB = cyc16 / At, Bt / At
    spdB16 = cyc16 / Bt
    P(f"Oracle-B  전역단일최적T = {BT:>3}        total = {fmt(Bt):>14} cyc"
      f"   speedup vs T16 = {spdB16:6.4f}x")
    P(f"Oracle-A  per-block 포락선(상한)        total = {fmt(At):>14} cyc"
      f"   speedup vs T16 = {spdA16:6.4f}x | vs Oracle-B = {spdAB:6.4f}x")
    if Cres is not None:
        Ct, beta, Csch = Cres
        spdC16, spdCB = cyc16 / Ct, Bt / Ct
        gap = Bt - At
        recov = 100 * (Bt - Ct) / gap if gap > 0 else float("nan")
        P(f"Oracle-C  롤백예산 β*={beta:,.0f}        total = {fmt(Ct):>14} cyc"
          f"   speedup vs T16 = {spdC16:6.4f}x | vs Oracle-B = {spdCB:6.4f}x")
        P("")
        P(f"  A–B gap (동적T 가 노릴 파이) = {fmt(Bt-At)} cyc "
          f"({100*(Bt-At)/Bt:.2f}% of Oracle-B)")
        P(f"  Oracle-C 가 회수한 gap 비율  = {recov:.1f}%  "
          f"(롤백신호 기반 동적T = Stage4 가망성 지표)")
    else:
        Ct = Csch = None
        P("Oracle-C  (intensity 데이터 부족 — 생략)")

    # ── 핵심질문 3개 자동 해석 ──
    P("")
    P("-- 핵심 질문 해석 --")
    P(f"  Q1 A–B gap 유의? : Oracle-A 가 최적고정T 대비 {spdAB:.4f}x "
      f"→ {'동적T 여지 있음' if spdAB > 1.02 else '여지 작음(ISN 평활과 부합)'}")
    if Cres is not None:
        P(f"  Q2 C 의 gap 회수 : {recov:.1f}% "
          f"→ {'롤백신호만으로 상한 근접' if recov >= 60 else ('부분 회수' if recov >= 20 else '회수 미미')}")
    P(f"  Q3 최적 고정 T   : {BT} (T=16 대비 {spdB16:.4f}x) "
      f"→ {'baseline 재설정 권고' if abs(spdB16-1) > 0.02 else 'T=16 가 사실상 최적'}")

    # ── B=64 민감도 ──
    d2, A2, _, B2, BT2, C2 = run(64, logs, intens)
    c2 = C2[0] if C2 else float("nan")
    P("")
    P("-- robustness: 결정입도 B=64 ts --")
    P(f"  Oracle-A(B64) speedup vs Oracle-B = {B2/A2:.4f}x  "
      f"(B128 = {Bt/At:.4f}x)  | 더 잘게 자를수록 상한 느슨")
    if C2:
        P(f"  Oracle-C(B64) total = {fmt(c2)} cyc  speedup vs T16 = "
          f"{cyc16/c2:.4f}x")

    # ── 그림 ──
    plt.rcParams.update({"font.size": 11, "axes.grid": True,
                         "grid.alpha": 0.3, "figure.dpi": 110})
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(15, 5.6))

    Ts_s = sorted(logs)
    xs = np.array(Ts_s, float)
    ys = np.array([d["total_fixed"][T] for T in Ts_s])
    axL.plot(xs, ys, "-o", color="#1565c0", lw=1.8, ms=7, zorder=3,
             label="fixed T (workload total cycles)")
    axL.scatter([BT], [Bt], s=170, facecolor="none", edgecolor="#c62828",
                lw=2.4, zorder=5, label=f"Oracle-B best fixed T={BT}")
    axL.axhline(At, color="#2e7d32", ls="--", lw=1.6,
                label=f"Oracle-A envelope ({At/1e6:.2f}M, "
                      f"{spdAB:.3f}x vs B)")
    if Ct is not None:
        axL.axhline(Ct, color="#ef6c00", ls="-.", lw=1.6,
                    label=f"Oracle-C rollback-budget ({Ct/1e6:.2f}M, "
                          f"{Bt/Ct:.3f}x vs B)")
    axL.axhline(cyc16, color="#6a1b9a", ls=":", lw=1.4,
                label=f"T=16 baseline ({cyc16/1e6:.2f}M)")
    axL.set_xscale("log", base=2)
    axL.set_xticks(xs); axL.set_xticklabels([str(int(t)) for t in xs])
    axL.set_xlabel("fixed sync period T  (log2)")
    axL.set_ylabel("workload total HW cycles")
    axL.set_title("[A] fixed-T total cycles + oracle bounds", fontsize=12,
                  loc="left")
    axL.legend(loc="best", fontsize=8.4)

    bx = d["bn"][:-1]
    axR.step(bx, Asch, where="post", color="#2e7d32", lw=1.8,
             label="Oracle-A per-block T*")
    if Csch is not None:
        axR.step(d2["bn"][:-1] if False else bx, Csch, where="post",
                 color="#ef6c00", lw=1.8, ls="-.",
                 label=f"Oracle-C per-block T (β*={Cres[1]:,.0f})")
    axR.axhline(BT, color="#c62828", ls="--", lw=1.4,
                label=f"Oracle-B single T={BT}")
    axR.axvspan(0, WARMUP, color="grey", alpha=0.15)
    axR.set_yscale("log", base=2)
    axR.set_yticks(xs); axR.set_yticklabels([str(int(t)) for t in xs])
    axR.set_xlabel("timestep  (block start;  1971 = 50 + 128x15)")
    axR.set_ylabel("oracle-chosen sync period T")
    axR.set_title("[B] dynamic T schedule (B=128 blocks)", fontsize=12,
                  loc="left")
    axR.legend(loc="best", fontsize=8.4)

    fig.suptitle("Stage 3 - Oracle upper-bound analysis (brunel_si v1)",
                 fontsize=13, y=1.02)
    fig.tight_layout()
    os.makedirs(os.path.dirname(FIG), exist_ok=True)
    fig.savefig(FIG, bbox_inches="tight")
    P("")
    P(f"[saved] {FIG}")

    with open(TXT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[saved] {TXT}")


if __name__ == "__main__":
    main()
