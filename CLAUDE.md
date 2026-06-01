# NeuroSync GradProj — CLAUDE.md

## 프로젝트 개요

**NeuroSync**는 HPCA 2022 논문 기반의 투기적(speculative) 멀티코어 뇌 시뮬레이터 하드웨어를 소프트웨어로 시뮬레이션하는 프레임워크.

- 핵심 메커니즘: 동기화 주기 T마다만 동기화하고 그 사이를 투기 실행, 오예측 시 롤백
- 언어: Python + Cython (성능 크리티컬 모듈은 `.pyx` → C 컴파일)
- 외부 도구: Metis (뉴런-코어 그래프 파티셔닝)

**졸업 연구 목표**: ~~동기화주기 T 동적 최적화~~ → ~~코어별 speculative advance + belated 예측 stall~~ → **둘 다 ISN 항상성으로 실현 latency 이득 ≈0 (A4 FAIL, Stage4 입증)**. 현 국면 = 정직한 한계규명 + energy 축 미정 + 다음 전략 추후 선택. 단일진실원 `STAGE4_FINDINGS.md`
- 큰 그림: 워크로드 활성도/롤백 분석 → 글로벌-T oracle 천장(작음→폐기) → per-core stall oracle 천장(10.4/18.1%) → **trace-driven 예측가능성 A4 gate = FAIL(시간 Poisson·공간 Δt⊥거리·실현 net 음수)** → [보류] perceptron 구현 / [미정] energy 정량
- 이중 목표: ① latency(critical-path rollback 사이클 → 저영향 stall 치환) ② energy(stall idle ≪ rollback 재계산+RR). 세부: `research_roadmap.md`(v2, 압축 단일 진실원)
- 세부 단계는 아래 **연구 로드맵** 및 `research_roadmap.md` 참고

---

## 연구 로드맵

`research_roadmap.md` 기반으로 단계별 진행. **현재 단계: Stage 4 완료 → A4 gate = FAIL (latency 축). 글로벌 동적-T 와 동일 근원(ISN 항상성)으로 per-core 예측 stall 의 *실현* 이득 ≈0(음수). 정밀 정리 = `STAGE4_FINDINGS.md`. energy 축만 미정. 다음 전략 = 사용자 추후 선택(현재 보류) — Stage 5 구현은 보류**. 진행하며 이 줄을 갱신할 것.
- Stage 0: `brunel_si` 확정. retune `G=7,EP_RATE=50Hz`(brunel_workload.py)으로 감쇠 완화.
  - **핵심 발견(ISN 항상성)**: 1500ts↑ tail 평탄화는 워크로드 결함이 아니라 **억제안정화망의 본질**. 외부구동을 느리게 2~8배 흔든 v2(시변 OU Poisson)도 출력 불변 → 재귀 억제가 공통입력 변화를 흡수. Stage 2의 "투기HW가 롤백 흡수→cycle 평탄"과 같은 충격흡수 성질이 **네트워크 자체에도** 존재 → 동적T 상한 제한·느린 history 예측기 정당화의 핵심 근거
  - 표준 워크로드 = **v1**(`brunel_workload.py`+`example.cfg`→runspace/brunel_si). v2(`brunel_workload_v2.py`+`example_v2.cfg`→runspace/brunel_si_v2)는 강건성 확인용. ⚠️ 현재 `benchmark/brunel_si/dataset`는 v2 상태 — v1 필요시 `brunel_workload.py` 재생성. 결과 그림은 `result_img/*_v1.png`(표준)·`*_v2.png`(비교) 보존
- Stage 1 완료: 스파이크 시계열 — [plot_activity.py](plot_activity.py), `result_img/stage1_brunel_si_spike_timeseries_T16.png`
  - #1 최종올바른 발화 = `clean.dat` (**발화 생성** 수준 = 네트워크 활성도, retune 후 CV 0.95 지속진동 SI형)
  - #3 belated 롤백트리거 = `rollback_events.dat` (**시냅스 전달 이벤트** 수준, #1의 ~13×, CV 0.40) — #1과 단위 다름, 직접비교 금지
  - ⚠️ `clean/raw.dat`은 *발화 생성* 기록(in-flight 아님). raw≈clean(취소 anti 247개뿐). 'belated'는 수신측 전달 속성이라 생성로그엔 부재
  - #2 '모든 in-flight'(전달수준)는 사용자 결정으로 생략 (필요시 connection.npy fan-out 복원 or 전달경로 계측+재실행)
- Stage 2 완료: 롤백강도(=고정 16-ts Σdelta_t) 분석 — [plot_stage2.py](plot_stage2.py), [plot_cycle_per16ts.py](plot_cycle_per16ts.py)
  - `result_img/stage2_brunel_si_rollback_intensity_T16.png`, `_rollback_vs_spike_scatter_T16.png`, `brunel_si_cycle_per16ts_T16.png`
  - **스파이크수↔롤백강도: Pearson r=0.29 / Spearman ρ=0.19 (유의하나 매우 느슨, R²≈0.09)**. 큰 절편(18,426)=활성도-무관 롤백 floor. lag=0. (retune 전 r=0.39와 비교해 결론 강건)
  - overlay 검증: 롤백강도↔소모cycle r=0.38 (cycle은 정상연산 지배, CV 0.16으로 매우 평탄)
  - 평활 캐스케이드: 스파이크 CV 0.95 → 롤백강도 CV 0.40 → 소모cycle CV 0.16
  - 시사: **활성도만으론 롤백 예측 약함(R²≈0.09)** → 동적T는 롤백강도 history(자기상관) 기반이 유망 (Stage 4/5 설계 방향)
- Stage 3 완료: oracle 상한선 — 설계 [STAGE3_ORACLE_DESIGN.md](STAGE3_ORACLE_DESIGN.md), 구현 [plot_stage3_fixedT.py](plot_stage3_fixedT.py)·[oracle_analysis.py](oracle_analysis.py)
  - 고정 T 스윕(brunel_si v1, T=1..128): 총사이클 **U자형**, 최소 = **T=64(1.81M)**. T=1=9.89M(동기화 과다), T=128=1.91M(롤백 과다). `runspace/brunel_si/SWEEP_total_cycles.txt`
  - **oracle 3종**(서로 다른 관점): A=per-block 최소포락선(자유전환 상한), B=전역단일최적T(=고정T최소=baseline), C=롤백거리예산 게이트(배치가능 정책 천장; Stage4 표적)
  - **핵심 결과**: 최적 고정 T=64 는 T=16 대비 **1.155×**. 그러나 전지적 Oracle-A 도 최적고정T 대비 **겨우 1.020×**(A–B gap=1.95%), Oracle-C 는 gap 의 6.6%만 회수
  - **결론(ISN 항상성과 정합)**: 이 워크로드에서 동적 T 의 이론적 천장이 ~2%로 매우 작음 → **진짜 레버는 동적화가 아니라 올바른 상수 T(=64) 선택**. baseline 을 T=16→T=64 로 재설정 권고 (`result_img/stage3_brunel_si_fixedT_total_cycles.png`, `_oracle_comparison.png`, `runspace/brunel_si/stage3_oracle_results.txt`)
- Stage 3-B 완료: **글로벌 동적-T 폐기 확정 + 신본선 확립** — [stage3_T256_decision.py](stage3_T256_decision.py)·[oracle_analysis.py](oracle_analysis.py), 계측 [Core.pyx](neurosync/Core.pyx)`redo_cyc`(additive·non-invasive, MODIFICATIONS.md)
  - **Task1(글로벌 동적-T 사망진단)**: T=256 추가 시뮬→**병리적**(rollback-explosion, 100%CPU 63min, ts1586서 ≥4.58M, >31min/block 무진척→kill). per-block 최적 T∈{1..128}(Oracle-A,B=128)=1.773M=**최적고정T 대비 +1.99%(≤5%)** → **글로벌 동적-T 깔끔히 폐기** (`result_img/stage3_fixedT_total_cycles_with_T256.png`, `_oracleA_only_comparison_T256.png`, `runspace/brunel_si/stage3_T256_decision.txt`)
  - **Task2(신본선: 코어별 speculative-advance + 예측 stall)**: redo_cyc 정밀계측(`runspace/brunel_si_specgate/`, cyc/ spike 불변 검증완) — `rollback_state` 소모비율 = 완벽 stall-oracle 천장 = **T=64 10.4%, T=128 18.1%**(코어별 균일, 해석추정 9/17% 초과). 결합(stall+큰T)≈12.6%. **10% 연구가치 기준 충족** → 글로벌 T 대체 본선. 알고리즘(2bit/EWMA/퍼셉트론 stall 게이트)·6단계 로드맵은 대화 기록 참조. 다음 gate=재시뮬 없는 trace-driven 예측가능성 연구(자기상관·리드타임 평균 Δt≈35ts)
  - **Stage 4~5 재정의**: 기존 "동적 T 알고리즘/Fire 예측 기반 T"는 폐기. 대체 = "코어별 belated-spike 예측 stall"(Stage5 퍼셉트론과 자연 융합), Stage6 HW부담 분석은 그대로 적용

| 단계 | 목표 | 산출물 |
|------|------|--------|
| **0. 데이터셋 결정** | 시간에 따라 활성도가 높음↔낮음 반복(특정 상태로 수렴 X), 신경과학적으로 유효한 워크로드. Brunel SI type 유력, 규모는 `example_workload.py` 수준 | 새 워크로드 생성 스크립트 |
| **1. 활성도 시계열 분석** | 네트워크 활성도(=일정 기간 생성 스파이크 수)를 시간축으로 시각화 → 활성도가 시간적으로 얼마나 연속적인지 파악. (옵션) 롤백 유발 스파이크 별도 집계 | 활성도-시간 그래프 |
| **2. 활성도↔롤백 상관** | 롤백 강도(=고정 기간 내 롤백 거리 총합)와 전체 스파이크 수의 상관관계 분석 | 상관 분석 결과 |
| **3. Oracle 상한선** | ✅완료. 글로벌-T oracle 천장 ~2–4%(폐기) + 3B per-core stall oracle 천장 10.4/18.1%(GO) | oracle 수치·`stage3_*` |
| **4. per-core 예측가능성 gate** | ✅완료. **A4 = FAIL(latency)**: 시간 ACFdem≈0·R²lastval≈−0.9(Poisson), Δt⊥NoC기하(corr−0.007), 실현예측기 net −68~−344%(FP:TP≈5–6) ≪ 통과선 +29%. oracle만 통과. 글로벌-T와 동일근원(ISN) | `STAGE4_FINDINGS.md`·`stage4_predict.py`·`result_img/stage4_*` |
| **5. perceptron stall 예측기** | ⏸️**보류**(A4 FAIL — 실현 latency 이득≈0 입증). 구현 청사진만 보존(`Core.pyx:235`/`Router packet_in`/`RRManager`). 진행=추후 전략 결정 종속 | (미구현) |
| **6. HW 부담 + 에너지** | ⏸️area/latency=§5 종속 보류. **energy = 유일 미닫힌 축**(추후 정량, 다음 전략 결정 입력) | (energy 모델 미수행) |

---

## 핵심 파일

| 파일 | 역할 |
|------|------|
| `neurosync/Core.pyx` | 코어 FSM: 뉴런 계산 → 시냅스 → NoC → 동기화/롤백 |
| `neurosync/RRManager.pyx` | 롤백·복구·체크포인트 관리 (연구 핵심) |
| `neurosync/NoC.pyx` | NoC 패킷 라우팅, 칩간 통신 |
| `neurosync/Neuron.pyx` | 뉴런 모델 (DLIF, Izhikevich, Alpha) |
| `neurosync/GlobalVars.py` | 타이밍·대역폭 파라미터 (NoC 지연, 파이프라인 깊이 등) |
| `run.py` | 오케스트레이션: 파라미터 스윕, Metis 매핑, 병렬 실행 |
| `example.cfg` | 시뮬레이션 설정 (chip_xy, sync_period, pretrace_engine 등) |
| `research_roadmap.md` | 0~6단계 연구 계획 (단계별 진행의 기준 문서) |
| `benchmark/brunel_si/brunel_workload.py` | **현재 워크로드** — Brunel SI-type (4100 뉴런), 상단 KNOBS로 스케일 조정 |
| `benchmark/example1/` | (구) mini 워크로드 (2080 뉴런, Watts-Strogatz) |
| `mapping/` | Metis 기반 뉴런-코어 매핑 |
| `plot_*.py` | 결과 분석·시각화 |

---

## 빌드

```bash
cd neurosync/
python3 setup.py build_ext --inplace
```

`.pyx` 파일 수정 시 반드시 재컴파일 필요.

---

## 실행

```bash
# 워크로드 생성 (최초 1회, 또는 네트워크 변경 시)
cd benchmark/example1/ && python3 example_workload.py

# 시뮬레이션 실행
cd /home/heechan/26_GRADPROJ/NeuroSync_GradProj
python3 run.py example.cfg
```

결과는 `runspace/` 하위에 저장.

---

## 정확성 검증

```bash
# T가 달라도 spike 출력이 동일해야 함
diff runspace/lazy/example1_peri1_10pretrace_eng/multicore_spike_out_clean.dat \
     runspace/lazy/example1_peri16_10pretrace_eng/multicore_spike_out_clean.dat
```

---

## 현재 연구 설정 (example.cfg)

- 워크로드: `brunel_si` (Brunel SI-type, 4000 뉴런 + 100 poisson = 4100)
- 토폴로지: 4칩 × 16코어 = **총 64코어**, 코어당 ~64뉴런
- `max_timestep = 1971` (= 50 + 128×15), `setup_timestep = 50` (웜업: 투기 실행 안 함)
  - 1971로 잘라야 마지막 T=1 cooldown 드레인 구간(ts≈1986~2000)이 분석에서 배제됨
- `sync_period = 16` — 로드맵 baseline T (spike 출력은 T 무관 → Stage 1 분석엔 무영향)
- 분석 대상 구간: 타임스텝 50 ~ 1971 (웜업·T=1 tail 제외)
- 참고 실측: simulate 루프 wall clock ≈ 8.3분(@1971, T=16) + 최초 init ≈ 3분

---

## 연구 핵심 개념

- **T (sync_period)**: 투기 실행 단위. T가 크면 롤백 위험↑, 작으면 동기화 오버헤드↑
- **롤백**: 오예측 감지 시 체크포인트로 상태 복원, 비용이 큼
- **체크포인트**: 동기화 경계마다 상태 저장 (Checkpoint.pyx)
- **웜업 (setup_timestep)**: 네트워크 안정화 전 구간, 롤백 폭증 가능
- **네트워크 활성도**: 일정 기간 동안 생성된 스파이크 수 (시계열 분석·예측의 단위)
- **롤백 강도**: 고정 기간 동안 롤백 거리의 총합 (동적 T 결정의 입력 신호)
- **Oracle**: 워크로드 전체를 완벽히 아는 상한선 알고리즘 — 동적 T의 이론적 최대 가속 기준

---

## 주의사항

- `rm -rf runspace/lazy` 전에 보존할 결과 있는지 반드시 확인
- `.pyx` 수정 후 빌드 안 하면 변경사항 미반영
- `run.py`는 파라미터 조합별로 별도 디렉토리에 Cython 코드를 복사해 컴파일함 — 공통 수정은 원본 `.pyx`에서 해야 함
- `tail -n 20 runspace/lazy/<폴더명>/log` 로 실행 상태 확인 가능
