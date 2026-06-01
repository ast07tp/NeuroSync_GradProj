"""
Stage4-energy — redo_cyc 분해 분석 (rollback action vs recovery/recompute).
specgate 재시뮬(계측본)의 redo_cyc.dat 을 읽어:
  1) 비침습 검증: 새 redo 총합 == 백업(.bak_predecomp) 총합  (계측이 시뮬 불변)
  2) restore+recompute == redo  (분해 정합)
  3) 보고: restore/recompute 비율, recompute 가 total cyc 의 몇 %인가
  4) 포스터용 stacked-bar 그림(정상연산 vs 복원 vs 재계산).
재시뮬 0 (이미 계측 재시뮬 산출된 redo_cyc.dat 만 읽음).
"""
import os, re
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNDIR = f"{ROOT}/runspace/brunel_si_specgate"
OUT_FIG = f"{ROOT}/research/result_img/stage4_redo_decomp.png"
OUT_TXT = f"{ROOT}/runspace/brunel_si/stage4_redo_decomp.txt"


STATES = ["neu_comp", "neu_comp_end", "sync_wait", "commit", "sync_done", "rollback"]


def parse(T):
    p = f"{RUNDIR}/brunel_si_peri{T}_10pretrace_eng/redo_cyc.dat"
    tot = decomp = None
    bak_redo = None
    for ln in open(p):
        if ln.startswith("# TOTAL"):
            kv = dict(re.findall(r"(\w+)=(-?\d+\.?\d*)", ln))
            tot = dict(cyc=int(kv["cyc"]), redo=int(kv["redo"]),
                       redo_frac=float(kv["redo_frac"]))
        elif ln.startswith("# DECOMP"):
            kv = dict(re.findall(r"(\w+)=(-?\d+\.?\d*)", ln))
            decomp = dict(restore=int(kv["restore"]), recompute=int(kv["recompute"]),
                          sum=int(kv["sum"]))
    bp = f"{p}.bak_predecomp"
    if os.path.isfile(bp):
        for ln in open(bp):
            if ln.startswith("# TOTAL"):
                bak_redo = int(dict(re.findall(r"(\w+)=(-?\d+\.?\d*)", ln))["redo"])
    # FSM 상태별
    fp = f"{RUNDIR}/brunel_si_peri{T}_10pretrace_eng/fsm_cyc.dat"
    fsm = None
    if os.path.isfile(fp):
        for ln in open(fp):
            if ln.startswith("# TOTAL"):
                kv = dict(re.findall(r"(\w+)=(\d+)", ln))
                fsm = {s: int(kv[s]) for s in STATES}
    return tot, decomp, bak_redo, fsm


def main():
    rows = []
    out = []
    def P(s=""):
        print(s); out.append(s)

    P("=" * 70)
    P("Stage4-energy — redo_cyc 분해 (rollback 부기 vs recovery/recompute)")
    P("=" * 70)
    for T in (64, 128):
        tot, dec, bak, fsm = parse(T)
        if tot is None or dec is None:
            P(f"[T={T}] redo_cyc.dat 미완성 — 재시뮬 진행중?"); continue
        noninv = (bak is None) or (bak == tot["redo"])
        match = (dec["sum"] == tot["redo"])
        rest_f = dec["restore"] / tot["redo"]
        rec_f = dec["recompute"] / tot["redo"]
        rec_of_total = dec["recompute"] / tot["cyc"]
        rest_of_total = dec["restore"] / tot["cyc"]
        P(f"\n[T={T}]  total cyc = {tot['cyc']:,}  (64-core sum)")
        P(f"  ── redo_cyc 분해 (rollback_state) ──")
        P(f"  redo_cyc (roll+recov)= {tot['redo']:,}  ({tot['redo_frac']*100:.2f}% of total)")
        P(f"  ├ restore/bookkeeping= {dec['restore']:,}  "
          f"({rest_f*100:.2f}% of redo, {rest_of_total*100:.2f}% of total)")
        P(f"  └ recompute/recovery = {dec['recompute']:,}  "
          f"({rec_f*100:.2f}% of redo, {rec_of_total*100:.2f}% of total)")
        P(f"  [check] restore+recompute == redo : {match}")
        P(f"  [check] redo == 백업(비침습)        : {noninv}"
          + (f"  (bak={bak:,})" if bak is not None else "  (백업없음)"))
        if fsm:
            P(f"  ── FSM 상태별 분해 (전체 cyc 어디로 가나) ──")
            for s in STATES:
                P(f"  {s:>13} = {fsm[s]:>14,}  ({fsm[s]/tot['cyc']*100:5.2f}%)")
            P(f"  [check] fsm[rollback] == redo_cyc : {fsm['rollback'] == tot['redo']}")
            real = fsm["neu_comp"] + fsm["sync_done"]
            sync_ovh = fsm["neu_comp_end"] + fsm["sync_wait"] + fsm["commit"]
            P(f"  → 실연산(neu_comp+sync_done시냅스) ≈ {real/tot['cyc']*100:.1f}%  | "
              f"sync오버헤드(end+wait+commit) ≈ {sync_ovh/tot['cyc']*100:.1f}%  | "
              f"rollback ≈ {tot['redo_frac']*100:.1f}%")
        rows.append((T, tot["cyc"], dec["restore"], dec["recompute"], tot["redo"], fsm))

    if rows:
        P("\n[해석] redo_cyc 는 'rollback 행위'가 아니라 거의 전부 recovery/recompute.")
        P("       즉 보고했던 10.4/18.1% 천장은 이미 rollback+recovery 합산값.")
        _figure(rows)
        P(f"\n[saved] {OUT_FIG}")

    os.makedirs(os.path.dirname(OUT_TXT), exist_ok=True)
    open(OUT_TXT, "w").write("\n".join(out) + "\n")
    P(f"[saved] {OUT_TXT}")


def _figure(rows):
    plt.rcParams.update({"font.size": 11, "figure.dpi": 130})
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13.5, 5.6))
    x = np.arange(len(rows))
    labels = [f"T={r[0]}" for r in rows]

    # ── LEFT: 전체 cyc 의 FSM 6-상태 분해 (rollback 의 자리매김) ──
    seg = {  # (label, color) — bottom→top
        "neu_comp": ("neuron compute", "#7e57c2"),
        "sync_done": ("synapse delivery / drain (sync_done)", "#90caf9"),
        "neu_comp_end": ("sync request (neu_comp_end)", "#b0bec5"),
        "sync_wait": ("barrier idle (sync_wait)", "#eeeeee"),
        "commit": ("commit", "#ffe082"),
        "rollback": ("rollback + recovery", "#c0392b"),
    }
    order = ["neu_comp", "sync_done", "neu_comp_end", "sync_wait", "commit", "rollback"]
    bottoms = np.zeros(len(rows))
    for s in order:
        vals = np.array([r[5][s] for r in rows], float) / 1e6
        axL.bar(x, vals, 0.55, bottom=bottoms, label=seg[s][0], color=seg[s][1],
                edgecolor="white", linewidth=0.6)
        bottoms += vals
    for i, r in enumerate(rows):
        axL.text(i, r[1]/1e6*1.01, f"rollback\n{r[4]/r[1]*100:.1f}%",
                 ha="center", va="bottom", fontsize=10, fontweight="bold",
                 color="#c0392b")
    axL.set_xticks(x); axL.set_xticklabels(labels)
    axL.set_ylabel("cycles  (millions, 64-core sum)")
    axL.set_title("Where do all cycles go?  (FSM state breakdown)\n"
                  "90% is real SNN work; rollback is 10–18%", fontsize=11.5)
    axL.legend(loc="upper center", fontsize=8.5, ncol=1,
               bbox_to_anchor=(0.5, -0.10))
    axL.set_ylim(0, max(r[1] for r in rows)/1e6 * 1.12)

    # ── RIGHT: rollback_state 내부 분해 (restore vs recompute) ──
    restore = np.array([r[2] for r in rows], float) / 1e6
    recomp = np.array([r[3] for r in rows], float) / 1e6
    axR.bar(x, recomp, 0.5, label="recompute / recovery (state replay)", color="#c0392b")
    axR.bar(x, restore, 0.5, bottom=recomp,
            label="restore / bookkeeping (fixed 2 cyc/event)", color="#f39c12")
    for i, r in enumerate(rows):
        axR.text(i, recomp[i]/2, f"{r[3]/r[4]*100:.1f}%", ha="center", va="center",
                 color="white", fontsize=12, fontweight="bold")
        axR.text(i, (recomp[i]+restore[i])*1.02, f"redo={r[4]/1e6:.1f}M",
                 ha="center", va="bottom", fontsize=9.5)
    axR.set_xticks(x); axR.set_xticklabels(labels)
    axR.set_ylabel("rollback_state cycles  (millions)")
    axR.set_title("Inside rollback_state (= redo_cyc)\n"
                  "≈95% is recompute → redo already INCLUDES recovery", fontsize=11.5)
    axR.legend(loc="upper left", fontsize=9)
    axR.set_ylim(0, max(r[4] for r in rows)/1e6 * 1.2)

    fig.tight_layout()
    fig.savefig(OUT_FIG, bbox_inches="tight")


if __name__ == "__main__":
    main()
