# Research Poster Outline — *A Limits Study of Speculative SNN Simulation*

> **Purpose of this file.** This is a complete, self-contained English outline
> for a research poster. It is intentionally verbose and panel-structured so
> that a poster-generating LLM (or designer) can lay it out directly without
> further context. Every numeric claim is final and verified against the
> project's durable analysis artifacts. Do **not** invent additional numbers;
> use only what is here.

---

## POSTER TITLE

**Primary title (use this):**

> **Rollback Predictability: A Limits Study of Speculative SNN Simulation**

**Sub-title line:**

> *Profiling the rollback overhead of an optimistic multicore SNN accelerator, and testing every path to predict or balance it away.*

**Alternate titles** (do not use as primary; list only if a secondary line is wanted):
- *A Limits Study of Speculative SNN Simulation.* (bare form)
- *On the Limits of Predicting Rollback in Speculative SNN Simulation.*

**Authors / affiliation:** _(placeholder — fill in)_

---

## SUGGESTED POSTER LAYOUT (directive for the generating LLM/designer)

- Format: A0, **3 columns**, portrait or landscape.
- **Column 1:** §1 Background → §2 NeuroSync → §3 Opportunity / Motivation.
- **Column 2 (visual centerpiece, give it the most area):** §4 *This Work* —
  the **0-1-2-3 elimination spine**. The elimination-tree diagram is the anchor
  graphic.
- **Column 3:** §4 Synthesis (root cause) → §5 Conclusion & Future Work →
  Take-home banner.
- Recurring visual motifs:
  - a **"✗ CLOSED"** stamp on each of paths (1), (2), (3);
  - the **U-curve** (fixed-T total cycles);
  - the **elimination-tree** schematic;
  - the **ISN smoothing-cascade** arrow chain `CV 0.95 → 0.40 → 0.16`.
- Use one accent color for *closed / negative* results and a second, distinct
  color for the *constructive / future-work* redirections.
- Every numeric claim should appear as a **bold callout**, not buried in prose.
- Figure files live under `result_img/` (paths given per section).

---

## SECTION 1 — Background: Brain Simulators & SNN Accelerators

**Goal of panel:** orient a general computer-architecture audience.

- **Spiking neural networks (SNNs)** model the brain as neurons that exchange
  discrete *spikes* across synapses, each with a transmission delay.
  Large-scale SNN simulation is a core tool for both neuroscience and the
  design of neuromorphic hardware.
- Simulation is **compute- and communication-heavy**: millions of
  time-stepped neuron updates plus delayed synaptic events. Pure-software
  simulators are slow, motivating dedicated **brain-simulation accelerators**
  that parallelize the network across many cores.
- The fundamental difficulty is **parallel causality**: a spike produced on
  one core may need to affect an *earlier* timestep on another core (because of
  synaptic + network-on-chip delay). Two classic strategies:
  - **Conservative:** globally synchronize every timestep — always correct,
    but slow (no overlap across cores).
  - **Optimistic / speculative (Time-Warp style):** let cores run ahead and
    **roll back** when a late ("belated") spike violates causality.
- Speculation only pays off **if rollbacks are rare or predictable.** That
  premise is exactly what this work puts to the test.

*Suggested visual:* a small schematic — neurons → spikes → cores on a NoC; a
cartoon of a "belated spike crossing into a core's already-computed past →
rollback."

---

## SECTION 2 — NeuroSync: A Speculative Multicore SNN Simulator

**Goal of panel:** define the concrete system under study.

- **NeuroSync** (HPCA'22-lineage) is a cycle-level model of speculative
  multicore brain-simulation hardware. Configuration in this study:
  - **64 cores** = 4 chips × 16 cores, on an **8×8 NoC mesh**;
  - neurons partitioned across cores by **Metis** (~64 neurons/core);
  - workload **Brunel SI** (sustained irregular regime): 4000 + 100 Poisson
    = **4100 neurons**; **1971-timestep** analysis window.
- **Speculation mechanism:**
  - a global **sync period `T`**;
  - within a period each core **speculatively advances** its timestep;
  - state is **checkpointed** at every sync boundary;
  - a **belated spike** — a remote spike whose target timestep the receiving
    core has *already passed* (`gen_timestep < GV.timestep`) — forces a
    **rollback** to the checkpoint and a **recompute**.
- **The `T` trade-off (a U-curve):**
  - small `T` → frequent **sync/checkpoint overhead**;
  - large `T` → more and **deeper rollbacks**;
  - there is a single static optimum.
- **Branch-prediction analogy:** speculative execution + a
  misprediction-recovery penalty. The natural question — *can we predict the
  causality violation and avoid the penalty, like a branch predictor?*

*Suggested visual:* NeuroSync core/NoC block diagram + a `T`-window timeline:
speculate → belated spike arrives → rollback → recompute.

---

## SECTION 3 — Opportunity: Rollback as an Acceleration Target (Motivation)

**Goal of panel:** state the hypothesis and why it was worth pursuing.

- **Hypothesis:** rollback is *wasted latency*; if it could be predicted or
  avoided, those cycles are reclaimed as speedup.
- **Profiling.** An **additive, non-invasive `redo_cyc` instrumentation** was
  added to the rollback path (verified: cycle counts and spike output remain
  **byte-identical** — the probe does not perturb the simulation). It shows:

  > **Rollback consumes ≈ 10.4 % of all cycles at the optimal `T=64`, rising to
  > 18.1 % at `T=128`.**

  Non-trivial — a worthwhile acceleration target.
- **Research question:**

  > *Can rollback be predicted (or its overhead balanced away) to convert its
  > latency loss into speedup?*

- This is a classic speculative-architecture problem: **predict the
  misprediction** — a "branch predictor" for causality violations.

*Key callout (large):* **"Rollback ≈ 10–18 % of all cycles — the acceleration
target."**

---

## SECTION 4 — This Work: Closing the Solution Space (the 0-1-2-3 spine)

**Goal of panel (the core of the poster):** present the research as an
**exhaustive elimination** of the acceleration solution space — a deliberate,
complete limits study, *not* a single failed idea.

**Framing statement (display prominently):**

> To beat rollback-induced latency there are exactly **three logical paths**:
> **(A-proxy)** predict rollback from an intuitive *surrogate* signal;
> **(A-direct)** predict the *direct cause* — the belated spike — itself;
> **(B-balance)** don't predict at all — *balance* rollback against idle by
> varying `T`.
> **We close all three experimentally — and they fail for one common reason.**

**Methodology box (place near the top of this section):**

- **Trace-driven, zero re-simulation.** Inputs: existing `rollback_events.dat`
  (`T=64,128`), `redo_cyc.dat`, and the Metis neuron→core mapping.
- Tooling: `stage4_predict.py` (steps 1–7) — oracle ceilings + a predictability
  decomposition (state granularity, temporal autocorrelation, NoC geometry,
  offline policy replay, causal diagnosis, **online perceptron-BP replay**).
- **Unit discipline enforced:** per-core-summed `redo_cyc` and the
  single-(critical-)core total are never mixed (a unit-mixing bug was caught
  and corrected during the study — reported honestly).

### The elimination-tree diagram (anchor figure — render as the centerpiece)

```
            Beat rollback-induced latency?
                        │
 0) PROFILE: rollback = 10.4% of cycles @best T=64
             (18.1% @T=128)            → worth attacking
                        │
   ┌────────────────────┴───────────────────────────┐
   │ (A) Predict & avoid rollback                    │ (B) No prediction:
   │     (needs a predictable signal)                │     balance rollback↔idle
   │                                                 │     via dynamic T
   │  1) proxy = network activity                    │
   │       → R²≈0.09           ✗ unusable            │  → omniscient oracle
   │  2) direct = belated spike itself               │    only +2–4%   ✗
   │       → AUC≈0.53          ✗ unpredictable        │
   │       └ even a PERFECT predictor loses 7.5:1    │
   │         (per-core shared timestep)  ✗           │
   └────────────────────┬───────────────────────────┘
                        │
   ALL THREE PATHS CLOSED → common root cause =
   ISN homeostasis (workload-intrinsic, not engineering)
```

### (0) Profile — how big is the target?

- The `redo_cyc` instrumentation establishes the ceiling any acceleration
  could *possibly* reclaim: **10.4 % of cycles @ `T=64`; 18.1 % @ `T=128`.**
- This is the yardstick every later result is measured against.

### (1) Proxy path — network activity is **not** a usable predictor ✗

- *Intuition:* more spiking → more rollback. *Reality:* the link is very weak.
- **Pearson r = 0.29, R² ≈ 0.09** — network activity explains only ~9 % of
  rollback variance; there is a large **activity-independent rollback floor**.
- The underlying pattern is a **smoothing cascade**:

  > **spike CV 0.95 → rollback CV 0.40 → cycle CV 0.16**

  variance is progressively *laundered out* as the signal propagates.
- **Conclusion:** activity carries almost no predictive signal for rollback —
  the intuitive surrogate path is closed.
- *Figure:* `result_img/stage2_brunel_si_rollback_vs_spike_scatter_T16_v1.png`
  — caption: *Rollback intensity vs spike count: weak, scattered (R²≈0.09),
  large activity-independent floor.*

### (2) Direct path — the belated spike is **intrinsically unpredictable** ✗

Predict the actual cause directly: *"will a belated spike hit this core/link
in the current window?"*

- **Temporal:** within-pair *demeaned* autocorrelation ≈ 0; a last-value
  predictor scores **R² ≈ −0.9** (worse than predicting the mean). The
  per-link rollback process is effectively **Poisson** at the decision
  timescale.
- **Spatial:** rollback distance **Δt is orthogonal to NoC geometry** —
  **corr(hop, Δt) = −0.007**, inter-chip ≈ intra-chip, and **Δt ≈ T/2**
  (set by the sync-window position, *not* by transmission distance).
- **Separability:** classifying "belated vs not" reaches only
  **AUC ≈ 0.53 (causal)**; even a *future-cheating* static-rate predictor
  reaches only **0.65**.
- **A real perceptron branch predictor also fails (the canonical BP,
  explicitly tested):** an *idealized* online perceptron (per-core weights +
  local + global history, swept H = 4–64, plus a remote-activity feature),
  evaluated at the **true per-timestep advance decision** (belated rate
  ≈ 0.28–0.30, non-degenerate), reaches only **AUC ≈ 0.53–0.58 with ZERO
  accuracy lift over the trivial majority** — statistically equal to
  2-bit / last-value and below even a future-cheating static-rate predictor,
  and nowhere near a usable predictor (~0.95). The strongest standard online
  predictor extracts nothing → the unpredictability is **intrinsic, not a
  weak-predictor artifact.**
- **Embodiment — the per-core predictive-stall (the "A4 gate"):** offline
  replay of realizable predictors (last-block / EWMA / static-prior) yields a
  **net of −68 % to −344 % of the ceiling**, with **FP:TP ≈ 5–6** (the
  predictor is wrong 84 %+ of the times it fires). The pass line is **+29 %**.
  **Only the omniscient oracle passes.**
- **Causal diagnosis — why even a *perfect* predictor fails:**
  - the 64 neurons of a core **share one timestep counter**;
  - at any given timestep only **~7.5 of 64** neurons are belated-victims;
  - stalling the whole core to protect that minority costs **7.5 : 1**;
  - a core meets a belated spike at **~30 % of all timesteps** (so a per-core
    stall gate ≈ a collapse of `T`);
  - stalling also delays the core's *own* future spikes (a feedback path;
    victim↔source mass correlation **+0.38 @T=64**), so even the static-trace
    oracle's "+18 %" is **optimistic**.
- **Conclusion:** this is **not** a weak-predictor artifact — *the predictive
  signal does not exist*. The direct path is closed.
- *Figures:*
  - `result_img/stage4_temporal_autocorr.png` — *demeaned ACF≈0, predictor
    R²<0: rollback is ~Poisson in time.*
  - `result_img/stage4_horizon_ceiling.png` — *Δt ⊥ NoC geometry; a depth cap
    is just a re-parameterized T.*
  - `result_img/stage4_a4gate_replay.png` — *realizable selective stall nets
    ≤ 0; only the omniscient oracle clears the +29 % line.*
  - `result_img/stage4_cause_diagnosis.png` — *per-core shared timestep ⇒
    7.5:1 structural loss; belated separability AUC≈0.5.*
  - `result_img/stage4_perceptron.png` — *an idealized online perceptron BP
    stays at chance (AUC 0.53–0.58, zero lift) across the whole design
    space — far below cheating-static and the perfect oracle.*

### (3) Balancing path — prediction-free dynamic `T` has a **negligible ceiling** ✗

Give up prediction; just trade rollback against idle by varying `T` per block.

- **Fixed-`T` U-curve:** `T=1` 9.89 M, `T=8` 2.60 M, **`T=64` 1.808 M (min)**,
  `T=128` 1.909 M, `T=16` ≈ 2.09 M (**+15.5 % worse than `T=64`**), `T=256`
  **pathological** (rollback explosion → run killed).
- **Omniscient Oracle-A** — per-block *free* `T` switching, zero switch cost —
  beats the best fixed `T` by only **+1.99 %**, saturating at **~4 %** even
  with finer block granularity.
- **Conclusion:** dynamic `T` cannot meaningfully beat the *static* optimum
  `T=64`. The prediction-free balancing path is closed.
- *Figures:*
  - `result_img/stage3_fixedT_total_cycles_with_T256.png` — *the U-curve, with
    the pathological T=256 point.*
  - `result_img/stage3_oracleA_only_comparison_T256.png` — *even an omniscient
    per-block oracle is only +1.99 % over the best fixed T.*

### Synthesis — one root cause (highlight box)

> All three paths fail for the **same reason: inhibition-stabilized-network
> (ISN) homeostasis.** Recurrent inhibition absorbs input fluctuation and
> *launders* the spike→rollback→cycle variance into a process that is
> **temporally white, spatially uniform, and prediction-resistant.**
> **The limit of speculation here is set by the workload's statistical
> structure, not by engineering effort.** The only effective control left is
> the **static optimal sync period (`T=64`).**

---

## SECTION 5 — Conclusion & Future Work

### Conclusion

- **First systematic mapping of the *predictability boundary* of speculative
  SNN simulation:** proxy-prediction, direct-prediction, and prediction-free
  balancing are *all* closed, with a single mechanistic root cause.
- **Honest engineering takeaway:** simply *picking the static optimal `T`*
  (`16 → 64` alone is **+15.5 %**) is the real lever; dynamic or predictive
  rollback control is **not worthwhile** for ISN-homeostatic workloads.

### Contributions (box, C1–C4)

- **C1 — Methodology:** a reusable, **zero-re-simulation** framework that
  decomposes speculation overhead into *oracle ceilings* + *temporal/spatial
  predictability* + *offline policy replay*.
- **C2 — Mechanistic negative result:** *ISN homeostasis ⇒ smoothing cascade ⇒
  prediction-resistant rollback* — a finding about a **workload class**, not a
  single failed idea.
- **C3 — Architectural insight:** a **granularity mismatch** (per-core shared
  timestep vs per-neuron sparse victims, **7.5 : 1**) defeats *even a perfect*
  belated-spike predictor — independent of prediction quality.
- **C4 — Design guidance:** a principled redirection — **predict the
  *predictable*, not belatedness.**

### Future Work — "predict the predictable" (three constructive directions)

1. **Per-link silence prediction → speculative sync/checkpoint elision.**
   Communication *sparsity* (Metis locality; self-core traffic only ~1.6 %)
   *is* predictable from local + remote spike history. Skip the
   sync/checkpoint handshake on predicted-silent links to safely harvest the
   low-sync benefit of large `T`; a misprediction simply falls back to the
   existing rollback. Net gain ≈ f(silence fraction × predictor accuracy);
   **verifiable with zero re-simulation** from the clean spike output +
   connectivity.
2. **Topology-guaranteed safe speculation window.** The NoC minimum transit
   latency is a **deterministic lower bound**: a spike from K hops away (or
   inter-chip) physically *cannot* arrive before its transit time, so a core
   can advance that far with **zero rollback risk and zero misprediction by
   construction** (a proof, not a prediction).
3. **Rollback-scope / Δt prediction → cheap targeted recovery.** Occurrence is
   unpredictable, but Δt is **tight and stationary** and victims are **sparse
   (~7 / 64)**. Fine-checkpoint only the belated-prone minority to cut the
   *recovery cost (and energy) per rollback* — optimize the recovery instead of
   predicting the event.
- **Open axes:** the **energy** trade-off (stall idle vs rollback
  recompute + recovery) is not yet quantified; **generality** on
  less-homeostatic / bursty workloads remains to be tested.

---

## TAKE-HOME MESSAGE (large boxed banner — center or bottom)

> **In speculative SNN simulation, the limit of speculation is set by the
> workload, not by the engineer.** Inhibition-stabilized homeostasis makes
> rollback fundamentally unpredictable. We close all three acceleration paths,
> identify the single root cause, and show the only lever is the static optimal
> sync period. **The negative result *is* the contribution — and it points to
> what to predict instead.**

---

## KEY-NUMBERS QUICK TABLE (for an at-a-glance panel)

| Item | Value |
|---|---|
| Cores / mesh / neurons | 64 (4×16) / 8×8 NoC / 4100 (Brunel SI) |
| Rollback cycle share | **10.4 % @ T=64**, **18.1 % @ T=128** |
| Activity ↔ rollback | r = 0.29, **R² ≈ 0.09** |
| Smoothing cascade (CV) | spike **0.95** → rollback **0.40** → cycle **0.16** |
| Belated predictability | demeaned ACF ≈ 0, R²₍lastval₎ ≈ −0.9, **AUC ≈ 0.53** |
| Perceptron BP (idealized, online) | **AUC 0.53–0.58, 0 lift over majority** (= 2-bit/last-value) |
| Per-core stall replay | net **−68 … −344 %**, FP:TP ≈ 5–6, only oracle passes |
| Granularity loss | **7.5 : 1** (shared timestep vs ~7.5/64 victims) |
| Fixed-T optimum | **T=64 = 1.808 M cyc**; T=16 +15.5 %; T=256 pathological |
| Dynamic-T oracle ceiling | **+1.99 %** (saturates ~4 %) |
| Root cause | **ISN homeostasis** (workload-intrinsic) |

---

## FIGURE INVENTORY (file → suggested caption)

| File (`result_img/`) | Poster use | Caption |
|---|---|---|
| `stage2_brunel_si_rollback_vs_spike_scatter_T16_v1.png` | §4(1) | Activity↔rollback: weak, scattered (R²≈0.09); large activity-independent floor. |
| `stage3_fixedT_total_cycles_with_T256.png` | §4(3) | Fixed-T U-curve; T=64 optimal; T=256 pathological. |
| `stage3_oracleA_only_comparison_T256.png` | §4(3) | Omniscient per-block Oracle-A only +1.99 % over best fixed T. |
| `stage4_temporal_autocorr.png` | §4(2) | Demeaned ACF≈0, predictor R²<0 → rollback ~Poisson in time. |
| `stage4_horizon_ceiling.png` | §4(2) | Δt ⊥ NoC geometry; depth cap = re-parameterized T. |
| `stage4_a4gate_replay.png` | §4(2) | Realizable selective stall nets ≤ 0; only oracle clears +29 %. |
| `stage4_cause_diagnosis.png` | §4(2) | Per-core shared timestep ⇒ 7.5:1 loss; belated AUC≈0.5. |
| `stage4_perceptron.png` | §4(2) | Idealized online perceptron BP stays at chance (AUC 0.53–0.58, 0 lift) << cheating-static << oracle. |
| `stage4_granularity_concentration.png` | §4(2) supporting | Predictor-state granularity: per-src-core is the right unit. |

> Provenance (for fact-checking, not for the poster body): all figures and
> numbers are reproduced by `stage4_predict.py` (steps 1–7, incl. the online
> perceptron-BP replay) and the Stage-3 sweep; durable single-source narrative
> in `STAGE4_FINDINGS.md` and `research_roadmap.md`.
