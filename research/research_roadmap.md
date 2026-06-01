# NeuroSync 졸업연구 로드맵 (v2 — 목표 전환: per-core speculative advance)

> 이 파일은 /compact·/clear 후에도 단독으로 연구 재개가 가능한 **압축 단일 진실원**.
> 상세 근거는 `CLAUDE.md`(로드맵), `MODIFICATIONS.md`(코드원장),
> `STAGE3_ORACLE_DESIGN.md`, `runspace/*/...txt`, `result_img/stage3_*` 참조.

---

## 0. 연구 목표 (전환됨)

**기존(폐기):** 동기화주기 T 를 런타임에 동적으로 최적화하는 예측기.
**현(본선):** **코어별 독립 speculative timestep advance + belated-spike 예측 stall.**

각 코어가 매 timestep, **국소 정보만으로** perceptron 예측:
> "다음 timestep 으로 advance 하면, *직전 timestep 까지는 belated 가 아니었을*
> spike 가 (advance 탓에) belated 가 되어 rollback 을 유발하지 않을까?"

위험 예측 시 그 spike 수신까지 **적절히 stall** 후 advance → rollback 회피.
정확성은 불변(stall 은 *지연*만; 기존 rollback 이 backstop). 예측기는 성능 힌트.

**이중 목표**
1. **Latency 단축**: critical-path 코어의 rollback 손실 사이클을, 영향이 작은
   stall 사이클로 치환 → 전체 latency 감축.
2. **Energy 감축**: stall = idle(클럭게이팅) ≪ rollback(동일 연산 2회 재계산
   + RR 절차) → mis-spec 1건을 (재계산+RR 에너지)→(idle leakage)로 치환.

---

## 연구 경과 압축 (Stage 0–3B, durable 결과)

| 단계 | 한 줄 결과 |
|---|---|
| **0 데이터셋** | `brunel_si` v1(4100뉴런, G=7/EP=50Hz, 1971ts, ~10min). 핵심: **ISN 항상성** — tail 평탄화는 결함 아닌 억제안정망 본질(시변 OU v2도 출력 불변). 표준=v1. |
| **1 활성도 시계열** | spike 생성(clean.dat, CV 0.95 지속진동 SI형) vs belated 롤백트리거(rollback_events.dat, 전달수준, CV 0.40) — **단위 다름, 직접비교 금지**. |
| **2 활성도↔롤백** | spike↔rollback강도 **매우 약함**(Pearson 0.29, R²≈0.09), 활성도-무관 롤백 floor 큼. **평활 캐스케이드** spike CV0.95→롤백 CV0.40→cycle CV0.16. |
| **3 oracle(글로벌 T)** | 고정 T=1..128 U자형, 최소 **T=64(1.81M)**, T=16=2.09M(최적 고정 T 가 T16 대비 +15.5%). oracle 3종(A 포락선/B 단일최적/C 롤백예산): 전지적 **Oracle-A 도 최적고정T 대비 +1.99%**(B=128; 더 잘게=포화 ~4%). |
| **3B-Task1** | **T=256 = 병리적**(rollback-explosion, 100%CPU 63min, ts1586서 ≥4.58M, 비종료→kill). per-block 최적 T∈{1..128} = **+1.99% (≤5%)** → **글로벌 동적-T 깔끔히 폐기**. |
| **3B-Task2** | 시뮬 `redo_cyc` 계측(additive·non-invasive, cyc·spike 불변 검증완) → **완벽 per-core stall *oracle* 천장 = rollback_state 사이클비율: T=64 10.4%, T=128 18.1%**(코어별 균일). 평균 롤백거리 Δt≈35ts. (당시 GO 판단 = oracle 천장만 근거) |
| **4 trace-driven 예측가능성 (A4 gate)** | 재시뮬0. **A4 = FAIL**: ① granularity=per-src-core 옳음(Gini); ② 시간 ACFdem≈0·R²_lastval≈−0.9(Poisson); ③ Δt⊥NoC기하(corr −0.007), 정적 link prior 무력; ④ 실현 예측기 net 천장회수 **−68~−344%**(FP:TP≈5–6) ≪ 통과선 +29%. **오직 전지적 oracle 만 통과**. → 상세 `STAGE4_FINDINGS.md` |

**결론(갱신):** 글로벌 동적-T 천장 ~2–4%(폐기)와 per-core stall 의 *실현*
효과 ~0(음수, A4 FAIL)은 **동일 근원 = ISN 항상성**(평활→white/Poisson·
Δt⊥거리). per-core *oracle* 천장 10.4–18.1% 는 실현 불가(예측 핸들 부재
입증). **유일 레버 = 정적 최적 sync 주기 T=64**. 다음 전략은 `STAGE4_
FINDINGS.md` §4 후보 중 *추후* 사용자 선택(현재 보류).

**핵심 코드 위치(Stage 5 구현용, 발견 완료)**
- `Core.pyx:242` `GV.cyc[ind]+=1`(step당 1 cyc) · `:166–179` rollback_state 분기
  (`redo_cyc` 계측 지점) · **`:235` `GV.timestep[ind]+=1` = speculative advance
  (단조; 여기에 stall 게이팅)** · `:79` neu_comp_state.
- `RRManager.pyx:777` `rollback()` · `:107` `delta_t` · `rollback_consuming_cyc`
  누적 · `GV.rollback_events`(Stage1/2 로그).
- `Router.pyx` `packet_in()`의 **belated 분기(`gen_timestep < GV.timestep`)**
  = 예측기 훈련 정답신호·src별 카운터 지점.
- 산출: `runspace/brunel_si_specgate/*/redo_cyc.dat`, `runspace/brunel_si/SWEEP_total_cycles.txt`.

---

## 4. per-core 예측가능성 gate — **A4 = FAIL (latency 축), 정직 down-scope**

> 단일 진실원 상세: **`STAGE4_FINDINGS.md`** (효과 크기·무력 원인·다음
> 전략 후보). 코드 `stage4_predict.py` step1..5, 그림 `result_img/
> stage4_*`, 로그 `runspace/brunel_si/stage4_step{2,3,4,5}_*.txt`.

3B 의 redo_frac(10.4/18.1%)은 **oracle 천장**일 뿐 — 실현 가능성은 별도
gate. trace-driven(재시뮬0) 으로 측정한 결과:

- **4-1 공간분포**: victim Gini≈0.15·src-core Gini≈0.28(거의 균일, hot
  link 없음) → 예측기는 전 코어 균일 작동 필요(핫스팟 특화 불가).
- **4-2 granularity**: per-src-core 가 옳은 단위(dense·균일). src-neuron=
  발화율편향·희소·상태폭증 기각, 동적 per-link=희소 기각.
- **4-3 시간 예측가능성**: within-pair demeaned ACF≈0, R²_lastval≈−0.9
  (글로벌평균보다 나쁨) → 롤백 시계열 fine-scale **Poisson**(forecasting
  무력). eta² fine 3~6%.
- **4-4 공간 예측가능성**: Δt ⊥ NoC 기하(corr(hop,Δt)=−0.007, inter≈
  intra, dist-aware<uniform), Δt≈T/2 → **정적 NoC link prior 무력**.
  uniform horizon-cap = effective-T 재매개변수화(Stage3가 이미 최적화).
- **4-5 A4 gate 리플레이**: 통과선 = net 천장회수 ≥29.1%(T128→T64).
  oracle=net100%(WIN, 단 완벽예측 전제). 실현(last-block/EWMA/static-
  prior) **net = −68~−344%**, FP:TP≈5–6 → **전부 음수, FAIL**.

**판정**: 예측 핸들(시간·공간) 부재 입증 → per-core 예측 stall 의 *실현*
latency 이득 ≈ 0(음수). 글로벌 동적-T 와 동일 근원(ISN 항상성). **latency
A4 = FAIL → 정직 down-scope**(로드맵 §4-2 사전합의대로). 미닫힌 축 =
**energy**(아래 §6, 추후 정량). 다음 전략 = `STAGE4_FINDINGS.md` §4 후보
중 추후 사용자 선택(현재 보류).

---

## 5. per-core speculative advance + perceptron stall 예측기 구현

> ⚠️ **상태: 보류(A4 FAIL)**. 이 절은 *어떤 미래 전략이 A4 를 통과할 경우*
> 의 구현 청사진으로만 보존. 현재 trace 증거(§4)는 이 예측기의 실현
> latency 이득 ≈0(음수)을 입증 → 미구현. 진행 여부 = `STAGE4_FINDINGS.md`
> §4 추후 결정에 종속. 아래 코드 위치·additive 원칙은 재개 시 유효.

**5-1. 예측 대상 (정의 고정)**
- 예측 = spike *발생*(예측불가, 시뮬 본질)이 **아니라**, advance 가 유발하는
  **belatedness**(전송지연=NoC 거리·hop·혼잡 → 구조적·예측가능).
- 코어 c, 현 timestep t: "t→t+1 advance 시, ≤t 에 영향줄 spike 가 belated 로
  도착해 rollback 을 부르는가?" 이진 판정.

**5-2. perceptron 예측기 (기존 Stage5 BP 아이디어 흡수)**
- feature: 해당 source 의 Local/Remote Firing History, 최근 belated 이력
  (saturating), NoC 거리/hop/inter-chip(정적 prior), 마지막 sync 후 투기깊이.
- perceptron: weighted sum→threshold→안전/위험. rollback 발생 or 불필요 stall
  시 weight 온라인 갱신. 출력 = source별 `safe_horizon`; 코어는 전 source
  `safe_horizon` 최솟값까지만 advance. cold-start = topology 정적 prior 하이브리드.

**5-3. 시뮬레이터 수정 구역 (additive·cfg 플래그·복제후수정·새 result폴더)**
- 예측기 상태 → `RRManager`(mis-spec 탐지·src history 보유).
- 훈련 정답 → `Router.pyx packet_in()` belated 분기.
- 예측 소비(게이팅) → `Core.pyx:235` speculative advance(`GV.timestep+=1`)
  앞에 stall 게이트. **stall timeout K**(강제 advance, 기존 rollback backstop)
  로 데드락 방지. 정확성 회귀테스트: `clean.dat` 불변 필수.

**5-4. 평가**
- 비교군: 고정 T16 / best static T64 / (폐기된 글로벌 동적-T 참고선) / **신규 예측기**.
- 분해 지표: 최종 cyc = baseline + sync + (**회피된 rollback cyc** − **추가 stall cyc**).
  핵심 부등식 **E[회피 critical-path rollback] > E[불필요 critical-path stall]**.
  주의: latency 는 매 주기 *critical-path 코어*의 rollback 만 좌우(barrier 뒤
  코어 rollback 은 무관) — redo_frac 은 코어 균일하므로 critical-path 근사 타당.
- 큰 T 동반측정: stall 이 rollback 억제 → 큰 T(저 sync overhead) 해금 효과 확인.
- 목표: 실측 가속이 oracle 천장(10.4%@T64, 18.1%@T128) 대비 의미있는 분율.

---

## 6. 하드웨어 부담 + 에너지 분석

> 상태: **energy = 유일 미닫힌 축**(latency A4 FAIL 확정). 6-3 이 다음
> 전략 결정의 핵심 입력 — *현재 미수행*. 6-1/6-2(area/latency overhead)는
> 예측기 구현 종속이라 §5 와 함께 보류.

**6-1. Area**: perceptron weight 테이블 = source수 × history × weight bits.
디버그 메타 제외 최소구성(Checkpoint 주석의 "실 HW=lastspike_t+addr만" 방식)
으로 in-core SRAM 예산 대비 평가.

**6-2. Latency overhead**: 본 방식은 **per-core/per-link → 전역 aggregation 불필요**
(글로벌 동적-T 는 root 가 롤백강도 수집 필요했음 — 구조적 이점). perceptron
dot-product 1회를 neu_comp stage 에 은닉 가능한지 분석.

**6-3. Energy (두 번째 이득 축)**: stall=idle→Internal state/L-Trace/Learning
미동작·클럭게이팅. rollback=t0부터 재계산(연산 2회)+RR 절차. 정량:
(회피 rollback수 × 평균 재계산에너지 + RR에너지) − (추가 stall수 × idle에너지).
의의: latency 가 박빙이어도 **energy 로 차별화** 가능. 입력은 5-4 분해 카운트
+ 단순 전력모델(active vs idle 비, 문헌/파라미터화) 민감도.

A6(결과): 종합 net win/loss 판정 + 졸업논문 결론.
