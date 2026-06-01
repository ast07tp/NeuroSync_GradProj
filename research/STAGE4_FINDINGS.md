# STAGE4 — per-core speculative-advance + 예측 stall: 효과 크기 & 무력 원인 정밀 정리

> 목적(사용자 지시): **다음 전략을 고르기 전에**, 현재 본선 전략(코어별
> speculative timestep advance + belated 예측 stall)이 *어느 정도 효과*이고
> *왜 효과가 적은지* 정확히 확정. 전 수치 = 이번 Stage4-2 trace-driven 연구
> (재시뮬 0회, 기존 `rollback_events.dat` T=64/128 + `redo_cyc.dat`).
> 분석 코드 `stage4_predict.py`(step1..5), 그림 `result_img/stage4_*`,
> 로그 `runspace/brunel_si/stage4_step{2,3,4,5}_*.txt`. 단위: `src_pid`=
> 소스뉴런 gid, `rollback_gid`=victim뉴런 gid, `mapping_4100_64.npz`로
> src/dst-core 파생. redo_cyc=64코어 합산 / CYC_T*=임계 1코어 total (불혼합).

---

## 1. 효과 크기 (정량 — "어느 정도")

| 구분 | 수치 | 의미 |
|---|---|---|
| **이론 천장(완벽 oracle stall)** | redo_frac = **T64 10.42%, T128 18.14%** | 완벽 예측 시 제거 가능한 rollback_state 사이클 비율(Stage3-B 확정). 전략이 *낼 수 있는 최대* |
| **유효 천장(동적여지)** | **~2%** | 단, best 고정 T=64 가 이미 최적(Stage3). T16→T64 재선정이 +15.5%. 동적/예측이 그 위에 더 버는 천장은 글로벌-T와 동급 ~2% |
| **A4 통과선** | net 천장회수 **≥29.1%** | T=128 base→fixed-T=64(1.808M) 도달 요건 = (1−1.808/1.909)/0.181 |
| **실현 예측기 net 회수** | last-block **−68%**, EWMA **−71~−133%**, static-prior **−344%** (천장 대비) | 전부 **음수**. gross 회수(15.7~75.8%)를 FP(거짓 stall)가 압도 |
| **실현 예측기 절대가속** | **0% (실질 음수)** | oracle 18.1% 대비 realizability gap ≈ 천장 전체. fixed-T=64는 물론 base T=128도 못 이김 |
| FP:TP 비 | **5.3 ~ 6.2** | 예측기가 stall 발사할 때 84%+ 가 거짓 |

**한 줄**: 이론적으론 ≤18%(유효 ~2%), **실현 가능 효과 = 0(음수)**. 완벽
oracle 만 천장을 회수하고, 구현 가능한 어떤 단순 정책도 net 음성.

---

## 2. 왜 효과가 적은가 (메커니즘 — 정확한 인과 사슬)

1. **ISN 항상성(Stage0)**: 억제안정망의 재귀 억제가 입력 변동을 흡수 →
   평활 캐스케이드 **spike CV 0.95 → rollback CV 0.40 → cycle CV 0.16**.
2. **시간축 예측 불가(Step3)**: per-(dst,src-core) 롤백 시계열은 per-advance
   결정 시간대(Δt≈35–67ts)에서 **시간적으로 white(Poisson)**.
   within-pair demeaned ACF≈0(±0.0x), **R²_lastval≈−0.9 / R²_ewma≈−0.3
   (글로벌 평균보다 나쁨)**. eta²(정적 prior가 설명하는 질량분산)도 fine
   scale 3~6%로 작음. → *최근 belated 이력* feature 무력.
3. **공간축 예측 불가(Step4)**: 롤백거리 Δt 가 NoC 기하와 **무상관** —
   corr(hop,Δt)=**−0.007**, inter-chip 35.4 ≈ intra 35.3, dist-aware
   horizon 이 uniform 보다 *나쁨*. Δt≈T/2 (sync 윈도 위치가 지배, 전송거리
   아님). → *정적 NoC link prior* 무력(설계서 제거가 정직).
4. **비선택 stall = 작은 T**: 시간·공간 선택신호가 없으니 uniform depth-cap
   은 **effective-T 재매개변수화**일 뿐 → Stage3 U-곡선이 이미 최적화
   (T=64), 작은 cap = sync/chkpt 과다. 새 레버 아님.
5. **gate 귀결(Step5)**: 예측 불가 → 예측기는 거의 FP(FP:TP≈5–6). 불필요
   stall 의 latency 가산이 드물게 맞춘 rollback 회수분을 압도 → net ≤ 0.
6. **글로벌 동적-T와 동일 근원**: 글로벌-T 천장 ~2%(폐기)와 per-core 실현
   ~0 은 *같은 현상*. ISN 항상성이 spike→rollback→cycle 의 활용가능
   변동구조를 제거. 유일 레버 = **정적 최적 sync 주기**(T=64).

**granularity 결론(질문 답, 그래도 유효)**: 만약 진행한다면 상태/결정 단위
는 **per-src-core**(균일·dense; src-neuron=발화율편향·희소·상태폭증으로
기각; 동적 per-link=희소로 기각). 단 §2-3·2-4 가 *정적 link prior 항*을
실측 기각 → "per-src-core 동적 + 정적 prior" 2-tier 중 정적항은 이 워크로드
무효.

---

## 3. 아직 안 닫힌 축 — energy (다음 전략 결정 입력)

latency A4 = FAIL 확정. **에너지 축은 미정**: TP 에서 rollback(재계산
k_rb≈1.17–1.25× + RR 절차 에너지) → idle(클럭게이팅 leakage) 치환은
*에너지* 절감일 수 있음. 그러나 실현 예측기 FP:TP≈5–6 → 거짓 stall idle
*에너지*가 이득을 먹을 가능성 큼(latency 와 동형 논리). stall 내부 사이클/
전력비는 trace 로 검증 불가 → **Step6 전력모델**(active vs idle, RR 에너지,
문헌 파라미터 민감도)로 별도 정량해야 결론. *현재 미수행* — 추후 전략
선택의 핵심 입력.

---

## 4. 추후 전략 후보 (사용자 결정 보류 — 선택 안 함, 목록만)

A. **Step6 에너지 정량 먼저** → latency음성+energy(±) 완성 후 재판단.
B. **정직한 negative-result 논문** — Stage0~4 통합 oracle+예측가능성
   프레임으로 "ISN 항상성 워크로드에서 투기 오버헤드는 동적-T·per-core
   stall 어느 쪽도 환원 불가, 유일 레버=정적 최적 T" 입증. 재시뮬 0.
C. **다른(덜 항상성/버스티) 워크로드로 일반성 검증** — 전 파이프라인
   재실행. 음성이 워크로드 특수성인지 근본인지 규명(재시뮬 필요).
D. 예측기 가설 추가 탐색 — Step3·4가 신호부재를 강하게 시사 → 낮은 기대.

---

## 5. 무력 *결정적 원인* 진단 (STEP6, 사용자 가설 검증, 측정값)

가설 A1(stall→그 코어 미래 spike 지연→하류 재-belated 전파) / A2(코어
~64뉴런이 timestep 공유인데 한 ts victim 은 소수 → 다수 위해 전진 유리한데
소수 위해 코어 전체 stall) / B(예측기 품질) 중 무엇인가? (코드
`stage4_predict.py step6`, 그림 `result_img/stage4_cause_diagnosis.png`,
로그 `runspace/brunel_si/stage4_step6_cause.txt`. 단위: per-TIMESTEP =
실제 advance 결정 단위; bin=16 은 victim 뭉쳐 A2 과소평가하므로 per-ts 가
정답.)

- **A2 = 결정적 (사용자 정확)**: per-ts (코어,ts) belated 발생 시 victim
  뉴런 = **mean 7.5 / median 6** (코어 ~64 중) → ~88% 뉴런은 그 ts
  belated 無. timestep 코어 공유라 그 소수 위해 코어 전체 stall →
  **헛정지:victim 손익비 = 7.5 : 1** (T64 7.4:1). 코어가 belated 만나는
  ts = **30%** → per-core stall 게이트면 30% ts 코어 전체 정지 = 사실상
  T 붕괴(Stage3 열위). **완벽 belated 예측기여도 *per-core* 단위 stall
  이면 구조적으로 패배** — 예측 성능과 무관한 granularity 불일치.
- **B = 동시 성립(보강), 단 '예측기 탓' 아님**: 블록 belated 분리 AUC
  causal last-block 0.53·EWMA 0.56 (≈무작위), *미래 컨닝* 정적 rate
  조차 0.65(약). belated 는 예측기 품질이 아니라 **내재적으로 예측 신호
  부재**(Step3 Poisson·Step4 Δt⊥거리와 정합).
- **A1 = 전제 성립(직관 타당), 완전검증=재시뮬 필요**: corr(코어
  victim-mass, source-mass) = +0.10(T128)/+0.38(T64) 양수 → stall 대상
  코어가 동시에 큰 belated source → 지연 전파 경로 존재. 정적 trace 는
  재타이밍 미반영 → **Step5 oracle(+18%)은 과대평가**(실제 더 나쁨).
- **종합**: 세 원인 동방향. 핵심 = **A2(공유 timestep × per-뉴런 희소
  victim, 7.5:1)**, 그 위에 B(내재 예측불가) 곱, A1(전파)이 oracle 상한
  까지 갉음. → per-core speculative-advance stall 폐기 **확정 정당**.

## 5-B. perceptron BP 정면 확인 (STEP7) — '직접 예측' 경로 airtight

토이 예측기(last-value/EWMA)뿐 아니라 **branch-prediction 비유의 대표·
최강 온라인 도구인 perceptron(Jiménez–Lin)** 도 못 맞히는가? BP 표준
평가법(트레이스 온라인 학습 리플레이, 재시뮬0)로 정면 확인. 코드
`stage4_predict.py step7`, 그림 `result_img/stage4_perceptron.png`, 로그
`runspace/brunel_si/stage4_step7_perceptron.txt`.

- **타겟 = per-(dst-core, *timestep*)** = 실제 투기-advance 결정 단위
  (belated율 T64 **0.284** / T128 **0.300**, 비-degenerate). per-(코어,
  T-window) 는 belated율 **~0.97**(거의 항상 발생=vacuous)이라 부적합 —
  per-ts 가 정답(이 자체도 의미 있는 부수 발견).
- **예측기(이상화, 최대 유리)**: per-entity(dst-core) weight + local
  history(H) + global history(G; gshare식) + bias, **float 무클립**,
  online, entity-벡터화. H=G ∈ {4,8,16,32,64} 스윕 + kitchen-sink
  (H64+G64+remote-activity feature).
- **결과**: perceptron **AUC ≈ 0.53–0.58** (chance 0.5 바로 위, usable
  BP ~0.95 에 한참 못 미침), **majority 대비 acc lift ≈ 0 (±0.01)**.
  2-bit·last-value 와 동급, *미래 컨닝* static-rate 상한(AUC≈0.52)도
  무의미. 그 사소한 AUC>0.5 = Stage3 의 약한 단거리 자기상관(near-
  Poisson+미세 rate 이질성)뿐 = Stage5 가 이미 FP:TP≈5–6, net≤0 으로
  무력화한 그 신호.
- **결론**: 비예측성은 **예측기 약함이 아니라 신호 자체의 부재**(Step3
  Poisson·Step4 Δt⊥거리·Step6 정합). BP 비유의 최강 도구조차 무력 →
  '직접 belated 예측' 경로(0-1-2-3 의 (2)) **airtight**. (granularity
  A2 와 독립 — STEP7 은 예측 *품질*만 격리 측정.)

## 6. branch-prediction 아이디어의 *정확* 재적용 3안 (제안만, 미구현)

실패 교훈: per-core stall 은 BP 를 *오적용* — ① 예측불가한 것(belated
*발생/방향*=B)을 예측 ② 비용단위(per-뉴런 victim)와 다른 granularity
(per-core)서 행동(A2) ③ 행동에 피드백(stall→자기 출력 지연=A1). 올바른
BP 적용 = *예측 가능한 것*을, *비용에 맞는 granularity*로, *값싸고 피드백
없는 복구*와 함께. 측정상 예측가능/결정론적인 것 = Δt 분포(좁음·정상·
≈T/2), 링크 침묵(Gini·Metis 지역성·self 1.6%), NoC 전송지연 하한(결정론).

1. **롤백 *범위/거리* 예측 → 표적 selective-replay** (BP 유추: branch
   *target*/RAS·checkpoint, direction 아님). 발생은 예측불가(B)지만 Δt
   는 좁고 정상·victim 은 per-ts ~7/64 로 희소(§5). ∴ "stall 여부"가
   아니라 "무엇을 얼마나 복구할지"를 예측: belated-prone 소수 뉴런만
   fine-checkpoint + Δt 분포 크기의 shadow state → 롤백 시 victim·≤Δt
   만 복구(보수적 full rollback_state 대비 ↓). **redo_cyc(10.4/18.1%)
   질량 자체를 건당 비용↓로 공략**. A1 무관(stall 無), A2 무관(per-뉴런
   복구), 예측대상이 *예측가능한 범위*. trace 로 천장 산정 가능(재시뮬0).
2. **per-link *침묵* 예측 → 투기적 sync/checkpoint elision** (BP 유추:
   way/filter·memory-dependence 예측, 값싼 안전 fallback). Stage3 의
   지배 레버 = sync 비용. 대다수 (src→dst)링크는 대다수 윈도서 무전송
   (self 1.6%·Gini·sparse fan-in = *이건* 예측가능). 침묵 예측 링크는
   checkpoint/handshake 생략(틀리면 기존 rollback backstop = 유계 복구).
   → 안전한 곳에서만 *effective T↑*(sync↓, Stage3 win) 하되 rollback
   폭증 없음. A2 무관(per-link), A1 무관(계산 지연 아닌 부기 생략),
   예측대상=침묵(예측가능).
3. **토폴로지 보장 안전 투기창** (BP 유추: static hint/provably-safe
   path, 오예측 0 by construction). NoC 최소 전송지연은 *하한이 결정론*:
   K-hop·inter-chip source 의 spike 는 물리적으로 그 전엔 도착 불가.
   ∴ 코어는 in-edge 최소 도착 horizon 까지 **롤백위험 0** 으로 advance
   (예측 아닌 *증명*). Metis 매핑+토폴로지+min transit 로 per-core 안전
   거리 계산, 위험 투기는 그 너머로 최소화. 예측기 부재→A1/B 무관, 안전
   하한이라 A2 무관. trace+mapping 으로 천장 즉시 산정(재시뮬0).

> 우선순위: #2(Stage3 입증 sync 레버 직격, 전형적 BP 투기) ≳ #3(무위험·
> 즉시 천장 산정 가능, 다만 이득 작을 수 있음) ≳ #1(redo 질량 직접·
> energy 동시, Δt/victim 측정 재사용). 셋 다 재시뮬 0 으로 천장 선검증
> 가능 → A4 식 gate 재적용 후 진행.

> 결정 규칙(로드맵 §4-2 사전합의): 회수율 너무 낮으면 정직하게 down-scope.
> 현재 per-core stall net ≤ 0 → A4 FAIL·폐기 확정. 다음 = §6 3안 중
> 추후 사용자 선택(각 안 재시뮬0 천장 선검증부터).
