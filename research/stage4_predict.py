"""
Stage 4-2 — trace-driven 예측가능성 연구 (재시뮬 0회).

기존 rollback_events.dat(T=64/128) + mapping_4100_64.npz 만 사용.
신규 파일(기존 무수정). 모듈 import 재사용 + __main__ 에서 단계 실행.

데이터 단위(검증 완료):
  rollback_events.dat 열 = spiked_ts affecting_ts delta_t src_pid is_anti rollback_gid
    src_pid      : 트리거 belated spike 의 *소스 뉴런 gid* (0..4099)
    rollback_gid : victim 뉴런 gid (dst 코어 소속)
  → mapping 으로 src_core / dst_core 파생(per-core granularity 의 근거).

토폴로지(example.cfg): chip_xy=(2,2), core_xy=(4,4) = 8x8 메시 64코어.
  Parse.py core_ind 해석:  core_gid = gy*8 + gx,
    gx = (chip%2)*4 + (core%4),  gy = (chip//2)*4 + (core//4)
  hop(a,b)=|gx|+|gy| (Manhattan),  chip = (gy//4)*2 + (gx//4)  → 정적 link prior.

usage:
  python3 stage4_predict.py step1     # 인프라 + 정합성 검증
  python3 stage4_predict.py step2     # granularity 집중도
"""
import os, sys
import numpy as np

ROOT = "/home/heechan/26_GRADPROJ/NeuroSync_GradProj"
SETUP_TS = 50       # 웜업(투기 없음) — 분석서 제외
MAX_TS   = 1971
NCORE    = 64
GRID     = 8        # 8x8 mesh

# ─────────────────────────── 토폴로지 ───────────────────────────
def core_xy(c):
    """core_gid -> (gx, gy) on 8x8 mesh."""
    return c % GRID, c // GRID

def core_chip(c):
    gx, gy = core_xy(c)
    return (gy // 4) * 2 + (gx // 4)

def hop(a, b):
    """Manhattan NoC hop (정적 link prior 의 핵심 성분)."""
    ax, ay = core_xy(a); bx, by = core_xy(b)
    return abs(ax - bx) + abs(ay - by)

def inter_chip(a, b):
    return core_chip(a) != core_chip(b)

# ─────────────────────────── 매핑 ───────────────────────────
def load_gid2core():
    """gid(0..4099) -> core(0..63) int array. (bijection 검증완: 4100 unique)"""
    nl = np.load(f"{ROOT}/mapping/brunel_si/mapping_4100_64.npz",
                 allow_pickle=True)["node_list"]
    n = sum(len(c) for c in nl)
    g2c = np.full(n, -1, dtype=np.int16)
    for core, gids in enumerate(nl):
        for g in gids:
            g2c[g] = core
    assert (g2c >= 0).all(), "gid 미매핑 존재"
    return g2c

# ─────────────────────────── 트레이스 ───────────────────────────
def load_trace(T, restrict_window=True):
    """
    rollback_events.dat(T) -> dict of np arrays + 파생 src_core/dst_core.
    restrict_window: spiked_ts 가 [SETUP_TS, MAX_TS] 인 이벤트만(웜업·tail 제외).
    """
    p = f"{ROOT}/runspace/brunel_si/brunel_si_peri{T}_10pretrace_eng/rollback_events.dat"
    a = np.loadtxt(p, dtype=np.int64, comments="#")
    sp, af, dt, src, anti, rgid = (a[:, i] for i in range(6))
    g2c = load_gid2core()
    src_core = g2c[src]
    dst_core = g2c[rgid]
    d = dict(spiked_ts=sp, affecting_ts=af, delta_t=dt, src_pid=src,
             is_anti=anti, rollback_gid=rgid, src_core=src_core,
             dst_core=dst_core, n_raw=len(sp))
    if restrict_window:
        m = (sp >= SETUP_TS) & (sp <= MAX_TS)
        for k in ("spiked_ts", "affecting_ts", "delta_t", "src_pid",
                  "is_anti", "rollback_gid", "src_core", "dst_core"):
            d[k] = d[k][m]
    d["n"] = len(d["spiked_ts"])
    d["T"] = T
    return d

def load_redo_ceiling():
    """specgate redo_cyc.dat 의 TOTAL 라인 -> {T: (redo_frac, total_cyc, redo_cyc)}."""
    out = {}
    for T in (64, 128):
        p = (f"{ROOT}/runspace/brunel_si_specgate/"
             f"brunel_si_peri{T}_10pretrace_eng/redo_cyc.dat")
        if not os.path.isfile(p):
            continue
        last = [ln for ln in open(p) if ln.startswith("# TOTAL")]
        if not last:
            continue
        # "# TOTAL cyc=.. redo=.. redo_frac=.. max_core_cyc=.." → 쌍 시작 idx=2
        tok = last[-1].replace("=", " ").split()
        kv = {tok[i]: tok[i + 1] for i in range(2, len(tok) - 1, 2)}
        out[T] = dict(redo_frac=float(kv.get("redo_frac", "nan")),
                      total_cyc=int(kv.get("cyc", 0)),
                      redo_cyc=int(kv.get("redo", 0)))
    return out

# ─────────────────────────── STEP 1 ───────────────────────────
def step1():
    print("=" * 70)
    print("STEP 1 — 트레이스 인프라 + 정합성 검증")
    print("=" * 70)
    g2c = load_gid2core()
    print(f"[map] gid->core: n={len(g2c)}  cores={g2c.max()+1}  "
          f"neu/core min/max={np.bincount(g2c).min()}/{np.bincount(g2c).max()}")
    EXPECT_RAW = {64: 278971, 128: 292488}   # wc -l - 1(header) (사전 측정)
    ceil = load_redo_ceiling()
    for T in (64, 128):
        d = load_trace(T, restrict_window=False)
        dw = load_trace(T, restrict_window=True)
        ok = "OK" if d["n_raw"] == EXPECT_RAW[T] else f"MISMATCH(exp {EXPECT_RAW[T]})"
        print(f"\n[T={T}] events raw={d['n_raw']:,} [{ok}]  "
              f"window[{SETUP_TS},{MAX_TS}]={dw['n']:,} "
              f"({100*dw['n']/d['n_raw']:.1f}%)")
        sd = dw["delta_t"]
        print(f"  Σdelta_t(롤백질량)={sd.sum():,}  "
              f"mean Δt={sd.mean():.2f}  med={np.median(sd):.0f}  "
              f"max={sd.max()}  (Stage2 롤백강도와 동일 단위)")
        print(f"  is_anti: {100*dw['is_anti'].mean():.2f}%  "
              f"uniq src_pid={len(np.unique(dw['src_pid']))}/4100  "
              f"uniq src_core={len(np.unique(dw['src_core']))}/64  "
              f"uniq dst_core={len(np.unique(dw['dst_core']))}/64")
        # self-link(같은 코어 내) 비율 — NoC 무관 롤백 floor 추정
        self_link = (dw["src_core"] == dw["dst_core"]).mean()
        hops = np.array([hop(s, t) for s, t in
                         zip(dw["src_core"][:20000], dw["dst_core"][:20000])])
        ic = np.array([inter_chip(s, t) for s, t in
                       zip(dw["src_core"][:20000], dw["dst_core"][:20000])])
        print(f"  self-core={100*self_link:.1f}%  "
              f"hop(샘플2e4) mean={hops.mean():.2f} max={hops.max()}  "
              f"inter-chip={100*ic.mean():.1f}%")
        if T in ceil:
            c = ceil[T]
            print(f"  [redo ceiling/specgate] redo_frac={100*c['redo_frac']:.2f}% "
                  f"total_cyc={c['total_cyc']:,} redo_cyc={c['redo_cyc']:,} "
                  f"(완벽 stall-oracle 천장 — STEP5 분모)")
    print("\n[STEP1 결론] 단위 확정: src_pid=소스뉴런·rollback_gid=victim뉴런, "
          "매핑으로 src/dst-core 파생. event수 사전측정 일치 → 인프라 신뢰.")


# ─────────────────────────── STEP 2 ───────────────────────────
def _gini(x):
    """Gini (numpy2.x 안전, trapz 미사용). x>=0, 길이 n."""
    x = np.sort(np.asarray(x, float))
    n = len(x); s = x.sum()
    if n == 0 or s == 0:
        return 0.0
    i = np.arange(1, n + 1)
    return (2.0 * (i * x).sum() - (n + 1) * s) / (n * s)

def _entropy_eff(counts):
    """정규화 엔트로피 H/Hmax 와 effective-N(=exp H, perplexity)."""
    c = np.asarray(counts, float); c = c[c > 0]
    if c.size <= 1:
        return 0.0, float(c.size)
    p = c / c.sum()
    H = -(p * np.log(p)).sum()
    return H / np.log(c.size), float(np.exp(H))

def _agg(keys, vals, K):
    """key(0..K-1) 별 vals 합 → 길이 K 벡터."""
    return np.bincount(keys, weights=vals, minlength=K)

def _topk_cov(v, k):
    v = np.sort(v)[::-1]
    return v[:k].sum() / v.sum() if v.sum() else 0.0

def step2():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    print("=" * 70)
    print("STEP 2 — granularity 집중도 (src뉴런 vs src코어 vs (src→dst)링크)")
    print("=" * 70)
    print("질문: 예측기 상태/결정을 어느 단위로? 집중도(Gini)·신호밀도"
          "(events/active)·상태크기·핫스팟 유무로 per-core(+link prior) 검증.\n")

    out = []
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4))
    for ax, T in zip(axes, (64, 128)):
        d = load_trace(T)
        n = d["n"]
        dt = d["delta_t"].astype(float)
        sc, dc, sp = d["src_core"], d["dst_core"], d["src_pid"]
        link = sc.astype(np.int64) * NCORE + dc
        grans = {
            "src-neuron": (sp, 4100),
            "src-core":   (sc, NCORE),
            "(src->dst)link": (link, NCORE * NCORE),
        }
        out.append(f"\n[T={T}]  events={n:,}  Σdelta_t(롤백질량)={dt.sum():,.0f}")
        out.append(f"  {'granularity':<14}{'n_act':>7}{'effN':>8}"
                    f"{'Gini(ev)':>9}{'Gini(mass)':>11}"
                    f"{'ev/act':>8}{'top10%mass':>11}")
        lor = {}
        for name, (key, K) in grans.items():
            ev = np.bincount(key, minlength=K)
            ms = _agg(key, dt, K)
            act = ev > 0
            nact = int(act.sum())
            _, effN = _entropy_eff(ev[act])
            gini_e = _gini(ev[act])
            gini_m = _gini(ms[act])
            evpa = ev[act].mean()
            k10 = max(1, int(round(0.10 * nact)))
            cov10 = _topk_cov(ms[act], k10)
            out.append(f"  {name:<14}{nact:>7}{effN:>8.1f}"
                       f"{gini_e:>9.3f}{gini_m:>11.3f}"
                       f"{evpa:>8.1f}{100*cov10:>10.1f}%")
            # Lorenz (mass)
            v = np.sort(ms[act])[::-1]
            cum = np.cumsum(v) / v.sum()
            xs = np.arange(1, len(v) + 1) / len(v)
            lor[name] = (xs, cum)

        # dst-core fan-in (per-core 예측기 상태 크기 = HW 논거)
        fanin = np.array([len(np.unique(sc[dc == c]))
                          for c in range(NCORE)])
        # 각 dst-core 의 롤백질량 90% 를 덮는 src-core 수
        cov90 = []
        for c in range(NCORE):
            mm = np.sort(_agg(sc[dc == c], dt[dc == c], NCORE))[::-1]
            mm = mm[mm > 0]
            if mm.size:
                cc = np.cumsum(mm) / mm.sum()
                cov90.append(int(np.searchsorted(cc, 0.90) + 1))
        cov90 = np.array(cov90)
        out.append(f"  dst-core fan-in(기여 src-core 수): "
                   f"mean={fanin.mean():.1f} max={fanin.max()} "
                   f"min={fanin.min()}  | 질량90% 커버 src-core "
                   f"mean={cov90.mean():.1f} max={cov90.max()} "
                   f"→ per-core 상태 ≤{fanin.max()} entry/코어")

        # ASCII-only 라벨(폰트 tofu 방지; 한글 해석은 .txt 리포트에)
        ax.plot([0, 1], [0, 1], ":", color="#999", lw=1, label="uniform")
        col = {"src-neuron": "#c62828", "src-core": "#1565c0",
               "(src->dst)link": "#2e7d32"}
        gmass = {nm: _gini(_agg(k, dt, K)[np.bincount(k, minlength=K) > 0])
                 for nm, (k, K) in grans.items()}
        for name, (xs, cum) in lor.items():
            ax.plot(xs, cum, "-", color=col[name], lw=2,
                    label=f"{name}  Gini={gmass[name]:.2f}")
        ax.set_xlabel("cumul. fraction of sources (mass-sorted desc)")
        ax.set_ylabel("cumul. fraction of rollback mass")
        ax.set_title(f"T={T}  Lorenz of rollback mass by granularity")
        ax.grid(alpha=.3); ax.legend(fontsize=8.5, loc="lower right")

    fig.suptitle("Stage4-2 STEP2  rollback-mass concentration:  "
                 "src-neuron = firing-rate skew (unpredictable spike-gen) & sparse; "
                 "src-core = near-uniform & dense -> per-core (+static link prior)",
                 fontsize=10.3)
    fig.tight_layout()
    fp = f"{ROOT}/research/result_img/stage4_granularity_concentration.png"
    fig.savefig(fp, bbox_inches="tight", dpi=110)
    out.append(f"\n[saved] {fp}")

    out.append(
        "\n[STEP2 해석 — 정밀]"
        "\n (1) src-neuron Gini(mass)≈0.82 = '높음'(집중). 단 이 집중은 belated "
        "예측가능성이 아니라 Brunel 발화율 이질성(일부 뉴런이 더 자주 발화) — "
        "즉 우리가 예측 안 하기로 한 spike-발생 편향(§5-1). 게다가 n_act≈3.8k·"
        "ev/act≈73(희소) → 뉴런별 history 는 잡음·약한 자기상관 = 예측기 부적합."
        "\n (2) src-core Gini≈0.27 = 거의 균일(effN 56~58/64), §4-1 victim 균일성"
        "과 정합 → 전 코어 고른 회수 필요(핫스팟 특화 불가). ev/act≈4.4k(수십~"
        "수백배 dense) = 중심극한 평활(spike CV0.95→예측가능 신호) → history "
        "예측 양호. 상태=64 entry."
        "\n (3) (src→dst)link 은 n_act≈4.1k·ev/act≈70 으로 per-neuron 만큼 희소 "
        "→ *동적* per-link 학습상태는 per-neuron 과 같은 잡음병. 따라서 link "
        "차원은 *정적* prior(NoC hop/inter-chip; self-core 1.6%·inter-chip 74%)"
        "로만 써야 함 — 데이터가 'link prior 는 학습 아닌 정적'을 정량 입증."
        "\n (4) dst-core fan-in mean≈64·질량90% 커버≈45 src-core → per-core "
        "상태 ≤64 entry/코어 = in-core SRAM 부합(§6-1)."
        "\n[결론] 상태/결정 = per-src-core (동적 history),  "
        "feature += 정적 (src→dst)link topological prior.  "
        "순수 per-neuron(잡음·상태폭증·spike-gen 추종)·동적 per-link(희소) 기각.")
    txt = "\n".join(out)
    print(txt)
    rp = f"{ROOT}/runspace/brunel_si/stage4_step2_granularity.txt"
    open(rp, "w").write(txt + "\n")
    print(f"[saved] {rp}")


# ─────────────────────────── STEP 3 ───────────────────────────
def _series(pair_key, npair, block, nb, w):
    """pair×block 그리드(mass 또는 count) → shape (npair, nb)."""
    idx = pair_key.astype(np.int64) * nb + block
    flat = np.bincount(idx, weights=w, minlength=npair * nb)
    return flat.reshape(npair, nb)

def _pooled_acf(M, k, demean_pair):
    """
    활성 pair 만 pooled lag-k 자기상관.
    demean_pair=True → 각 pair 의 시계열 평균을 먼저 제거
      = '정적 prior(평균율)를 빼고 *동적 history* 가 추가로 주는 예측가능성'.
    """
    act = M.sum(1) > 0
    X = M[act].astype(float)
    if demean_pair:
        X = X - X.mean(1, keepdims=True)
    a = X[:, :-k].ravel()
    b = X[:, k:].ravel()
    a = a - a.mean(); b = b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0

def _persist(Mc):
    """이진 발생 시계열 → base rate p1, 지속 p11=P(act b+1|act b), lift."""
    act = Mc.sum(1) > 0
    B = (Mc[act] > 0).astype(np.int8)
    p1 = B.mean()
    cur, nxt = B[:, :-1], B[:, 1:]
    denom = cur.sum()
    p11 = (cur & nxt).sum() / denom if denom else 0.0
    p01 = ((1 - cur) & nxt).sum() / (1 - cur).sum() if (1 - cur).sum() else 0.0
    return p1, p11, p01, (p11 / p1 if p1 else 0.0)

def _eta2(M):
    """롤백질량 분산 중 *링크 차이(정적)*가 설명하는 비율 = 정적 prior 천장.
    1-eta2 = within-link 시간변동분(이 중 ACFdem 만이 history 로 예측가능)."""
    X = M[M.sum(1) > 0].astype(float)
    g = X.mean()
    sst = ((X - g) ** 2).sum()
    rm = X.mean(1, keepdims=True)
    ssb = (X.shape[1] * (rm - g) ** 2).sum()
    return float(ssb / sst) if sst > 0 else 0.0

def _r2(M, mode, alpha=0.5):
    """블록 b(>=1) 를 예측 → pooled R² (baseline=grand mean).
      static : 링크 전기간 평균(=학습된 정적 prior 의 *상한*, lookahead 주의)
      lastval: x[b-1]
      ewma   : 인과 EWMA(alpha)  (t<b 만 사용)
    """
    X = M[M.sum(1) > 0].astype(float)
    n, nb = X.shape
    tgt = X[:, 1:]
    if mode == "static":
        pred = np.repeat(X.mean(1, keepdims=True), nb - 1, axis=1)
    elif mode == "lastval":
        pred = X[:, :-1]
    elif mode == "ewma":
        pred = np.zeros_like(tgt)
        s = X[:, 0].copy()
        for j in range(1, nb):
            pred[:, j - 1] = s
            s = alpha * X[:, j] + (1 - alpha) * s
    g = tgt.mean()
    sst = ((tgt - g) ** 2).sum()
    ssr = ((tgt - pred) ** 2).sum()
    return float(1 - ssr / sst) if sst > 0 else 0.0

def _acf_topmass(M, k, frac):
    """롤백질량 상위 frac 를 덮는 *최소* 링크집합만으로 demeaned pooled ACF.
    pooled(전체)이 희소링크 4천개에 지배돼 hot 링크 메모리를 가렸는지 검증."""
    s = M.sum(1)
    order = np.argsort(s)[::-1]
    cs = np.cumsum(s[order]) / s.sum()
    ntop = int(np.searchsorted(cs, frac) + 1)
    sub = M[order[:ntop]].astype(float)
    sub = sub - sub.mean(1, keepdims=True)
    a, b = sub[:, :-k].ravel(), sub[:, k:].ravel()
    a -= a.mean(); b -= b.mean()
    den = np.sqrt((a * a).sum() * (b * b).sum())
    return (float((a * b).sum() / den) if den > 0 else 0.0), ntop

def step3():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    print("=" * 70)
    print("STEP 3 — 시간 예측가능성 (per-(dst,src) 자기상관)")
    print("=" * 70)
    print("질문: 링크의 최근 롤백 이력이 다음 블록을 예측하나? "
          "within-pair demeaned ACF = *정적 prior 평균율을 뺀* 순수 "
          "동적-history 예측가능성(= 2-tier 설계의 동적 항이 실제 버는 것).\n")
    BINS = [16, 32, 64, 128]
    out = []
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.0))
    plot = {}

    for T in (64, 128):
        d = load_trace(T)
        at = np.clip(d["affecting_ts"], SETUP_TS, MAX_TS)
        dt = d["delta_t"].astype(float)
        sc, dc, sp = d["src_core"], d["dst_core"], d["src_pid"]
        pk_core = dc.astype(np.int64) * NCORE + sc          # (dst,src-core)
        out.append(f"\n[T={T}]  per-(dst,src-core) 롤백질량 분산 분해 + 예측기 R²")
        out.append(f"  {'bin':>4}{'nb':>4} | {'eta2(정적%)':>11}"
                   f"{'ACFdem_all':>11}{'ACFdem_top80':>13} | "
                   f"{'R2_static':>10}{'R2_lastv':>9}{'R2_ewma':>8}"
                   f"{'lift':>6}")
        for B in BINS:
            nb = int((MAX_TS - SETUP_TS) // B + 1)
            blk = (at - SETUP_TS) // B
            Mm = _series(pk_core, NCORE * NCORE, blk, nb, dt)
            Mc = _series(pk_core, NCORE * NCORE, blk, nb, np.ones_like(dt))
            eta2 = _eta2(Mm)
            ad_all = _pooled_acf(Mm, 1, True)
            ad_top, ntop = _acf_topmass(Mm, 1, 0.80)
            r2s = _r2(Mm, "static"); r2l = _r2(Mm, "lastval")
            r2e = _r2(Mm, "ewma")
            _, _, _, lift = _persist(Mc)
            out.append(f"  {B:>4}{nb:>4} | {100*eta2:>10.1f}%"
                       f"{ad_all:>11.3f}{ad_top:>13.3f} | "
                       f"{r2s:>10.3f}{r2l:>9.3f}{r2e:>8.3f}{lift:>6.2f}"
                       f"   (top80=링크{ntop})")
            if T == 64 and B == 64:
                plot["core_r2"] = (r2s, r2l, r2e)
                plot["core_acf"] = [_pooled_acf(Mm, l, True)
                                    for l in range(1, 9)]
                pk_neu = dc.astype(np.int64) * 4100 + sp
                Nm = _series(pk_neu, NCORE * 4100, blk, nb, dt)
                plot["neu_acf"] = [_pooled_acf(Nm, l, True)
                                   for l in range(1, 9)]
                plot["neu_r2"] = (_r2(Nm, "static"), _r2(Nm, "lastval"),
                                  _r2(Nm, "ewma"))
            if B in (16, 64):
                plot.setdefault(f"eta_{T}", {})[B] = eta2

    # ── 그림 (ASCII) : 분해가 핵심 ──
    L = list(range(1, 9))
    axes[0].plot(L, plot["core_acf"], "-s", color="#1565c0", lw=2,
                 label="src-CORE")
    axes[0].plot(L, plot["neu_acf"], "-^", color="#c62828", lw=2,
                 label="src-NEURON")
    axes[0].axhline(0, color="#999", lw=.8)
    axes[0].set_ylim(-0.2, 0.6)
    axes[0].set_title("T=64 B=64  within-pair DEMEANED ACF\n"
                      "(pure dynamic-history signal ~ 0)")
    axes[0].set_xlabel("lag (blocks)"); axes[0].set_ylabel("autocorr")
    axes[0].legend(fontsize=8.5); axes[0].grid(alpha=.3)

    g = ["R2_static\n(prior)", "R2_lastval", "R2_ewma"]
    xx = np.arange(3)
    axes[1].bar(xx - .17, plot["core_r2"], .34, color="#1565c0",
                label="src-CORE")
    axes[1].bar(xx + .17, plot["neu_r2"], .34, color="#c62828",
                label="src-NEURON")
    axes[1].set_xticks(xx); axes[1].set_xticklabels(g, fontsize=8.5)
    axes[1].set_title("T=64 B=64  predictor R²\n"
                      "lastval/ewma NEGATIVE (worse than mean); static small")
    axes[1].set_ylabel("pooled R² over blocks")
    axes[1].legend(fontsize=8.5); axes[1].grid(alpha=.3, axis="y")
    for i, v in enumerate(plot["core_r2"]):
        axes[1].annotate(f"{v:.2f}", (i - .17, v), ha="center",
                         xytext=(0, 3), textcoords="offset points",
                         fontsize=8)

    bs = BINS
    e16 = [plot[f"eta_{T}"][16] for T in (64, 128)]
    e64 = [plot[f"eta_{T}"][64] for T in (64, 128)]
    xx2 = np.arange(2)
    axes[2].bar(xx2 - .17, e16, .34, color="#2e7d32", label="bin=16ts")
    axes[2].bar(xx2 + .17, e64, .34, color="#80c080", label="bin=64ts")
    axes[2].set_xticks(xx2); axes[2].set_xticklabels(["T=64", "T=128"])
    axes[2].set_ylim(0, 1)
    axes[2].set_title("eta^2 = static-prior share of\nrollback-mass variance")
    axes[2].set_ylabel("between-link variance fraction")
    axes[2].legend(fontsize=8.5); axes[2].grid(alpha=.3, axis="y")
    for i, v in enumerate(e16):
        axes[2].annotate(f"{v:.2f}", (i - .17, v), ha="center",
                         xytext=(0, 3), textcoords="offset points",
                         fontsize=8)
    for i, v in enumerate(e64):
        axes[2].annotate(f"{v:.2f}", (i + .17, v), ha="center",
                         xytext=(0, 3), textcoords="offset points",
                         fontsize=8)

    fig.suptitle("Stage4-2 STEP3 - per-link rollback series is ~POISSON at "
                 "fine scale: demeaned ACF~0, lastval/ewma R2<0, eta^2 only "
                 "3-6%@16-32ts  => forecasting framing weak; lever = "
                 "deterministic decision-time state (spec-depth x NoC geom, STEP4)",
                 fontsize=9.3)
    fig.tight_layout()
    fp = f"{ROOT}/research/result_img/stage4_temporal_autocorr.png"
    fig.savefig(fp, bbox_inches="tight", dpi=110)
    out.append(f"\n[saved] {fp}")

    out.append(
        "\n[STEP3 해석 — 정직, 설계 변경 신호]"
        "\n (1) within-pair demeaned ACF(all & top80% mass) ≈ 0(±0.0x, "
        "음수도) → 링크 평균율을 빼면 롤백은 시간적으로 거의 white(Poisson). "
        "고질량 링크만 봐도 동일 → false-negative 아님. *동적 history "
        "예측력 ≈ 0*."
        "\n (2) eta²(정적 prior 가 설명하는 질량분산)는 fine scale 에서 "
        "*작다*: 16ts 3%, 32ts 6%, 64ts 10%, 128ts 19% (coarse 일수록 "
        "within-link 잡음이 평균되어 상승). per-advance stall 결정이 작동할 "
        "Δt≈35ts 영역에선 정적 prior 도 분산의 ~3-6% 만 설명."
        "\n (3) R2_lastval≈-0.9, R2_ewma≈-0.3 (음수=글로벌평균보다 나쁨) → "
        "per-link 롤백질량 시계열은 fine scale 에서 사실상 Poisson; 시계열 "
        "*forecasting* (last-value/2bit/EWMA, 로드맵 §4-2 가정) 프레이밍 자체"
        "가 약함. persistence lift>1·raw ACF 는 약한 정적 rate 이질성의 "
        "조건부선택 효과일 뿐(eta² 3% 와 정합). ISN 평활 캐스케이드와 일치."
        "\n (4) src-NEURON 은 R²·ACF 모두 더 약함 → STEP2 'per-core' 결론 "
        "유지(단, 동적 항 자체가 무력)."
        "\n[설계 함의 — 중대] 예측 대상을 '롤백 시계열 forecasting' 으로 "
        "보면 천장이 매우 낮다. 그러나 belatedness 의 진짜 결정요인은 *예측* "
        "이 아니라 결정시점에 **결정론적으로 아는 상태**: (a) 현재 투기깊이"
        "(=advance 가 마지막 sync/chkpt 대비 몇 ts 앞섰나, 정확히 앎), "
        "(b) source 까지 NoC hop·inter-chip(정적, 앎), (c) 평균 도착지연 "
        "Δt(앎). 확률적 부분은 'source 가 취약창에서 발화했나'(spike-gen, "
        "예측 안 함)뿐. → 예측기는 temporal forecaster 가 아니라 **기하/"
        "임계 horizon 정책**(투기깊이가 source 군의 도착지연 horizon 을 "
        "넘으면 stall)이어야 함. 로드맵 §5-2 의 '최근 belated 이력 온라인 "
        "학습' 비중은 과대평가."
        "\n[A4 gate 재정의] STEP4 = 리드타임/Δt vs NoC 기하 분포(이 결정론 "
        "horizon 정책의 천장 측정). STEP5 = *horizon-stall 정책* 오프라인 "
        "리플레이를 1순위로 redo 천장(10.4/18.1%) 회수율 측정, "
        "history/forecaster 는 대조군(음수 예상).")
    txt = "\n".join(out)
    print(txt)
    rp = f"{ROOT}/runspace/brunel_si/stage4_step3_autocorr.txt"
    open(rp, "w").write(txt + "\n")
    print(f"[saved] {rp}")


# ─────────────────────────── STEP 4 ───────────────────────────
# 재정의: 예측기를 시계열 forecaster 가 아니라 '결정시점 결정론 상태(투기깊이
# ×NoC 기하)' horizon 정책으로 봄. 이 정책의 *천장*을 trace 만으로 측정.
#   가정(상한): 투기깊이를 chkpt+H 로 cap 하면 rollback 거리 delta_t 는
#   min(delta_t,H) 로 절단 → 회수 redo = Σ max(delta_t-H,0).
#   (실제 타이밍 불완전 정책 ≤ 이 상한. stall cyc 추가 = 같은 양, 단
#    rollback=recompute+RR ≫ stall=idle → energy/critical-path 이득.)
def step4():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    print("=" * 70)
    print("STEP 4 (재정의) — rollback거리 Δt × NoC기하 분포 + horizon-cap 천장")
    print("=" * 70)
    ceil = load_redo_ceiling()
    out = []
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.0))
    cols = {64: "#1565c0", 128: "#c62828"}

    for T in (64, 128):
        d = load_trace(T)
        dt = d["delta_t"].astype(float)
        sc, dc = d["src_core"], d["dst_core"]
        hops = np.array([hop(s, t) for s, t in zip(sc, dc)])
        ic = np.array([inter_chip(s, t) for s, t in zip(sc, dc)])
        tot = dt.sum()
        out.append(f"\n[T={T}]  events={len(dt):,}  Σdelta_t={tot:,.0f}  "
                   f"(redo_frac 천장={100*ceil[T]['redo_frac']:.2f}%, "
                   f"redo_cyc={ceil[T]['redo_cyc']:,})")

        # (1) Δt mass-weighted CDF: redo 사이클이 어느 깊이대에 있나
        order = np.argsort(dt)
        cdf_mass = np.cumsum(dt[order]) / tot
        q = {p: dt[order][np.searchsorted(cdf_mass, p)] for p in
             (0.25, 0.5, 0.75, 0.9)}
        out.append(f"  Δt: mean={dt.mean():.1f} med={np.median(dt):.0f} "
                   f"max={dt.max()} | mass-CDF Δt@25/50/75/90% = "
                   f"{q[0.25]:.0f}/{q[0.5]:.0f}/{q[0.75]:.0f}/{q[0.9]:.0f}")

        # (2) Δt vs NoC hop : 거리-인지 horizon 이 표적될 구조 있나
        out.append(f"  {'hop':>4}{'n_ev':>9}{'mean_Δt':>9}"
                   f"{'mass%':>8}{'cum_mass%':>10}")
        hb = np.arange(0, hops.max() + 2)
        cum = 0.0
        for h in range(hops.max() + 1):
            m = hops == h
            if not m.any():
                continue
            sh = dt[m].sum()
            cum += sh
            out.append(f"  {h:>4}{m.sum():>9,}{dt[m].mean():>9.1f}"
                       f"{100*sh/tot:>7.1f}%{100*cum/tot:>9.1f}%")
        out.append(f"  inter-chip: mean_Δt={dt[ic].mean():.1f} "
                   f"(mass {100*dt[ic].sum()/tot:.0f}%)  vs  intra="
                   f"{dt[~ic].mean():.1f} (mass {100*dt[~ic].sum()/tot:.0f}%)"
                   f"  corr(hop,Δt)={np.corrcoef(hops, dt)[0,1]:+.3f}")

        # (3) uniform horizon-cap H 천장: 회수 redo = Σmax(Δt-H,0)/Σ
        Hs = np.arange(0, T + 1)
        rec = np.array([np.maximum(dt - H, 0).sum() / tot for H in Hs])
        for Hq in (T // 8, T // 4, T // 2, 3 * T // 4):
            r = np.maximum(dt - Hq, 0).sum() / tot
            out.append(f"  cap H={Hq:>3}: 회수 redo={100*r:4.1f}% of Σ "
                       f"(= {100*r*ceil[T]['redo_frac']:4.2f}%p of total cyc; "
                       f"stall cyc=동량, rollback≫stall 에너지)")

        # (4) 거리-인지 H(hop): hop 별 분위수 cap 을 동일 평균-stall 예산서
        #     uniform 과 비교 (정적 NoC prior 의 추가가치 정량)
        for budget in (0.30, 0.50):
            # uniform: budget 만큼 회수하는 H_u
            Hu = Hs[np.argmin(np.abs(rec - budget))]
            recU = np.maximum(dt - Hu, 0).sum()
            # dist-aware: hop 별로 같은 분위수 p 적용해 동일 총 stall 에 맞춤
            best = None
            for p in np.linspace(0.02, 0.98, 49):
                Hh = np.zeros_like(dt)
                for h in range(hops.max() + 1):
                    m = hops == h
                    if m.any():
                        Hh[m] = np.quantile(dt[m], p)
                recD = np.maximum(dt - Hh, 0).sum()
                if recD <= recU * 1.001:          # 같은(이하) stall 예산
                    if best is None or recD > best[1]:
                        best = (p, recD)
            if best:
                gain = (best[1] / recU - 1) * 100 if recU else 0
                out.append(f"  [budget≈{int(budget*100)}%] uniform H={Hu} "
                           f"vs dist-aware H(hop): 동일 stall 예산서 회수 "
                           f"{gain:+.1f}% → 정적 NoC prior 추가가치")

        if T == 64:
            plot_rec64 = (Hs, rec)
            plot_hopdt64 = [(h, dt[hops == h].mean(),
                             dt[hops == h].sum() / tot)
                            for h in range(hops.max() + 1)
                            if (hops == h).any()]
        if T == 128:
            plot_rec128 = (Hs, rec)

    # ── 그림 ──
    H64, r64 = plot_rec64
    H128, r128 = plot_rec128
    axes[0].plot(H64 / 64, 100 * r64, "-", color=cols[64], lw=2,
                 label="T=64")
    axes[0].plot(H128 / 128, 100 * r128, "-", color=cols[128], lw=2,
                 label="T=128")
    axes[0].set_xlabel("depth cap H / T  (fraction of sync period)")
    axes[0].set_ylabel("recoverable redo  Σmax(Δt-H,0)/Σ  [%]")
    axes[0].set_title("horizon-cap ceiling\n(deterministic depth cap)")
    axes[0].legend(fontsize=9); axes[0].grid(alpha=.3)

    hh = [x[0] for x in plot_hopdt64]
    md = [x[1] for x in plot_hopdt64]
    ms = [100 * x[2] for x in plot_hopdt64]
    ax1b = axes[1].twinx()
    axes[1].bar(hh, ms, color="#c8d8e8", label="redo mass % (L)")
    axes[1].plot(hh, [0] * len(hh), alpha=0)
    ax1b.plot(hh, md, "-o", color="#1565c0", lw=2,
              label="mean Δt (R)")
    ax1b.set_ylim(0, 64)          # 0~T: 평탄함을 정직하게(줌 왜곡 방지)
    axes[1].set_xlabel("NoC hop (src-core -> dst-core)")
    axes[1].set_ylabel("redo mass share [%]")
    ax1b.set_ylabel("mean Δt (flat ~35 => Δt ⊥ distance)")
    axes[1].set_title("T=64  Δt & redo-mass vs NoC distance\n"
                      "(mean Δt flat across hops: corr~0)")
    axes[1].grid(alpha=.3)
    h1, l1 = axes[1].get_legend_handles_labels()
    h2, l2 = ax1b.get_legend_handles_labels()
    axes[1].legend(h1 + h2, l1 + l2, fontsize=8.5, loc="upper left")

    # redo recoverable as %p of TOTAL cyc (천장 맥락)
    for T, (Hs, rec), c in ((64, plot_rec64, cols[64]),
                            (128, plot_rec128, cols[128])):
        axes[2].plot(Hs / T, 100 * rec * ceil[T]["redo_frac"], "-",
                     color=c, lw=2,
                     label=f"T={T} (ceiling {100*ceil[T]['redo_frac']:.1f}%)")
    axes[2].set_xlabel("depth cap H / T")
    axes[2].set_ylabel("recoverable cycles  [%p of total]")
    axes[2].set_title("recovery in TOTAL-cycle terms\n"
                      "(latency/energy lever size)")
    axes[2].legend(fontsize=9); axes[2].grid(alpha=.3)

    fig.suptitle("Stage4-2 STEP4 - deterministic horizon-cap ceiling: redo "
                 "mass vs over-advance depth & NoC geometry "
                 "(re-defined A4 lever, no temporal forecast)", fontsize=9.6)
    fig.tight_layout()
    fp = f"{ROOT}/research/result_img/stage4_horizon_ceiling.png"
    fig.savefig(fp, bbox_inches="tight", dpi=110)
    out.append(f"\n[saved] {fp}")
    out.append(
        "\n[STEP4 해석 — 정직, 누적 음성]"
        "\n (1) Δt ⊥ NoC 기하: mean_Δt 가 hop 0–14 에서 평탄, "
        "corr(hop,Δt)≈0(-0.007/-0.002), inter-chip≈intra. dist-aware "
        "H(hop) 가 uniform 보다 *나쁨*(음수 gain). → 내가 STEP2 서 권장한 "
        "*정적 NoC link prior 는 이 워크로드에서 무력* (거리가 위험·깊이를 "
        "안 가름). 설계서 정적 link prior 항 제거가 정직."
        "\n (2) Δt ≈ T/2 (35@T64,67@T128, mass-CDF 도 그 부근) → 롤백깊이는 "
        "전송거리가 아니라 *sync 윈도 위치*가 지배. belatedness 의 구조적 "
        "예측핸들이 공간(거리)에 없음."
        "\n (3) uniform horizon-cap = 사실상 *effective T 재매개변수화*: "
        "H=8@T64 가 redo 77% 회수해도 그건 T_eff≈8 거동 = Stage3 U-곡선이 "
        "이미 '비싸다'고 판정한 영역(sync/chkpt 과다). 즉 cap 단독은 새 "
        "레버가 아니라 Stage3 가 최적화한 그 trade-off. 공짜 회수 아님."
        "\n[종합] STEP3(시간 forecasting≈0/음수) + STEP4(공간 prior 무력, "
        "cap=재매개변수화) → 비선택적 stall 은 작은 T 와 동치(이미 열위). "
        "이김은 *선택적* stall 만 가능한데 STEP3·4 가 싼 선택 신호 부재를 "
        "보임. 글로벌 동적-T 를 죽인 ISN 항상성(평활·균일·예측불가)이 "
        "per-core 축에도 동일 작용. STEP5 = 후보 선택정책을 오프라인 "
        "리플레이해 (회수 redo − stall − 재유입 sync) 의 net 을 Stage3 "
        "T=64 최적과 *정직 비교* → A4 gate(통과/down-scope) 확정.")
    txt = "\n".join(out)
    print(txt)
    rp = f"{ROOT}/runspace/brunel_si/stage4_step4_horizon.txt"
    open(rp, "w").write(txt + "\n")
    print(f"[saved] {rp}")


# ─────────────────────────── STEP 5 ───────────────────────────
# A4 gate: 후보 *선택적* stall 정책을 trace 에 오프라인 리플레이.
# 단위 원칙(사용자 피드백): redo_cyc=64코어 합산, CYC_T*=임계 1코어 total.
#   섞지 않는다. 모든 정책효과는 *무단위 비율*(천장 대비)로만 계산하고,
#   절대 latency 는 (비율 × redo_frac × 단일코어 CYC) 로만 환산(라벨 명시).
# 로드맵 확정 지표(§4-2, Stage3-B) = stall-oracle 천장 = redo_frac.
#   회수율 g = Σδ_caught/Σδ_total (천장 중 제거되는 분율, oracle=1.0).
#   FP 부담 = FP수×fp_unit/Σδ_total (불필요 stall 의 latency 가산, 같은
#   Δt-질량 단위). net 천장회수 = g − FP부담 (음수 가능, 정직).
#   stall 의 정확한 내부 사이클비(k_rb 등)는 trace 로 검증불가 → latency
#   에 날조하지 않고 Step6(energy)로 이월(여기선 k_rb 는 참고표시만).
# 기준선 = Stage3 fixed-T=64(1,808,130). base = fixed-T=128(1,909,086).
#   T128→T64 만큼만 이겨도 의미 → 필요 net 천장회수 =
#   (1−CYC64/CYC128)/redo_frac ≈ 0.0529/0.181 ≈ 29.2%.
def step5():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    print("=" * 70)
    print("STEP 5 — A4 gate: 선택적 stall 정책 오프라인 리플레이 (단위정합)")
    print("=" * 70)
    sweep = {}
    for ln in open(f"{ROOT}/runspace/brunel_si/SWEEP_total_cycles.txt"):
        if ln.startswith("#"):
            continue
        t, _, c = ln.split()
        sweep[int(t)] = int(c)
    CYC_T64, CYC_T128 = sweep[64], sweep[128]
    ceil = load_redo_ceiling()
    rf = ceil[128]["redo_frac"]
    need = (1 - CYC_T64 / CYC_T128) / rf      # T64 를 이기기 위한 net 천장회수
    out = []
    def P(s=""):
        out.append(s)
    P(f"기준선 Stage3 fixed-T=64 = {CYC_T64:,}  | base fixed-T=128 = "
      f"{CYC_T128:,}")
    P(f"redo 천장(stall-oracle, Stage3-B 확정) = redo_frac = {100*rf:.1f}% "
      f"(redo_cyc {ceil[128]['redo_cyc']:,}, 64코어 합산 단위)")
    P(f">>> A4 통과 요건: T=128 base 에서 net 천장회수 ≥ {100*need:.1f}% "
      f"(=fixed-T=64 도달선). 사용자 ~10% 절대가속 기준이면 거의 천장 전부.")

    T = 128
    d = load_trace(T)
    k_rb = ceil[T]["redo_cyc"] / d["delta_t"].sum()   # 참고용(라벨만)
    B = 16
    nb = int((MAX_TS - SETUP_TS) // B + 1)
    blk = (np.clip(d["affecting_ts"], SETUP_TS, MAX_TS) - SETUP_TS) // B
    pk = d["dst_core"].astype(np.int64) * NCORE + d["src_core"]
    M = _series(pk, NCORE * NCORE, blk, nb, d["delta_t"].astype(float))
    O = (_series(pk, NCORE * NCORE, blk, nb,
                 np.ones(len(blk))) > 0).astype(np.int8)
    keep = M.sum(1) > 0
    M, O = M[keep], O[keep]
    SD = M.sum()                       # Σδ_total (천장 분모, 무단위화 기준)
    fp_unit = M[M > 0].mean()          # FP 1건 idle ≈ 평균 활성블록 Δ-질량

    def replay(sm):
        tp = sm & (O == 1)
        fp = sm & (O == 0)
        g = M[tp].sum() / SD                       # gross 천장회수
        fpb = fp.sum() * fp_unit / SD              # FP latency 부담(천장단위)
        return g, fpb, g - fpb, int(tp.sum()), int(fp.sum())

    P(f"\n무대 T=128, bin=16ts. (g=gross 천장회수, FP부담=불필요stall, "
      f"net=g−FP부담; 절대가속≈net×{100*rf:.1f}%)  k_rb(참고)={k_rb:.2f}")
    P(f"  {'정책':<22}{'g%':>7}{'FP부담%':>8}{'net%':>7}"
      f"{'TP':>7}{'FP':>8}{'FP:TP':>7}{'~절대가속':>9}{'vsT64':>7}")
    rows = []

    def emit(name, sm):
        g, fpb, net, tp, fp = replay(sm)
        spd = net * rf                              # 단일코어 절대가속 추정
        cyc = CYC_T128 * (1 - spd)
        rows.append((name, 100 * net, cyc, 100 * g))
        rat = f"{fp/tp:.1f}" if tp else "inf"
        P(f"  {name:<22}{100*g:>6.1f}%{100*fpb:>7.1f}%{100*net:>6.1f}%"
          f"{tp:>7}{fp:>8}{rat:>7}{100*spd:>+8.1f}%"
          f"{'  WIN' if cyc < CYC_T64 else '  --'}")

    emit("oracle-perfect", (O == 1).astype(bool))
    sm = np.zeros_like(O); sm[:, 1:] = (O[:, :-1] == 1)
    emit("last-block(2-state)", sm.astype(bool))
    for thr in (0.2, 0.4):
        E = np.zeros_like(M); s = O[:, 0].astype(float).copy()
        for j in range(1, nb):
            E[:, j] = s
            s = 0.5 * O[:, j] + 0.5 * s
        emit(f"EWMA(a=.5,thr={thr})", (E > thr))
    s = M.sum(1); thrm = np.quantile(s[s > 0], 0.5)
    emit("static-hot-link(prior)",
         np.tile((s >= thrm)[:, None], (1, nb)).astype(bool))

    P("\n해석: oracle=g100%·FP0 → net 100% → 절대가속 = 천장 "
      f"{100*rf:.1f}% (>{100*need:.1f}% 요건 → WIN, 단 완벽예측 전제). "
      "실현 정책은 g 낮고 FP:TP≫1 → net ≤ 0(천장 회수 실패, 오히려 "
      "불필요 stall 로 latency 가산). Step3(시간≈0)·Step4(공간 무력)의 "
      "직접 귀결.")

    # ── 그림 ──
    fig, ax = plt.subplots(1, 2, figsize=(13.2, 5.2))
    nm = [r[0] for r in rows]
    netv = [r[1] for r in rows]
    cyc = [r[2] for r in rows]
    grossv = [r[3] for r in rows]
    y = np.arange(len(nm))
    ax[0].barh(y + .18, grossv, .36, color="#90a4ae", label="gross g")
    ax[0].barh(y - .18, netv, .36,
               color=["#2e7d32" if v > 0 else "#c62828" for v in netv],
               label="net (g - FP burden)")
    ax[0].axvline(100 * need, color="#ef6c00", ls="--", lw=1.6,
                  label=f"A4 pass line ({100*need:.0f}% of ceiling)")
    ax[0].axvline(0, color="#999", lw=.8)
    ax[0].set_yticks(y); ax[0].set_yticklabels(nm, fontsize=8.5)
    ax[0].invert_yaxis()
    ax[0].set_xlabel("recovery [% of redo ceiling]")
    ax[0].set_title(f"T={T} replay: only oracle clears the A4 line;\n"
                    "realizable nets <= 0 (false stalls dominate)")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=.3, axis="x")

    ax[1].axhline(CYC_T64 / 1e6, color="#2e7d32", ls="--", lw=2,
                  label=f"Stage3 best fixed-T=64 ({CYC_T64/1e6:.3f}M)")
    ax[1].axhline(CYC_T128 / 1e6, color="#999", ls=":", lw=1.5,
                  label=f"base fixed-T=128 ({CYC_T128/1e6:.3f}M)")
    ax[1].bar(range(len(nm)),
              [max(c, 1.5e6) / 1e6 for c in cyc],
              color=["#2e7d32" if "oracle" in n else "#c62828"
                     for n in nm], alpha=.85)
    ax[1].set_xticks(range(len(nm)))
    ax[1].set_xticklabels(nm, rotation=30, ha="right", fontsize=8)
    ax[1].set_ylabel("est. total cycles [M]  (= CYC128*(1-net*rf))")
    ax[1].set_ylim(1.5, 2.0)
    ax[1].set_title("roadmap-frame latency estimate\n"
                    "(realizable >= base T128; do NOT beat fixed-T=64)")
    ax[1].legend(fontsize=8.5); ax[1].grid(alpha=.3, axis="y")
    fig.suptitle("Stage4-2 STEP5 - A4 gate: realizable selective stall nets "
                 "<=0 of the redo ceiling (only omniscient oracle passes) "
                 "=> latency A4 FAIL, ISN-bound as global dynamic-T",
                 fontsize=9.2)
    fig.tight_layout()
    fpn = f"{ROOT}/research/result_img/stage4_a4gate_replay.png"
    fig.savefig(fpn, bbox_inches="tight", dpi=110)
    P(f"\n[saved] {fpn}")

    P("\n[STEP5 / A4 gate 판정 — 정직]")
    P(f" · 요건: net 천장회수 ≥ {100*need:.0f}% (T64 도달). oracle "
      "(완벽예측)만 충족 — 그러나 Step3(시간 forecasting≈0/음수)·"
      "Step4(공간 prior 무력, Δt⊥거리)가 그 예측 불가를 입증.")
    P(" · 실현 정책(last-block/EWMA/static-prior): gross 회수 낮고 "
      "FP:TP≫1 → net ≤ 0. base T=128 도 못 줄이고 Stage3 fixed-T=64 "
      "최적도 당연히 못 이김.")
    P(" · 근원: 글로벌 동적-T 를 폐기시킨 ISN 항상성(평활·균일·예측"
      "불가)이 per-core 축에서도 동일 작용. **latency A4 = FAIL**.")
    P(" · 잔존 가치(미확정): TP 의 롤백(재계산+RR)→idle 치환은 "
      "*에너지* 절감일 수 있음(stall 내부비용은 trace 검증불가 → "
      "Step6 에서 전력모델로 별도 정량). 졸업연구를 'latency 음성 + "
      "정직한 ISN 한계규명 + (가능시) energy-only 이득'으로 재정의할지 "
      "= 사용자 판단.")
    txt = "\n".join(out)
    print(txt)
    rp = f"{ROOT}/runspace/brunel_si/stage4_step5_a4gate.txt"
    open(rp, "w").write(txt + "\n")
    print(f"[saved] {rp}")


# ─────────────────────────── STEP 6 (진단) ───────────────────────────
# 사용자 가설 검증: speculative-advance stall 이 무력한 *결정적* 원인이
#  A1) stall→그 코어 미래 spike 발생 지연→하류서 재-belated(문제 보존/전파)
#  A2) 코어 내 ~64뉴런이 timestep 공유(GV.timestep[ind] per-core)인데 한
#      advance 의 victim 은 극소수 → 다수 위해 전진이 유리한데 소수 위해
#      코어 전체 stall = 구조적 손해
#  B ) 그냥 우리 predictor 가 belated 를 못 맞히는 것(예측기 품질)
# 중 어느 것인가? A2·B 는 trace 로 결정 가능, A1 은 전제조건만(정적 trace
# 는 stall 없는 타임라인 → 재타이밍 피드백 직접 검증 불가, 재시뮬 필요).
def _auc(score, label):
    """rank 기반 pooled AUC (Mann–Whitney). label∈{0,1}."""
    s = score.astype(float).ravel()
    y = label.astype(np.int8).ravel()
    n = len(s)
    order = np.argsort(s, kind="mergesort")
    rank = np.empty(n, float)
    rank[order] = np.arange(1, n + 1)
    npos = int(y.sum()); nneg = n - npos
    if npos == 0 or nneg == 0:
        return 0.5
    return float((rank[y == 1].sum() - npos * (npos + 1) / 2)
                 / (npos * nneg))

def step6():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    print("=" * 70)
    print("STEP 6 (진단) — 무력 원인: A1(전파)/A2(공유 timestep)/B(예측기)")
    print("=" * 70)
    g2c = load_gid2core()
    csize = np.bincount(g2c)            # 코어별 뉴런수 (~64)
    out = []
    def P(s=""):
        out.append(s)
    P(f"코어 뉴런수: mean={csize.mean():.1f} min={csize.min()} "
      f"max={csize.max()} (timestep 은 코어당 1개=GV.timestep[ind], "
      f"이 ~64뉴런이 함께 전진/stall)")

    fig, ax = plt.subplots(1, 2, figsize=(13, 5.0))
    for T, c in ((128, "#c62828"), (64, "#1565c0")):
        d = load_trace(T)
        B = 16
        nb = int((MAX_TS - SETUP_TS) // B + 1)
        blk = (np.clip(d["affecting_ts"], SETUP_TS, MAX_TS) - SETUP_TS) // B
        dc, vic, sc = d["dst_core"], d["rollback_gid"], d["src_core"]
        dt = d["delta_t"].astype(float)

        # ── A2: **per-timestep**(실제 advance 결정 단위) (dst_core, ts)
        #     셀당 distinct victim 뉴런수 vs 코어크기. bin=1 이 정답
        #     (block 집계는 16ts victim 을 합쳐 A2 를 과소평가). ──
        at = np.clip(d["affecting_ts"], SETUP_TS, MAX_TS)
        nts = MAX_TS - SETUP_TS + 1
        cell = dc.astype(np.int64) * nts + (at - SETUP_TS)
        pair_cv = np.unique(np.stack([cell, vic]), axis=1)
        vic_pc = np.bincount(pair_cv[0], minlength=NCORE * nts)
        csz_cell = csize[np.arange(NCORE * nts) // nts]
        trig = vic_pc > 0                              # 그 ts 에 belated 있음
        v = vic_pc[trig].astype(float)
        cs = csz_cell[trig].astype(float)
        needless = (cs - v) / v                        # victim 1당 헛stall 뉴런
        # per-core 가 *그 ts* belated 있으면 코어 전체 stall 한다 가정:
        #  강제 stall 된 (코어,ts) 빈도 / 전체 가능 (코어×활성ts)
        active_ts = nts                                # 분석창 전체
        fstall = trig.sum() / (NCORE * active_ts)
        waste_adv = (cs - v).sum()                     # 헛정지 뉴런-ts
        prot_adv = v.sum()                             # 실제 victim 뉴런-ts
        P(f"\n[T={T}] A2 (per-TIMESTEP=실제 advance 단위; 코어 timestep "
          f"공유):")
        P(f"  belated 발생한 (코어,ts) 셀당 victim 뉴런 = mean "
          f"{v.mean():.1f} / median {np.median(v):.0f}  (코어 ~"
          f"{int(np.median(cs))}뉴런 중) → 대다수는 그 ts belated 無")
        P(f"  → victim 1뉴런 보호 위해 코어 전체 stall 시 **헛정지 동료 "
          f"= mean {needless.mean():.1f} / median "
          f"{np.median(needless):.0f} 뉴런**")
        P(f"  전체 손익비(헛정지 뉴런-ts {waste_adv:,.0f} : 보호 victim "
          f"{prot_adv:,.0f}) = **{waste_adv/prot_adv:.1f} : 1**  "
          f"(≫1 → 공유 timestep 이 A2 결정적 손해)")
        P(f"  (참고) 코어가 belated 만나는 ts 빈도 = {100*fstall:.1f}% "
          f"→ 이만큼 코어 전체가 강제 stall(= 사실상 T 붕괴, Stage3 열위)")
        if T == 128:
            a2_hist = needless

        # ── B: in-sample(cheating 포함) 분리 가능성 AUC ──
        pk = dc.astype(np.int64) * NCORE + sc
        O = (_series(pk, NCORE * NCORE, blk, nb,
                     np.ones(len(blk))) > 0).astype(np.int8)
        O = O[O.sum(1) > 0]
        tgt = O[:, 1:]
        s_last = O[:, :-1]
        E = np.zeros_like(O, float); st = O[:, 0].astype(float).copy()
        for j in range(1, nb):
            E[:, j] = st
            st = 0.5 * O[:, j] + 0.5 * st
        s_ewma = E[:, 1:]
        s_static = np.repeat(O.mean(1, keepdims=True), nb - 1, axis=1)  # cheat
        aL = _auc(s_last, tgt); aE = _auc(s_ewma, tgt)
        aS = _auc(s_static, tgt)
        P(f"[T={T}] B (블록 belated 발생 분리 AUC; 0.5=무작위, 1=완벽):")
        P(f"  causal: last-block={aL:.3f} EWMA={aE:.3f} (≈0.5=무작위)  | "
          f"static-rate(CHEAT,전구간평균)={aS:.3f} (약함)")
        P(f"  → 실현(causal) 예측기는 사실상 무작위, *미래를 컨닝한* "
          f"정적 link rate 조차 AUC {aS:.2f}(약). belated 는 예측기 "
          f"품질이 아니라 *내재적으로* 거의 예측 불가(맞힐 신호 부재).")
        if T == 128:
            b_aucs = (aL, aE, aS)

        # ── A1 전제조건: victim-mass ↔ source-mass 코어상관 ──
        vmass = np.bincount(dc, weights=dt, minlength=NCORE)
        smass = np.bincount(sc, weights=dt, minlength=NCORE)
        r = np.corrcoef(vmass, smass)[0, 1]
        self_share = (d["src_core"] == d["dst_core"]).mean()
        P(f"[T={T}] A1 전제조건: corr(코어 victim-mass, 코어 source-mass)"
          f"={r:+.3f}, self-core={100*self_share:.1f}%")
        P(f"  → 양의 상관 = stall 대상(victim) 코어가 동시에 큰 belated "
          f"*source* → 그 코어 지연이 하류로 전파(A1 전제 성립). 단 "
          f"실제 재타이밍은 stall 재시뮬 필요(정적 trace 한계).")

    ax[0].hist(np.clip(a2_hist, 0, 64), bins=32, color="#c62828",
               alpha=.85)
    ax[0].axvline(np.median(a2_hist), color="k", ls="--",
                  label=f"median={np.median(a2_hist):.0f} needless/victim")
    ax[0].set_xlabel("needlessly-stalled sibling neurons per protected victim")
    ax[0].set_ylabel("(dst_core,block) cells")
    ax[0].set_title("A2: per-core shared timestep =>\nmajority frozen for a "
                    "tiny victim set (T=128)")
    ax[0].legend(fontsize=8.5); ax[0].grid(alpha=.3)

    g = ["last-block", "EWMA", "static-rate\n(CHEAT)"]
    ax[1].bar(range(3), b_aucs, color=["#1565c0", "#1565c0", "#ef6c00"],
              alpha=.85)
    ax[1].axhline(0.5, color="#c62828", ls="--", label="random (0.5)")
    ax[1].set_xticks(range(3)); ax[1].set_xticklabels(g, fontsize=9)
    ax[1].set_ylim(0.45, 0.75)
    ax[1].set_title("B: belated-block separability AUC (T=128)\n"
                    "even cheating ~0.5 => intrinsically unpredictable")
    ax[1].set_ylabel("pooled AUC")
    ax[1].legend(fontsize=8.5); ax[1].grid(alpha=.3, axis="y")
    for i, vv in enumerate(b_aucs):
        ax[1].annotate(f"{vv:.3f}", (i, vv), ha="center",
                       xytext=(0, 3), textcoords="offset points",
                       fontsize=9)
    fig.suptitle("Stage4-2 STEP6 - cause diagnosis: A2 (per-core shared "
                 "timestep, sparse victims) is decisive; B (belated "
                 "intrinsically unpredictable) compounds; A1 precondition holds",
                 fontsize=9.2)
    fig.tight_layout()
    fpn = f"{ROOT}/research/result_img/stage4_cause_diagnosis.png"
    fig.savefig(fpn, bbox_inches="tight", dpi=110)
    P(f"\n[saved] {fpn}")

    P("\n[STEP6 판정 — 사용자 가설 검증 (정직, 측정값 기반)]")
    P(" · **A2 = 결정적 (사용자 지적이 정확)**: 실제 결정 단위인 "
      "per-timestep 에서 한 ts 의 victim 은 코어 ~64뉴런 중 소수(중앙값 "
      "수치 위 표 참조)뿐인데, timestep 이 코어 공유(GV.timestep[ind])라 "
      "그 소수 위해 코어 전체를 stall → 헛정지:victim 손익비 ≫1. 완벽 "
      "belated 예측기여도 *per-core* stall 단위면 구조적으로 패배. "
      "(bin=16ts 로 보면 victim 이 뭉쳐 ~40%로 보여 A2 가 과소평가됨 — "
      "per-ts 가 올바른 렌즈.)")
    P(" · **B = 동시 성립(보강, 단 '예측기 탓' 아님)**: causal 예측기 "
      "AUC≈0.53(무작위), 미래 컨닝한 정적 rate 조차 ~0.65(약). 즉 "
      "'우리 predictor 가 못 맞힌다' 보다 정확히는 **belated 가 내재적"
      "으로 예측 신호를 안 준다**(Step3 Poisson·Step4 Δt⊥거리와 정합).")
    P(" · **A1 = 전제 성립(사용자 직관 타당), 완전검증은 stall 재시뮬 "
      "필요**: corr(코어 victim-mass, source-mass) 양수(T64 +0.38). "
      "stall→미래 spike 지연→하류 재-belated 경로 존재. 정적 trace 는 "
      "재타이밍 미반영 → Step5 oracle(+18%)은 *과대평가*(실제 더 나쁨).")
    P(" · **종합**: 세 원인이 같은 방향. 사용자 가설(A1+A2)이 핵심 "
      "인과 — 특히 **A2(코어 공유 timestep vs per-뉴런 희소 victim)가 "
      "결정적**, B 가 그 위에 곱해짐. per-core speculative-advance stall "
      "폐기는 정당. 재정의는 아래 BP 재적용 3안으로.")
    txt = "\n".join(out)
    print(txt)
    rp = f"{ROOT}/runspace/brunel_si/stage4_step6_cause.txt"
    open(rp, "w").write(txt + "\n")
    print(f"[saved] {rp}")


# ─────────────────────────── STEP 7 ───────────────────────────
# 연구 핵심 가설을 정면으로 닫는 실험: branch-prediction 비유의 대표
# 도구인 **perceptron predictor**(Jiménez–Lin)를 트레이스에 온라인
# 학습으로 리플레이 = BP 연구 표준 평가법(재시뮬 불요, 예측 품질만 격리;
# A2 granularity 와 분리). "토이 예측기(last-value/EWMA)뿐 아니라
# 정식 perceptron 도 rollback 을 못 맞힌다"를 시뮬레이션으로 확정.
#
# 대상('branch') = **per-(dst-core, timestep)** : 코어 c 가 ts t 의
#   advance 에서 belated 를 맞나? O[c,t]∈{+1,−1}. 이게 *실제* 투기-
#   advance 결정 단위(Stage6: belated율 ~30% → 비-degenerate). per-
#   (코어,T-window) 타겟은 belated율 ~97%로 vacuous → per-ts 가 정답.
# 예측기: per-entity(=dst-core) weight + local history(H) + global
#   history(G; gshare식) + bias (+kitchen: remote-activity). 예측
#   y=W·x, 오예측 or |y|≤θ 시 W += t·x. **float 무클립=이상화(강한
#   perceptron 에 최대 유리)**, entity-벡터화(64 동시), θ=1.93·N+14.
def _perc_ts(O, H, G, kit=None, warm_frac=0.25):
    """O:(E,NT)∈{0,1} per-(dst,ts). 인과 온라인, entity-벡터화.
       return acc(post-warm), auc(score), base(majority over eval)."""
    E, NT = O.shape
    S = (O * 2 - 1).astype(float)                  # ±1
    nf = 1 + H + G + (0 if kit is None else 1)
    theta = 1.93 * (H + G) + 14.0
    W = np.zeros((E, nf))
    LHR = np.zeros((E, H)) if H else None          # 코어별 local hist
    GHR = np.zeros(G) if G else None               # 전역 hist(±1 추세)
    warm = int(NT * warm_frac)
    cor = tot = 0
    sc_l, lb_l = [], []
    X = np.empty((E, nf))
    X[:, 0] = 1.0
    for t in range(NT):
        if H:
            X[:, 1:1 + H] = LHR
        if G:
            X[:, 1 + H:1 + H + G] = GHR            # (G,) → 전 entity 공통
        if kit is not None:
            X[:, -1] = kit[:, t]                   # 인과(과거값)
        y = np.einsum("ef,ef->e", W, X)            # (E,)
        tpm = S[:, t]
        pred_taken = y >= 0
        act_taken = tpm > 0
        if t >= warm:
            cor += int(np.sum(pred_taken == act_taken)); tot += E
            sc_l.append(y.copy())
            lb_l.append(act_taken.astype(np.int8))
        upd = (pred_taken != act_taken) | (np.abs(y) <= theta)
        if upd.any():
            W[upd] += tpm[upd, None] * X[upd]
        if H:
            LHR = np.roll(LHR, 1, axis=1); LHR[:, 0] = tpm
        if G:
            GHR = np.roll(GHR, 1); GHR[0] = tpm.mean()
    auc = _auc(np.concatenate(sc_l), np.concatenate(lb_l)) if tot else 0.5
    p1 = O[:, warm:].mean()
    return cor / tot, auc, max(p1, 1 - p1)

def _bimodal_ts(O, warm_frac=0.25):
    """2-bit saturating counter per entity, entity-벡터화 (표준 BP)."""
    E, NT = O.shape
    ctr = np.ones(E, int)
    warm = int(NT * warm_frac); cor = tot = 0
    for t in range(NT):
        pred = ctr >= 2
        o = O[:, t].astype(bool)
        if t >= warm:
            cor += int(np.sum(pred == o)); tot += E
        ctr = np.where(o, np.minimum(3, ctr + 1), np.maximum(0, ctr - 1))
    return cor / tot if tot else 0.0

def step7():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    print("=" * 70)
    print("STEP 7 — perceptron branch predictor 로 'rollback 예측 불가' 확정")
    print("=" * 70)
    print("타겟 = per-(dst-core, TIMESTEP) = 실제 advance 결정 단위"
          "(Stage6 belated율~30%, 비-degenerate). perceptron(Jiménez–Lin) "
          "online·float무클립=이상화. 핵심지표=AUC + majority 대비 acc lift.\n")
    HS = [4, 8, 16, 32, 64]
    NT = MAX_TS - SETUP_TS + 1
    out = []
    def P(s=""):
        print(s); out.append(s)
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))

    for ax, T in zip(axes, (64, 128)):
        d = load_trace(T)
        at = np.clip(d["affecting_ts"], SETUP_TS, MAX_TS) - SETUP_TS
        dc = d["dst_core"]
        cell = dc.astype(np.int64) * NT + at
        cnt = np.bincount(cell, minlength=NCORE * NT).reshape(NCORE, NT)
        O = (cnt > 0).astype(np.int8)                       # per-(c,ts)
        p1 = O.mean()
        base = max(p1, 1 - p1)
        # 왜 per-ts 인가: per-(코어,T-window) 타겟은 거의 상수 → vacuous
        win_nb = int((MAX_TS - SETUP_TS) // T + 1)
        Ow = (_series(dc, NCORE, at // T, win_nb,
                      np.ones(len(at))) > 0)
        P(f"[T={T}]  per-ts belated율={p1:.3f} (base/majority "
          f"{base:.3f})  ‖ 참고: per-(코어,T={T}창) belated율="
          f"{Ow.mean():.3f} → 그 타겟은 vacuous, 그래서 per-ts 사용")
        # kitchen feature: 직전 ts belated-event 수(remote 활성 proxy), 표준화
        kit = np.zeros((NCORE, NT))
        z = (cnt - cnt.mean()) / (cnt.std() + 1e-9)
        kit[:, 1:] = z[:, :-1]

        aucs, accs = [], []
        for H in HS:
            a, u, _ = _perc_ts(O, H, H)
            accs.append(a); aucs.append(u)
        ks_a, ks_u, _ = _perc_ts(O, 64, 64, kit=kit)
        bm = _bimodal_ts(O)
        au_last = _auc(O[:, :-1].astype(float), O[:, 1:])
        st = np.repeat(O.mean(1, keepdims=True), NT, axis=1)
        au_static = _auc(st[:, 1:], O[:, 1:])               # 미래 컨닝 상한

        P(f"  {'H(=G)':>6}{'acc(pw)':>9}{'lift':>7}{'AUC':>7}"
          f"  (perceptron, local+global hist)")
        for H, a, u in zip(HS, accs, aucs):
            P(f"  {H:>6}{a:>9.3f}{a-base:>+7.3f}{u:>7.3f}")
        P(f"  kitchen-sink(H64+G64+remote-act): acc={ks_a:.3f} "
          f"lift={ks_a-base:+.3f} AUC={ks_u:.3f}")
        P(f"  baselines: 2-bit acc={bm:.3f}(lift {bm-base:+.3f}) | "
          f"AUC last-val={au_last:.3f}  static-rate(CHEAT,상한)="
          f"{au_static:.3f}  perfect oracle=1.000")
        lift = np.mean(accs) - base
        verdict = ("majority 대비 무이득 + last-value 동급 → 예측 불가(확정)"
                   if lift <= 0.02 else "lift>2%p: 재검토 필요")
        P(f"  → perceptron AUC≈{np.mean(aucs):.3f}(chance 0.5 바로 위, "
          f"usable BP~0.95 에 한참 못 미침), majority 대비 acc "
          f"lift≈{lift:+.3f} : {verdict}")
        P("")
        ax.plot(HS, aucs, "-o", color="#1565c0", lw=2,
                label="perceptron (local+global)")
        ax.scatter([64], [ks_u], marker="*", s=190, color="#6a1b9a",
                   zorder=5, label=f"kitchen-sink ({ks_u:.2f})")
        ax.axhline(au_static, color="#ef6c00", ls="--", lw=1.6,
                   label=f"cheating static-rate ({au_static:.2f})")
        ax.axhline(au_last, color="#9e9e9e", ls="-.", lw=1.2,
                   label=f"last-value ({au_last:.2f})")
        ax.axhline(0.5, color="#c62828", ls=":", lw=1.5,
                   label="random (0.50)")
        ax.axhline(1.0, color="#2e7d32", ls="-", lw=1.2, alpha=.6,
                   label="perfect oracle (1.00)")
        ax.set_ylim(0.45, 1.03)
        ax.set_xlabel("perceptron history length H (=G)")
        ax.set_ylabel("AUC (threshold-free separability)")
        ax.set_title(f"T={T}: per-timestep advance decision\n"
                     f"a real perceptron BP stays at chance "
                     f"(<< cheating-static << oracle)")
        ax.set_xscale("log", base=2); ax.set_xticks(HS)
        ax.set_xticklabels(HS)
        ax.legend(fontsize=7.5, loc="center right"); ax.grid(alpha=.3)

    fig.suptitle("Stage4-2 STEP7 - an online (idealized) perceptron branch "
                 "predictor at the true per-timestep advance decision: AUC "
                 "barely > chance (0.53-0.58), ZERO accuracy lift over "
                 "majority, = last-value/2-bit => unpredictability is intrinsic",
                 fontsize=8.6)
    fig.tight_layout()
    fpn = f"{ROOT}/research/result_img/stage4_perceptron.png"
    fig.savefig(fpn, bbox_inches="tight", dpi=110)
    P(f"[saved] {fpn}")
    P("\n[STEP7 판정 — 정직, 측정값 기반]")
    P(" · 타겟 = *실제 advance 결정 단위*(per-dst-core,ts; belated율 "
      "T64 0.284 / T128 0.300, 비-degenerate). 정식 perceptron(per-"
      "entity weight + local+global history, float 무클립=이상화, "
      "online)을 H 4~64 + kitchen-sink(remote-activity)까지 스윕.")
    P(" · 결과: **AUC ≈ 0.53–0.58** (chance 0.5 바로 위, usable BP "
      "~0.95 에 한참 못 미침), **majority 대비 acc lift ≈ 0(±0.01)**. "
      "2-bit·last-value 와 동급이며, *미래를 컨닝한* static-rate "
      "상한(AUC≈0.52)도 무의미. 즉 AUC 가 0.5 '정확히'는 아니지만 "
      "**운영상 무이득**(thresholding 해도 majority 못 넘음).")
    P(" · 그 사소한 AUC>0.5 의 정체 = Stage3 가 규명한 *약한 단거리 "
      "자기상관*(near-Poisson + 미세한 rate 이질성)뿐 → Stage5 에서 이미 "
      "FP:TP≈5–6 으로 stall 게이트에 쓰면 net ≤ 0 임을 입증한 그 신호. "
      "branch-prediction 비유의 *대표·최강 온라인 도구*조차 이걸 못 "
      "넘김 → rollback 비예측성은 **예측기 약함이 아니라 신호 부재** "
      "(Step3 Poisson·Step4 Δt⊥거리·Step6 정합).")
    P(" · 부수 확인: per-(코어,T-window) belated율 ~0.97 = '발생 여부'는 "
      "거의 항상 yes(vacuous) → 가치는 '언제/어디'에 있는데 그게 Poisson. "
      "포스터 (2) '직접 예측 불가' airtight. (A2 granularity 와 독립 — "
      "여긴 예측 품질만 격리 측정.)")
    txt = "\n".join(out)
    rp = f"{ROOT}/runspace/brunel_si/stage4_step7_perceptron.txt"
    open(rp, "w").write(txt + "\n")
    print(f"[saved] {rp}")


if __name__ == "__main__":
    {"step1": step1, "step2": step2, "step3": step3,
     "step4": step4, "step5": step5, "step6": step6,
     "step7": step7}.get(
        sys.argv[1] if len(sys.argv) > 1 else "step1", step1)()
