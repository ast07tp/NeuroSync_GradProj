# Research Memo — 투기적 뇌 시뮬레이터의 롤백 오버헤드 감축 연구

> **새 Claude 세션이 이 메모만 읽고 20페이지 BS 졸업논문을 작성할 수 있도록
> 준비한 단일 브리프.** 모든 수치 주장은 출처가 명시되어 있고, 모든 설계
> 결정은 정당화되어 있다. 논문 본문은 **한글**, 마지막 페이지의 Abstract만
> **영문** — 표준 SNU BS thesis 관습. 메모 자체는 한글(지침/메타) +
> 영문(인용용 원문/수치)을 섞어 작성한다.

---

## 0. 사용 안내

- **참조 양식**: `research/paper/BS_Thesis_share.pdf` 의 **목차/구성/페이지 분량
  분배만** 전적으로 따른다. 내용(SpyKING CIRCUS 관련)은 절대 참고하지
  않는다.
- **참조 양식의 실측 목차** (사용자 직접 확인본):
  ```
  초록            i
  목차            ii
  그림목차        iii
  1 서론          1
    1.1 뇌-컴퓨터 인터페이스
    1.2 SpyKING CIRCUS 개요
    1.3 연구의 목적 및 해결 과제
  2 본론          5
    2.1 알고리즘의 전체 흐름
    2.2 MPI 기반 채널 병렬화
    2.3 Pruning 최적화
    2.4 메모리 최적화
    2.5 연산 최적화
      2.5.1 피크 검출 연산 최적화
      2.5.2 템플릿 거리 연산 최적화
  3 결론          12
    3.1 결과 분석
    3.2 기여 및 한계
    3.3 향후 연구 방향
  참고문헌        15
  Abstract        16
  ```
  → **3챕터, 본론에 5개 절, 마지막 절(2.5)만 sub-sub 구조**. 우리도 이 패턴
  그대로.
- **본 논문 분량**: 약 20페이지 (참고 thesis 의 약 1.4× 확장). 분배는
  §1 표 참고.
- **본문 언어**: **한글**. 그림 라벨/수치/인용 식별자는 영문 가능.
  마지막 페이지의 Abstract 는 **영문**.
- **논문 제목 (제안)**:
  - 한글: *투기적 뇌 시뮬레이터에서의 롤백 오버헤드 저감*
  - 영문: *Rollback Overhead Reduction in Speculative Brain Simulators*
    (포스터 제목 그대로 유지)
- **저자/소속**: 정희찬 (지도교수: 김장우). 서울대학교 컴퓨터공학부,
  고성능 컴퓨터시스템 연구실 (HPCS Lab).
- **출처 자료** (claim verification 용): **§0.5 Repo 구조 절** 에 전체 디렉토리
  트리 + baseline 수정 위치 (line 번호 포함) + 새로 추가된 파일 목록 + 파일
  찾기 가이드가 정리되어 있다. 모든 수치 인용은 §4 의 Key Numbers 표를 거쳐
  해당 출처 파일과 cross-check 한다.
- **작업 흐름**: 이 메모 §0 → §0.5 (repo 구조) → §2 (narrative) → §3 (챕터별
  본문 가이드) 순서로 통독 → 챕터별 본문 작성 시 수치는 §4 표에서, 그림은
  §5 인벤토리에서, 예상 심사 질문은 §6 에서 끌어 쓴다.

---

## 0.5 Repo 구조 및 baseline 수정사항 (GitHub 첨부 기준)

본 연구 자료는 GitHub repo **`ast07tp/NeuroSync_GradProj`** 로 Claude Project
에 첨부된다. 이 절은 (a) repo 디렉토리 구조, (b) baseline NeuroSync 에서
수정된 파일과 정확한 line 번호, (c) 본 연구가 새로 추가한 파일, (d) 자주
참조할 위치 가이드를 한곳에 정리한다.

### 0.5.1 디렉토리 구조

```
NeuroSync_GradProj/                ← repo 루트
├── CLAUDE.md                      프로젝트 컨텍스트 (사용자 설정 + 명령 안내)
├── research_memo.md               ★ 이 파일 (논문 작성 단일 브리프)
├── README.md, LICENSE             baseline 그대로
│
├── neurosync/                     시뮬레이터 코어
│   ├── Core.pyx                   ← 수정 (FSM 계측)
│   ├── RRManager.pyx              ← 수정 (롤백 logging + redo 분해)
│   ├── GlobalVars.py              ← 수정 (새 카운터 선언)
│   ├── Main.py                    ← 수정 (init + 결과 dump)
│   ├── Checkpoint.pyx, Init.pyx, Router.pyx, EnumList.pxd, Neuron.pyx, NoC.pyx (baseline)
│   └── setup.py                   Cython 빌드
│
├── runspace/                      시뮬레이션 결과 (전부 본 연구 산출)
│   ├── brunel_si/                 fixed-T sweep, Oracle 분석, Stage 4 step 출력
│   └── brunel_si_specgate/        redo_cyc / fsm_cyc 정밀 측정 (T=64, T=128)
│
├── benchmark/brunel_si/           새 워크로드 (Brian2 기반)
├── mapping/brunel_si/             Metis 매핑 (mapping_4100_64.npz)
│
├── example.cfg                    ← 수정 (brunel_si workload)
├── example_specgate.cfg           ← 신규 (redo_cyc 정밀 측정용)
├── example_v2.cfg                 ← 신규 (workload robustness 비교용)
├── run.py                         baseline 그대로 (오케스트레이션)
├── run_specgate.sh                ← 신규 (T=64/128 정밀 측정 runner)
├── run_T_sweep.sh                 ← 신규 (T=1..256 sweep runner)
│
└── research/                      본 연구의 모든 산출물 (코드·문서·그림)
    ├── STAGE4_FINDINGS.md         Stage 4 단일 진실원 (보조 reference)
    ├── outline.md                 영문 포스터 outline (보조)
    ├── STAGE3_*.md, MODIFICATIONS.md, research_roadmap.md
    ├── *.py  (14개)               분석/플롯 스크립트
    ├── paper/
    │   ├── 졸프포스터_정희찬_A1최종본.pdf   최종 포스터 (결론 reference)
    │   └── BS_Thesis_share.pdf              양식 reference (목차/구조만)
    └── result_img/                그림 PNG + CSV
```

### 0.5.2 Baseline NeuroSync 에서 수정된 파일 (5개)

모두 **순수 관찰 계측** (additive, non-invasive). cycle/spike 출력
byte-identical 검증 통과 (시뮬 거동 무변화). 각 추가 위치엔 `[research]`
마커 주석이 부착돼 있어 `grep -n "\[research" neurosync/*.{pyx,py}` 로
즉시 검출 가능.

| 파일 | line | 추가 내용 | 목적 |
|---|---|---|---|
| `neurosync/GlobalVars.py` | 35 | `rollback_events = None` | belated 이벤트 로그 컨테이너 |
| 〃 | 36 | `redo_cyc = None` | rollback_state 사이클 카운터 |
| 〃 | 37–38 | `redo_restore_cyc`, `redo_recompute_cyc` | redo 분해 카운터 |
| 〃 | 39 | `fsm_cyc = None` | FSM 6-state 카운터 |
| `neurosync/Core.pyx` | 72 | `cdef int entry_state` | 진입 상태 캡처 변수 |
| 〃 | 170 | `GV.redo_cyc[self.ind] += 1` | rollback_state 사이클 누적 |
| 〃 | 250 | `GV.fsm_cyc[self.ind][entry_state] += 1` | FSM 6-state 분해 |
| `neurosync/RRManager.pyx` | 91 | `cdef int _setup_consuming` | redo 분해용 snapshot 변수 |
| 〃 | 110–115 | `GV.rollback_events.append(...)` 한 줄 | belated 이벤트 로깅 (Stage1 #3 / Stage2 distance 분석의 원천) |
| 〃 | 119 | `_setup_consuming = self.rollback_consuming_cyc` | 복원/recompute 경계 snapshot |
| 〃 | 280–285 | `GV.redo_restore_cyc[ind] += _setup_consuming` 등 누적 | redo 분해 집계 |
| `neurosync/Main.py` | 66–69 | 새 카운터 4개 init | per-run 초기화 |
| 〃 | 119–124 | `rollback_events.dat` 파일 출력 | belated 이벤트 dump |
| 〃 | 126–148 | `redo_cyc.dat` 파일 출력 (TOTAL/DECOMP 라인 포함) | redo 분해 dump |
| 〃 | 149–164 | `fsm_cyc.dat` 파일 출력 (TOTAL/FRAC/CHECK 라인) | FSM 분해 dump |
| `example.cfg` | 전체 | workload_name=brunel_si, max_timestep=1971, setup_timestep=50, sync_period=[16] | 본 연구 표준 설정 |

**비침습 검증** (논문 §2.2 에서 인용 가능):
1. `multicore_spike_out_clean.dat` byte-identical
2. 코어별 `GV.cyc` 합 byte-identical (T=64 → 12,303,306 / T=128 → 22,956,017
   정확 재현 확인)
3. 내부 정합성 — `Σ fsm_cyc[ind] == GV.cyc[ind]`, `fsm_cyc[rollback_state]
   == redo_cyc`, `restore + recompute == redo_cyc` — 모두 True

### 0.5.3 본 연구가 새로 추가한 파일 (그룹별)

**(a) 워크로드 / 매핑** — 시뮬레이션 입력
- `benchmark/brunel_si/brunel_workload.py` — Brunel SI 생성 (Brian2,
  dt=0.1 ms, 4100 뉴런 = 3200 E + 800 I + 100 Poisson)
- `mapping/brunel_si/mapping_4100_64.npz` — Metis 64-core 매핑

**(b) 설정 + 실행 스크립트**
- `example_specgate.cfg` — `redo_cyc.dat` 출력용 설정 (specgate 변형)
- `example_v2.cfg` — workload robustness 비교 (시변 OU Poisson)
- `run_specgate.sh` — T=64/128 정밀 측정 자동 runner
- `run_T_sweep.sh` — T=1..256 sweep 자동 runner

**(c) 시뮬레이션 결과** — `runspace/`
- `runspace/brunel_si/SWEEP_total_cycles.txt` — fixed-T sweep 총합 (U-curve 원천)
- `runspace/brunel_si/stage3_oracle_results.txt`,
  `stage3_T256_decision.txt` — Oracle-A/B/C, T=256 pathological
- `runspace/brunel_si/stage4_step{2..7}_*.txt` — Stage 4 단계별 분석
- `runspace/brunel_si/stage4_redo_decomp.txt` — redo + FSM 분해 (이번 작업)
- `runspace/brunel_si_specgate/brunel_si_peri{64,128}_10pretrace_eng/{redo_cyc, fsm_cyc}.dat`
  — 계측 원시 출력 (논문 §2.2 표 직접 인용)

**(d) 분석/플롯 스크립트** — `research/` (14개)
- `oracle_analysis.py` — Stage 3 Oracle 천장 (A/B/C)
- `stage4_predict.py` — Stage 4 trace-driven 분석 (step 1–7: 입도, ACF,
  NoC 기하, A4 gate, 인과 진단, perceptron BP)
- `stage3_T256_decision.py` — T=256 pathological 검증
- `analyze_redo_decomp.py` — redo + FSM 분해 (이번 conversation 산출)
- `plot_stage2.py`, `plot_stage3_fixedT.py`, `plot_activity.py`,
  `plot_cycle_per16ts.py`, `plot_proxy_unusable.py` — 그림 생성
- `dump_proxy_csv.py`, `dump_dynamicT_csv.py` — PPT 차트용 CSV 추출
- (옛 워크로드용) `plot_cycle_per_128ts.py`, `plot_cycle_per_timestep.py`,
  `plot_speedup.py` — 본 연구 미사용 (참고용)

**(e) 문서** — `research/`
- `STAGE4_FINDINGS.md` — Stage 4 단일 진실원 (보조)
- `outline.md` — 영문 포스터 outline (보조)
- `STAGE3_ORACLE_DESIGN.md`, `STAGE3_PLAN.md`, `MODIFICATIONS.md` — 작업 메모
- `research_roadmap.md` — 로드맵 v2

**(f) 그림 + CSV** — `research/result_img/`
- `stage{2,3,4}_*.png` — 각 Stage 핵심 그림
- `poster_proxy_unusable.png`, `stage4_redo_decomp.png` — anchor 그림
- `proxy_temporal.csv`, `proxy_spatial.csv`, `dynamicT_per_block.csv` — PPT 차트 데이터

**(g) 포스터 + 양식 reference** — `research/paper/`
- `졸프포스터_정희찬_A1최종본.pdf` — 최종 포스터 (논문 결론과 일치 확인)
- `BS_Thesis_share.pdf` — **양식 reference (목차/구조만 참고, 내용 무관)**

### 0.5.4 파일 찾기 가이드

논문 작성 중 무엇을 어디서 찾는지의 단축 매핑:

| 찾는 것 | 위치 |
|---|---|
| 모든 수치의 출처 색인 | `research_memo.md` §4 표 |
| 그림 인벤토리 + §-배치 권고 | `research_memo.md` §5 |
| 예상 심사 질문 + 방어 답변 | `research_memo.md` §6 |
| 계측 위치 (line 번호) | 본 절의 §0.5.2 표 또는 `grep "\[research" neurosync/*.{pyx,py}` |
| 시뮬 측정 원시값 | `runspace/brunel_si_specgate/.../{redo_cyc, fsm_cyc}.dat` |
| Stage 별 분석 derivatives | `runspace/brunel_si/stage*.txt` |
| 그림 PNG | `research/result_img/stage{2,3,4}_*.png` |
| 포스터 결론 (consistency check) | `research/paper/졸프포스터_정희찬_A1최종본.pdf` |
| 양식 reference (목차만!) | `research/paper/BS_Thesis_share.pdf` |
| 시뮬레이터 코드 인용 (line 번호 포함) | `neurosync/*.{pyx,py}` |
| 분석 스크립트 (재현 / 검증용) | `research/*.py` |

---

## 1. 논문 메타 & 구조 매핑표

참조 BS thesis 와 1:1 대응하는 3챕터 구조:

| 페이지 | 챕터·절 | 한글 제목 | 분량(p) | 핵심 내용 |
|---|---|---|---|---|
| i | 초록 | 초록 (Korean abstract) | 1 | 한 페이지, 한글 |
| ii | 목차 | 목차 | 1 | 자동 생성 |
| iii | 그림목차 | 그림목차 | 1 | 자동 생성 |
| 1 | 1 | 서론 | 5 | — |
| 1 | 1.1 | 뇌 시뮬레이션과 SNN 가속기 | 1.5 | 동기 |
| 2 | 1.2 | NeuroSync 와 투기적 실행 | 2 | Baseline |
| 4 | 1.3 | 연구의 목적 및 해결 과제 | 1.5 | 가설·질문·기여 |
| 6 | 2 | 본론 | 11 | — |
| 6 | 2.1 | 전체 접근 흐름 | 1 | Methodology overview + 0-1-2-3 spine |
| 7 | 2.2 | 평가 환경 및 측정 인프라 | 2.5 | HW/workload/mapping/instrumentation |
| 9.5 | 2.3 | 직접 예측: Belated-Spike Predictor | 3 | Idea #1 |
| 12.5 | 2.4 | 간접 예측: Proxy Predictor | 2 | Idea #2 (activity + distance) |
| 14.5 | 2.5 | 예측 없는 균형: Dynamic T Balancing | 2.5 | Idea #3 |
| 14.5 | 2.5.1 | 고정 T sweep 및 U-곡선 | 1.5 | sub-sub |
| 16 | 2.5.2 | Oracle 천장 분석 | 1 | sub-sub |
| 17 | 3 | 결론 | 3 | — |
| 17 | 3.1 | 결과 분석 | 1.5 | 공통 원인 분석 (ISN + 7.5:1) |
| 18.5 | 3.2 | 기여 및 한계 | 0.5 | C1~C4 + 한계 |
| 19 | 3.3 | 향후 연구 방향 | 1 | 3 redirections + 미정 축 |
| 20 | 참고문헌 | 참고문헌 | 1 | — |
| 21 | Abstract | Abstract (영문, 1 페이지) | 1 | — |

---

## 2. 연구 narrative (척추)

### 한 단락 elevator (초록/서론·결론에 변형해 재사용)

NeuroSync 는 투기적(speculative) 멀티코어 SNN 시뮬레이터(HPCA'22 계열)로,
각 코어가 전역 동기화 주기 T 내에서 자유롭게 timestep 을 전진시키고,
**belated spike**(수신 코어가 이미 지나친 timestep 으로 도착한 원격
스파이크)가 인과율을 위반하면 체크포인트로 롤백하여 SNN 시뮬레이션을
가속한다. 본 연구는 NeuroSync 를 계측하여 **rollback + recovery 가
T=64(최적)에서 전체 사이클의 10.4%, T=128에서 18.1%** 를 차지함을 측정
정량화한 뒤, 이 손실을 회수할 수 있는 세 가지 논리적 경로를
**완전히 봉쇄**한다:
(i) belated spike 를 perceptron 으로 직접 예측 → **AUC 0.53–0.58** (동전던지기 수준);
(ii) 표면적 surrogate 신호(네트워크 활성도·NoC 기하)로 간접 예측 →
**R² = 0.09 / corr ≈ 0** (사용 불가);
(iii) 예측 없이 동적 T 로 균형 → 전지적 oracle 천장 **+1.99%** (무의미).
셋이 모두 실패하는 이유는 같다 — 워크로드의 **억제안정화(ISN) 항상성**
이 평활 캐스케이드를 만들어 예측기가 쓸 만한 모든 신호의 분산을 흡수하고,
**코어당 7.5:1 입도 불일치**(64개 뉴런이 한 timestep 공유 vs 평균
7.5개만 belated 피해)가 완벽 예측기조차 구조적으로 패배시킨다. 결론은
정직한 *한계 연구* (limits study) — rollback 예측은 ISN 워크로드에서
워크로드 본질적으로 불가능하며, 가속 노력은 "belated 예측" 에서
"recovery 비용 절감" 또는 "예측 가능한 것 예측" (링크 silence,
NoC 결정론적 전송 하한)으로 재배치해야 한다.

### 0-1-2-3 elimination spine (§2.1 의 핵심 anchor figure)

```
                 롤백 유발 latency 를 회수할 수 있는가?
                              │
            (0) 프로파일링: rollback = 10.4% @T=64
                                    18.1% @T=128   → 공격 가치 있음
                              │
        ┌─────────────────────┼──────────────────────────┐
   (A) Predict & avoid                    (B) No prediction — balance
        │                                          │
   ┌────┴────────┐                                 │
 (1) Proxy       (2) Direct                        │
network activity / belated spike                   │
NoC distance     itself                            │
   ↓                ↓                              ↓
R² = 0.09     AUC ≈ 0.53–0.58            Oracle-A only +1.99%
corr ≈ 0       FP : TP ≈ 5–6 ; 7.5 : 1
✗ unusable     ✗ unpredictable             ✗ negligible
        │                                          │
        └─────────────── ALL THREE CLOSED ─────────┘
                              │
              Root cause: ISN homeostasis +
                granularity mismatch (7.5:1)
```

### 본 논문의 자세 (committee-defensible framing)

- **한계 연구 (limits study)** 로 frame 한다. 실패한 엔지니어링 시도가
  아니라, 한계의 위치를 정량적으로 입증한 연구. 부정 결과 자체가 기여.
- **건설적 재배치**: belated 예측 대신 (a) recovery 비용 절감 (95%가
  recompute → 직접 lever), (b) 예측 가능한 것 예측 (링크 silence),
  (c) 결정론적 안전 투기 창(NoC 하한).
- **열린 축 명시**: energy 정량화 미완, 단일 워크로드 (Brunel SI) — 한계
  솔직히 기술 (3.2).

---

## 3. 챕터별 본문 작성 가이드

### 초록 (i 페이지)

**목표**: 1 페이지 한글. 본문 전체 압축. §2 의 한 단락 elevator 를
다듬어 사용. 마지막에 핵심 수치 3개(10.4%/18.1%, AUC 0.53–0.58,
+1.99%) + 결론 한 줄 + 키워드 5–7개.

**키워드 후보**: 투기적 실행, 스파이킹 뉴럴 네트워크, 뇌 시뮬레이션,
NeuroSync, 롤백 예측, 억제안정화 네트워크, 한계 연구.

---

### 1 서론 (5 페이지)

#### 1.1 뇌 시뮬레이션과 SNN 가속기 (1.5 페이지)

**목표**: SNN 의 정의와 뇌 시뮬레이션의 의의를 소개하고, 하드웨어
가속이 왜 필요한지 동기 부여.

**작성 가이드**:
- **SNN 이란**: 뇌의 뉴런이 시냅스를 통해 이산적 스파이크를 주고받는
  과정을 시간 지연(synaptic delay)과 함께 모델링한 신경망. 대규모 SNN
  시뮬레이션은 계산신경과학, neuromorphic 하드웨어 설계, 뇌영감
  학습기 연구의 기반이다.
- **왜 하드웨어 가속이 필요한가**: 수천만 timestep × 뉴런 업데이트와
  지연된 시냅스 이벤트를 처리해야 함. 소프트웨어 시뮬레이터(NEST, Brian2)
  는 매우 느림. 본 연구의 실측: **4100 뉴런짜리 작은 brunel_si 워크로드도
  최적 설정(T=64) 에서 197 ms 의 생물학적 시간을 시뮬레이션하는 데
  약 11.2 분의 wall clock 이 소모됨 → 실시간 대비 약 3,400배 느림**
  (§4 표 참고). 더 큰 네트워크는 지수적으로 더 느려진다.
- **시간 정밀 시뮬레이션의 본질적 병목 — 동기화 barrier**: 뉴런 사이의
  지연 때문에 코어 A 에서 생성한 스파이크가 코어 B 의 *과거* timestep
  에 영향을 줘야 할 수 있다. 안전한 방법은 매 timestep 전역
  동기화하는 것 — 그러나 빨리 끝난 코어가 느린 코어와 모든 in-flight
  스파이크가 도착할 때까지 대기. 시스템이 확장될수록 전체 사이클의
  ~79%가 낭비된다는 보고가 있음 (NeuroSync 논문의 baseline 측정).
- **투기적 실행(Time-Warp 계열)이 해법**: 각 코어가 동기 없이 일정 구간
  T 동안 자유 전진. 인과율 위반(belated spike)이 발생하면 롤백. 동기
  대기를 롤백 비용으로 trade off.
- **본 연구의 표적**: 투기적 실행이 동기 idle 을 줄이는 대가로
  지불하는 *롤백 비용* 자체를 다시 줄일 수 있는가? 그것이 본 논문의
  연구 질문.

#### 1.2 NeuroSync 와 투기적 실행 (2 페이지)

**목표**: 본 연구가 사용한 baseline 인 NeuroSync (HPCA'22) 시스템의
구조와 투기 메커니즘을 정밀하게 정의.

**작성 가이드**:
- **NeuroSync 소개**: 투기적 멀티코어 SNN 시뮬레이터의 cycle-accurate
  소프트웨어 모델. Python + Cython 구현. 오픈소스
  (`github.com/SNU-HPCS/NeuroSync`). 본 연구 설정: **4 chip × 16 core
  = 총 64 코어, 8×8 NoC mesh** (포스터 §8 매개변수 표 인용).
- **코어 내부 구조**: 각 코어는 State Engine (뉴런 막전위 동역학),
  Learning Engine (시냅스 가소성; brunel_si 에서는 STDP off),
  Router (NoC interface), Rollback/Recovery Manager 로 구성. 로컬
  체크포인트 메모리는 copy-on-write.
- **한 sync period T 의 코어 진행 루프** (포스터 §2 상단 다이어그램):
  1. State Update — 뉴런별 membrane dV/dt 계산
  2. Generate Spike — threshold 교차 시 스파이크 송신
  3. Wait & Receive — NoC 로부터 입력 시냅스 이벤트 수신·처리
  4. Learning — STDP weight update (brunel_si 에서는 비활성)
  - 위 4단계가 **T 개 timestep** 동안 투기적으로 반복 → 전역 sync barrier
    에서 체크포인트 commit 후 다음 주기 시작.
- **Belated spike 와 Rollback & Recovery 메커니즘** (포스터 §2 하단):
  - **Belated spike** ≡ 수신 코어가 이미 지나친 timestep 으로 도착한
    원격 스파이크 (`affecting_timestep < GV.timestep[receiver]`).
  - 감지 시 영향받은 뉴런을 체크포인트 timestep `t0` 로 되돌리고,
    `t0` 부터 현재 투기 위치까지 **재계산(recovery)**. 재계산 과정에서
    스파이크 산출이 바뀌면 anti-spike / new spike 가 하류 코어에 전파 →
    **2차 롤백** 가능.
- **FSM 6 상태** (`EnumList.pxd:90`): `neu_comp`(0, 투기 연산) /
  `neu_comp_end`(1, sync 요청 준비) / `sync_wait`(2, barrier 대기) /
  `commit`(3, 체크포인트 flush) / `sync_done`(4, 시냅스 전달·전진) /
  `rollback`(5, 롤백+recovery). 본론 §2.2 의 측정 인프라에서 다시
  정밀히 사용.
- **전역 sync 메커니즘**: 계층적 트리 구조 (`Init.pyx:16-72`,
  `Router.pyx:245, 261`). 리프 코어가 `sync_req` 를 상향 송신, 루트가
  전체 도착·in-flight 카운터 = 0 확인 후 `commit` 을 하향 broadcast.
  **본론 §2.3 의 global belated history HW 부담 추정 시 이 트리 인프라
  가 이미 존재함을 활용한다 — 추가 배선 0**.
- **T trade-off (U-curve, 본론 §2.5 에서 정량)**: T 작으면 sync/checkpoint
  오버헤드↑, T 크면 rollback 깊이·빈도↑. 정적 최적은 존재한다 (본 연구
  결과 T=64).
- **시간 이산화**: simulator 의 1 timestep = **dt = 0.1 ms** 의 생물학적
  시간 (`brunel_workload.py:53`). 시냅스 지연 D_DELAY = 15 timestep =
  1.5 ms. 막전위 시간상수 tau_mem = 20 ms, tau_exc = 5 ms, tau_inh = 10 ms.
  dt = 0.1 ms 는 가장 짧은 시간상수의 1/15 ~ 1/50 로, SNN 시뮬레이션
  표준값 (NEST, Brian2 기본값과 일치).
- **반드시 강조할 단위 구분**: *timestep* (생물 시간, 0.1 ms) vs *cycle*
  (HW 실행 단위) 은 다른 축이다. Δt 는 timestep 단위 (롤백 깊이),
  redo_cyc 은 cycle 단위 (HW 비용). 결코 혼용하지 않는다.

#### 1.3 연구의 목적 및 해결 과제 (1.5 페이지)

**목표**: 가설 → 측정 → 연구 질문 → 기여 → 본론 구조 안내.

**작성 가이드**:
- **가설**: 롤백 사이클은 잃어버린 latency. 그것을 예측해 회피하거나
  균형을 잡으면 그만큼 가속할 수 있다.
- **본 연구에서 처음 정량화한 핵심 측정**: NeuroSync 의 `rollback_state`
  사이클(= rollback + recovery) 비중 = **전체의 10.42% @T=64, 18.14%
  @T=128** (`redo_cyc.dat` TOTAL 행, 64 코어 합산). 공격 가치 있음.
  - **정밀 명시**: 이 10.4%/18.1% 는 이미 *recovery(재계산) 포함값*.
    NeuroSync 는 lazy recovery 모델 — 롤백 시 영향받은 뉴런이
    `rollback_state` 내부에서 Δt timestep 만큼 `state_update` 를 재실행
    하고, 매 재실행 사이클이 `redo_cyc` 에 누적됨. 본 연구의 분해:
    **T=64 에서 recompute 95.5% / restore 4.5%** (§4 표). 이 분해는
    energy 축 논의의 기반 (3.3).
- **연구 질문** (포스터 §3 그대로): *Can rollback be predicted, or
  balanced away, to convert latency loss into speedup?*
- **본 연구의 기여 (C1–C4)**:
  - **C1 Methodology**: 재시뮬 없이 trace + 계측만으로 투기 오버헤드를
    오라클 천장 + 예측가능성 + 정책 리플레이로 분해하는 재사용 가능한
    프레임워크.
  - **C2 Mechanistic negative result**: ISN(억제안정화 네트워크)
    항상성 → 평활 캐스케이드 → 예측 저항성. *워크로드 종류*에 대한
    명제이지 단일 예측기의 실패가 아님.
  - **C3 Architectural insight**: 코어/뉴런 입도 불일치(64 뉴런이
    timestep 공유 vs 평균 7.5개만 belated 피해 = **7.5 : 1 구조적 손실**)
    가 완벽 예측기조차 패배시킴. 예측 품질과 독립.
  - **C4 Design guidance**: belated 가 아닌 *예측 가능한 것* 을 예측.
    구체적 후보 3개는 3.3.
- **본론 구조 안내** (한 문단): 본론은 동일한 방법론(zero-re-simulation
  trace-driven)으로 (i) 직접 예측, (ii) 간접 예측, (iii) 예측 없는 균형
  세 경로를 차례로 닫는다. 셋 모두 닫힌 뒤 공통 원인을 분석한다.

---

### 2 본론 (11 페이지)

#### 2.1 전체 접근 흐름 (1 페이지)

**목표**: 본론 전체의 anchor 그림(0-1-2-3 spine)을 제시하고 평가
방법론을 한 페이지에 압축.

**작성 가이드**:
- **세 경로의 논리적 완전성**: 롤백 latency 손실을 회수하는 방법은
  논리적으로 다음 셋뿐 — (A-1) 표면 신호(activity / 거리)로 간접 예측,
  (A-2) belated 자체를 직접 예측, (B) 예측 없이 동적 T 로 균형. 본 연구는
  셋을 모두 trace 만으로 닫는다.
- **0-1-2-3 spine 그림** (§2 참고. 본론의 anchor 도해, 가능하면 페이지
  중앙 큰 그림 한 장).
- **방법론 한 단락**: 모든 분석은 **재시뮬 0회 trace-driven**. 입력은
  (i) `rollback_events.dat` (T=64, T=128 각 1회 실행 시 캡처),
  (ii) `clean.dat` (시퀀스 검증용), (iii) `mapping_4100_64.npz`, (iv)
  계측 추가본 `redo_cyc.dat`/`fsm_cyc.dat`. 분석 도구: `research/oracle_analysis.py`
  (oracle 천장), `research/stage4_predict.py` (step 2–7: 입도 분해 / 시간
  자기상관 / 공간 기하 / A4 gate replay / 인과 진단 / perceptron BP),
  `research/analyze_redo_decomp.py` (FSM·redo 분해).
- **세 절(2.3, 2.4, 2.5)의 공통 평가 지표**: 분류 문제(예/아니오)에는
  **AUC**, 회귀 문제(연속값 예측)에는 **R² / Pearson r**, 절대 비용
  비교에는 **cycle 합**. AUC 와 R²/r 의 개념적 차이 및 본 연구에서
  부정의 기준선(AUC 0.5, r 0)이 동전 던지기에 해당한다는 설명은 각 해당
  절에서 상세화.

#### 2.2 평가 환경 및 측정 인프라 (2.5 페이지)

**목표**: 모든 후속 결과의 재현성·신뢰도를 떠받치는 평가 환경과 새로
추가한 비침습 계측을 한 곳에 모음.

**작성 가이드**:

- **하드웨어 플랫폼**
  - 64 코어 = 4 칩 × 16 코어/칩, 8×8 NoC mesh (Manhattan hop).
    Inter-chip 구분은 칩 ID (`chip = (gy//4)*2 + (gx//4)`).
  - 전역 sync = 트리 (root + 비-root). 리프 → sync_req 상향, 루트 →
    commit 하향 broadcast. **본 트리 인프라가 이미 존재한다는 사실이
    §2.3 의 global belated history HW 부담을 0에 가깝게 만드는 근거**.
  - *선택 이유*: NeuroSync HPCA'22 기준 구성과 일치. 내부/외부 칩 mass
    분리(25% intra / 75% inter)가 의미를 갖도록 충분히 큰 규모이면서,
    T 한 설정당 wall clock 13 분 안에 완주 가능.

- **워크로드 — Brunel SI**
  - 총 **4,100 뉴런** = 3,200 흥분성 + 800 억제성 (E/I = 4:1) + 100
    Poisson 자극 입력. 평균 발화율 ~5 Hz, 비동기 irregular 영역.
    STDP off (정적 시냅스; `plastic_all = np.zeros(...)`).
  - **dt = 0.1 ms** biological/timestep (brunel_workload.py:53).
    synaptic delay = 15 timestep (1.5 ms); tau_mem = 20 ms; tau_exc = 5 ms;
    tau_inh = 10 ms.
  - 시뮬레이션 길이 = **1971 timestep = 197.1 ms 생물학적 시간**
    (= 50 웜업 + 128 × 15 측정). 1971 로 정한 이유 = 분석 창이 정확히
    128-ts 블록 15개를 포함하고 (oracle 블록 분해와 일치), T=1 cooldown
    drain 구간(ts 1986–2000)을 배제하기 위함.
  - *선택 이유*:
    (a) SNN 분야 표준 벤치마크, 생물학적 유효성 검증됨.
    (b) **시간에 따라 출렁이는 활성도** (CV = 0.95) — 사용자 요건
        "활성도가 시간에 따라 높음↔낮음 반복" 을 충족.
    (c) **억제안정화** 특성 — 본 연구가 한계로 발견하는 ISN homeostasis
        를 *기본 정의로 갖는 워크로드*. 비-항상성 워크로드라면 예측
        한계 검증에 부적합 (찾으려는 한계 자체가 나타나지 않음).
  - *공개해야 할 한계*: 단일 워크로드 클래스. 비-항상성(burst /
    feedforward) 일반성은 미검증 (3.2 에서 명시).

- **뉴런-코어 매핑**
  - Metis 그래프 파티션, 코어당 평균 ~64 뉴런
    (`mapping/brunel_si/mapping_4100_64.npz`). 4100 gid 모두 정확히
    하나의 코어에 매핑됨이 verified (bijection assertion in
    `research/stage4_predict.py:load_gid2core`).
  - *선택 이유*: 인접 코어 간 spike 트래픽을 최소화하는 connectivity-aware
    파티션. SNN 매핑 문헌의 표준. 결과 재현 가능.

- **방법론 — 비침습 계측 (본 연구의 C1 방법론적 기여)**
  - 추가한 카운터 (모두 *순수 관찰*, 시뮬 로직 무변경):
    1. `GV.redo_cyc[ind]` — 코어가 `rollback_state` 에 있는 매 사이클
       증가 (`Core.pyx:170`). 롤백 + recovery 총 비용 측정.
    2. `GV.redo_restore_cyc` / `GV.redo_recompute_cyc` — `redo_cyc` 를
       복원(고정 2 cyc/event) vs 재계산(나머지)으로 분해 (`RRManager.pyx`
       에 snapshot/accumulator 추가). 본 연구가 처음 추가.
    3. `GV.fsm_cyc[ind][state]` — FSM 6 상태별 사이클. `Core.pyx:69`
       에서 entry_state 캡처, line 246 에서 누적. 본 연구가 처음 추가.
    4. `rollback_events.dat` — 매 belated 이벤트 (spiked_ts,
       affecting_ts, Δt, src_pid, is_anti, rollback_gid)
       (`RRManager.pyx:112`). 모든 trace-driven 분석의 원천.
  - **비침습 3중 검증** (반드시 보고):
    1. `clean.dat`(코어당 스파이크 발생 시퀀스) byte-identical 기준선
       동일.
    2. 코어별 `GV.cyc` 합 byte-identical 기준선 동일 (계측 전 백업
       `.bak_predecomp` 와 새 출력 비교 — T=64: 12,303,306, T=128:
       22,956,017 정확 일치).
    3. 내부 정합성 — `Σ fsm_cyc[ind] == GV.cyc[ind]`,
       `fsm_cyc[rollback_state] == redo_cyc`, `restore + recompute ==
       redo_cyc` — 모두 True (실측 확인).

- **§2.2 의 두 sub-sub 항목** (BS thesis 참조 양식의 2.5.1/2.5.2 패턴을
  본 절에 적용하지 *않고*, 참조 양식대로 sub-sub 는 본론의 마지막
  절(2.5)에만 둔다. 본 절의 내용은 평탄하게 작성).

- **본 절에서 발생한 핵심 측정값(§4 표 참조)**:
  - 전체 cyc 의 FSM 분해 (T=64): neu_comp 10.6% / neu_comp_end 4.1% /
    sync_wait 2.4% / commit 0.01% / sync_done **72.6%** / rollback 10.4%.
  - 같은 분해 (T=128): 10.0 / 5.4 / 2.3 / 0.01 / **64.2** / 18.1%.
  - **해석 (1.3 절 결론 보강용)**: 90% 의 대부분은 hidden overhead 가
    아니라 *실제 SNN 연산*. neu_comp 는 뉴런 막전위 업데이트, sync_done
    의 대부분은 시냅스 이벤트 전달 처리(`process_synapse_events()`
    가 매 사이클 시냅스 이벤트 1개를 popleft 해 가중치를 목적 뉴런에
    적용). 진짜 *idle 대기* (`sync_wait`) 는 2.3–2.4% 뿐.
  - **sync_done 이 실연산임의 결정적 증거 — T-독립성**: T=64 (barrier
    31회) sync_done 85.7M vs T=128 (barrier 15회) 81.2M. barrier 가 2배인
    데도 5% 차이뿐 → idle 이 아니라 T-무관한 시냅스 처리량이 지배.
    barrier idle 이 컸다면 T=64 가 T=128 의 약 2배여야 함.
  - 즉 NeuroSync 의 투기 메커니즘은 이미 비-투기 baseline 의 ~79% 낭비를
    sync_wait 2.4% 로 줄였고, 남은 speculation 비용은 거의 전부
    rollback (10.4%/18.1%) 으로 응축됨. 이 절이 후속 세 절(2.3–2.5)의
    공격 대상의 크기를 확정.

#### 2.3 직접 예측: Belated-Spike Predictor (3 페이지)

**목표**: belated spike 자체를 perceptron 으로 직접 예측. **AUC 0.53–0.58**
의 결과와 그 의미를 정밀하게 입증.

**작성 가이드**:

- **예측 대상과 입도 정당화**
  - 대상 = (목적지 코어 dst_core, timestep) 별 binary: "이 코어가
    이 timestep 에 belated 를 한 번이라도 받는가?" (±1).
  - **입도 선택 근거**: per-(코어, T-창) 단위로 잡으면 belated 발생률이
    0.97 (거의 모든 창이 ≥1회 belated) → 분류기가 항상 yes 만 찍어도
    AUC=0.5, *vacuous*. per-(코어, timestep) 으로 가면 발생률
    **0.284 (T=64) / 0.300 (T=128)** — 분류기 학습이 의미 있는
    비-degenerate 영역.

- **Perceptron predictor 설계 (Jiménez–Lin 계열 이상화)**
  - 코어별 가중치 벡터 + 편향. 매 사이클 입력 feature 벡터와의
    내적 → sign → 예측.
  - **이상화(idealized)** 측면: float 가중치, 클리핑 없음, 온라인 업데이트,
    entity-vectorized (실제 HW 보다 *유리하게* 줌). 그래도 안 되면
    *신호가 없는 것* — predictor 부족이 아님.
  - History depth H ∈ {4, 8, 16, 32, 64} 스윕.

- **입력 features (포스터 §5 그림 참조)**
  - **(a) Local History** — 코어 내부 Remote Spiking History 활용:
    NeuroSync 에 이미 존재하는 자료구조 (`Checkpoint.pyx:22`,
    `[src_pid × pos]` 비트맵으로 어떤 src 가 어느 sub-slot 에 도착했는지
    기록). 여기에 **"belated" 1 bit/entry 만 추가**. 기존 HistoryBufIndex
    enum (`EnumList.pxd:178-187`) 의 8 필드에 `history_belated` 하나
    추가 = 9 필드. 최소 침습 HW 변경.
  - **(b) Global History** — 전역 평균 belated rate, 기존 sync 트리로
    집계:
    - sync_req (상향) 페이로드에 **+1 bit** (이 코어가 이 주기에
      belated 봤는가) 추가
    - 루트에서 64개 평균 → commit (하향) 페이로드에 **+b bit** (entry
      너비, e.g., 8-bit)
    - 코어별 GHR (Global History Register) 길이 G = 64 슬롯 보관
  - **HW 부담 (매우 작음)**:
    - 코어당 GHR = G × b = 64 × 8 = **512 bit/core**, **칩 전체 4 KB**
    - NoC 패킷: sync_req +1 bit, commit +8 bit/entry — *기존 트리 재사용,
      신규 배선 0*
    - 기존 `src_spike_history` 비트맵 ≈ 25 Kbit/core = 1.6 Mbit/chip 의
      **약 0.3%** 추가 비용
  - *논문에서 강조*: global sync 트리가 *이미 존재*하므로 추가는
    페이로드 폭만 늘리면 됨. 새로운 broadcast 도메인 불필요.
  - *현실 차이 caveat*: 실제 HW 에서는 GHR 이 매 *sync period* 단위로만
    업데이트 가능 (매 timestep 아님). 분석에서는 timestep 단위 trace
    replay (이상화). 비용 동일, 입도만 거침.

- **실험 절차**
  - 재시뮬 0회. `rollback_events.dat` (T=64: 278,971 이벤트;
    T=128: 292,488 이벤트) + `mapping_4100_64.npz` 로 (코어, timestep,
    belated_yes/no) 시퀀스 구성.
  - `research/stage4_predict.py` step 7: entity-vectorized 온라인 perceptron,
    per-dst-core 가중치, local + global + kitchen-sink (원격 활성도)
    feature. H 스윕.
  - 기준선: majority (항상 no) + future-cheating static-rate (per-core
    평균 belated rate 를 미리 아는 *치트* 상한기).

- **결과 — AUC 0.53–0.58**
  - 모든 H 값에서 AUC ∈ [0.53, 0.58], **majority 대비 정확도 lift ≈ 0**.
  - 미래-치팅 static-rate 상한기조차 AUC ≈ 0.65 (T=64) 에 머무름.
  - 운영 가능한 임계 AUC ≈ 0.95 와 격차 매우 큼.

- **AUC 의 의미 (§2.1 에서 정의했어도 본 절에서 다시 1 문단 풀이)**
  - AUC = "양성 사례 하나와 음성 사례 하나를 무작위로 뽑았을 때 분류기가
    양성 쪽에 더 높은 점수를 줄 확률". 1.0 = 완벽 ranker, **0.5 =
    동전 던지기**.
  - 정확도(accuracy) 가 아닌 AUC 를 보고하는 이유 = 클래스 불균형.
    다수가 no-belated 이므로 "항상 no" 만 찍어도 정확도는 높음 — 사기.
    AUC 는 *순위* (분리력) 를 측정하므로 이 함정에 안 빠짐.

- **메커니즘 — 왜 신호가 없는가**
  - **시간축 (stage4_step3_autocorr.txt)**: per-link belated 이벤트의
    within-pair demeaned ACF ≈ 0. 직전값 회귀 R²_lastval = −0.9 (평균
    예측보다 *더* 나쁨). 결론: per-link belated 시계열은 fine scale 에서
    사실상 ~Poisson white noise.
  - **공간축 (stage4_step4_horizon.txt, §2.4 와 연결)**: corr(hop, Δt)
    = −0.007, mean Δt 가 hop 0~14 평탄, inter-chip ≈ intra-chip.
    Δt 는 sync 윈도 위치가 결정 (≈ T/2), 거리 무관.
  - **A4 gate offline replay (stage4_step5_a4gate.txt)**: 실현 가능
    예측기(last-block / EWMA / static-prior)로 stall 정책 리플레이 →
    net = **−68% ~ −344%** of ceiling, **FP : TP ≈ 5–6**, 통과선 +29.1%.
    오라클 (AUC=1.0) 만 통과.

- **§2.3 의 핵심 결정타 — Granularity 7.5 : 1 (= 기여 C3)**
  - 완벽 예측기를 가졌다 해도 NeuroSync 의 코어 구조 자체가 손실을 부른다.
  - **이유**: 코어당 64개 뉴런이 동일 `GV.timestep[ind]` 를 공유 → 코어가
    stall 하면 64개 전부 stall.
  - **per-timestep 측정 (stage4_step6_cause.txt)**: (코어, timestep) 에
    belated 가 발생할 때 평균 **7.5/64 (median 6/64)** 의 뉴런만 belated
    피해자. 나머지 ~88% 는 무관.
  - → 7.5명 살리려고 64명을 stall = **헛 stall : 보호 비율 = 56.5 : 7.5
    ≈ 7.5 : 1 구조적 손실**.
  - 코어가 belated 를 만나는 timestep 비율 = 30% (per-core stall 게이트는
    실효 T 붕괴).
  - 예측 정확도와 *독립*. 워크로드 무관 — 어떤 SNN 이든 sparse per-ts
    피해자가 있으면 동일하게 적용.

- **본 절 결론**: 직접 예측은 (i) 신호 부재 + (ii) 구조적 7.5:1 손실의
  이중 봉쇄로 실패. 단순한 예측기 부족이 아니라 *예측 가능성 부재*
  (perceptron 이상화에도 불구).

#### 2.4 간접 예측: Proxy Predictor (2 페이지)

**목표**: 표면적 surrogate 신호(네트워크 활성도, NoC 기하)로 롤백을
간접 예측 시도 → 둘 다 사용 불가 입증.

**작성 가이드**:

- **직관 (포스터 §6)**:
  > "더 많은 spike + 더 먼 거리 → 더 많은 belated"
  >
  > 시간축(activity) 과 공간축(distance) 으로 분리해 검증.

- **Activity Proxy (시간축)**
  - 질문: 16-ts 빈 단위 spike 수가 같은 빈의 rollback load (Σ Δt) 를
    예측하는가?
  - 데이터: `runspace/brunel_si/brunel_si_peri16_10pretrace_eng/`,
    분석창 ts 50–1971 → 120 빈.
  - **결과**: Pearson **r = +0.29**, **R² = 0.09** (선형 회귀). 큰
    activity-independent floor (intercept ≈ 18,426 Σ Δt/빈).
  - **R² 정의 (1문단)**: 회귀에서 R² = 종속변수(rollback load) 분산 중
    독립변수(spike count) 가 설명하는 비율. R² = 0.09 → 활성도가 롤백
    변동의 9% 만 설명, 91% 미설명. 단일 변수 선형 회귀에서 R² = r².
  - **평활 캐스케이드** (C2 ISN homeostasis 의 *경험적 지문*):
    - 빈당 spike CV = **0.95** (입력 수준 출렁임)
    - 빈당 rollback load CV = **0.40** (평활됨)
    - 빈당 cycle 비용 CV = **0.16** (거의 평탄)
    - "신호가 한 단계 전파될 때마다 분산이 빨아들여짐" — 재귀 억제
      피드백의 정량적 지문. 3.1 결과 분석의 가장 강한 시각적 증거가 됨.

- **Distance Proxy (공간축)**
  - 질문: src_core → dst_core 의 NoC hop 거리가 rollback 깊이 Δt 를
    예측하는가?
  - 토폴로지: 8×8 mesh, Manhattan hop. (src, dst) 쌍은
    `rollback_events.dat × mapping_4100_64.npz` 에서 도출.
  - **결과**: `corr(hop, Δt) = −0.007` (T=64) / **−0.002** (T=128). mean
    Δt 는 hop 0–14 에서 사실상 **평탄** (T=64: ≈ 35, T=128: ≈ 67, 모두
    ≈ T/2). inter-chip ≈ intra-chip.
  - **r 을 쓰고 R² 를 안 쓴 이유 (1문단 방어)**: 관계가 사실상 0 이므로
    r = −0.007 이 방향(미세하게 음)까지 보존해 더 정직. R² (= 0.00005
    ≈ 0.00) 은 부호를 잃고 "정확히 0" 처럼 보여 정보가 줄어듦. activity
    proxy 와의 비교를 위해선 R² = r² 변환 가능 (활성도 r = +0.29).
  - **해석**: Δt 는 sync 윈도 위치 (≈ T/2) 가 결정. 전송 거리가 아니라
    *전역 sync 시계* 가 깊이를 가른다. "멀리서 온 스파이크가 더 깊은
    롤백" 의 단순 직관이 ISN 메커니즘 때문에 어긋남.

- **본 절 종합**: 활성도 (R² = 0.09) 와 거리 (corr ≈ 0) 모두 사용 불가.
  §2.3 의 직접 예측 실패와 결합해 "롤백 예측" 의 양 측면이 동시에
  닫힌다.

#### 2.5 예측 없는 균형: Dynamic T Balancing (2.5 페이지, sub-sub 2개)

**목표**: 예측 없이 T 를 동적으로 조정해 균형 잡는 길의 천장을 측정.
참조 BS thesis 의 2.5.1 / 2.5.2 패턴 그대로 적용.

##### 2.5.1 고정 T sweep 및 U-곡선 (1.5 페이지)

- **접근**: 모든 T ∈ {1, 2, 4, 8, 16, 32, 64, 128} 에 대해 단일 시뮬
  실행 → 전체 cycle 측정.

- **결과 표** (`runspace/brunel_si/SWEEP_total_cycles.txt`):

  | T | Total cycles (단일 코어 등가) | vs T=64 |
  |---:|---:|---:|
  | 1 | 9,891,914 | 5.47× |
  | 2 | 5,743,497 | 3.18× |
  | 4 | 3,654,443 | 2.02× |
  | 8 | 2,602,320 | 1.44× |
  | 16 | 2,087,560 | 1.15× |
  | 32 | 1,854,170 | 1.03× |
  | **64** | **1,808,130** | **1.00 (최소)** |
  | 128 | 1,909,086 | 1.06× |
  | 256 | **pathological — 롤백 폭발 (killed)** | — |

- **U-곡선 형태**: 작은 T 에서 sync/checkpoint 폭증 (T=1 → T=64 비
  5.47×). 큰 T 에서 rollback 폭증 (T=128 → +5.6%). 최저 = **T=64**.
- **T=256 의 병리** (`stage3_T256_decision.txt`): 100% CPU 63분, ts1586
  에서 ≥ 4.58M cyc 한 블록 처리 못 함 → kill. 탐색 범위의 상한 경계.
- **실용적 결론**: **T = 16 → T = 64 의 baseline 재설정만으로 +15.5%
  속도 향상**. dynamic T 시도 전에 *정적 최적값 자체* 가 가장 큰 lever.

##### 2.5.2 Oracle 천장 분석 (1 페이지)

- **Oracle-A 정의**: 매 128-ts 블록에서 8개 T 중 가장 싼 것을 *자유롭게*
  선택, 전환 비용 0 가정. 어떤 실현 동적-T 알고리즘에 대해서도 strict
  upper bound (전지적·무비용 가정).
- **블록 분할**: 128 timestep × 15 블록 = 1920 timestep (ts 50–1970,
  분석창 전체).
- **결과**: Oracle-A 총합 = **1,772,784 cycle** = **+1.99%** speedup
  vs 고정 T=64 (`stage3_oracle_results.txt`).
  - 블록 입도 B=64 로 잘게 나눠도 +3.6%, 천장은 ~4% 에서 saturate.
- **블록별 최적 T 시퀀스 (`research/result_img/dynamicT_per_block.csv`)**:
  `[128, 64, 32, 128, 64, 32, 64, 64, 64, 64, 128, 64, 64, 64, 64]`
  - 분포: T=64 가 10/15 (67%), T=128 이 3/15, T=32 가 2/15.
- **핵심 narrative point — "최적 T 는 시간에 따라 바뀌지만 비용 차이가
  미세"**:
  - 5/15 (33%) 블록이 T=64 가 아닌 것이 최적 → dynamic T 의 *전제* 자체는
    경험적으로 참.
  - 그러나 best vs 2nd-best 의 비용 격차가 미세. 예: 블록 2 에서 T=32
    비용 = 113,435, T=64 비용 = 113,707 → **0.24% 차이**.
  - 결과: cost surface 가 T=64 근처에서 **shallow bowl** → 정확히 최적
    T 를 골라도 회수 가능한 사이클이 거의 없음.
- **실현 가능 알고리즘의 추가 손실**: Oracle-C (롤백 강도 예산 게이트)
  는 +1.99% 천장 중 **6.6% 만** 회수 → 실현 게인 ≈ **0.13%**.
- **결론**: dynamic T 는 *lever 가 아니다*. 작동하는 유일한 컨트롤은
  정적 최적 T=64.

---

### 3 결론 (3 페이지)

#### 3.1 결과 분석 (1.5 페이지)

**목표**: 셋이 모두 실패한 *공통* 원인을 분석. 본 논문의 가장 강한
지적 기여 위치.

**작성 가이드**:

- **세 실패의 재진술 (한 단락)**:
  - §2.3: perceptron AUC ≈ 0.53–0.58, lift ≈ 0, 7.5:1 구조적 손실.
  - §2.4: 활성도 R² = 0.09, 거리 corr ≈ 0.
  - §2.5: Oracle 천장 +1.99%, 실현 ~0.13%.

- **공통 원인 — ISN (Inhibition-Stabilized Network) homeostasis**
  - Brunel SI 는 흥분/억제 균형 재귀 네트워크. 흥분 활성이 올라가면
    억제가 자동으로 따라 올라 빠르게 누른다. *자동 온도조절기* 같은
    행동 — 입력 출렁임이 흡수되고 전체 활성은 평균적으로 일정 유지.
  - **평활 캐스케이드** (§2.4 의 CV 수치를 다시 인용):
    spike CV 0.95 → rollback CV 0.40 → cycle CV 0.16. 하류로 갈수록 분산
    감소. 피드백이 분산을 *세탁* 한다.
  - **반드시 명시할 nuance (심사위원이 질문)**: 워크로드는 *눈에 보이게
    출렁인다* (CV = 0.95, 블록별 최적 T 도 시간에 따라 다름). 평활
    캐스케이드가 "워크로드가 평탄" 이라는 뜻은 *아니다*. **거시 진동이
    미시 카오스를 감춘다** — 거시 집계는 리듬을 갖고, 개별 인과 이벤트
    (어떤 spike 가 어떤 rollback 을 일으키는지, 다음 belated 가 언제
    올지) 는 재귀 억제 피드백이 무작위화. 우리 세 접근은 모두 *미시*
    예측가능성을 필요로 했고 — 그것이 없다.

- **공통 원인이 세 길을 어떻게 죽이는가 (1대1 매핑)**:
  - **Proxy (§2.4)**: 활성도와 롤백 모두 출렁이지만 *함께* 출렁이지
    않음. 큰 activity-independent floor → 거시 상관 r=0.29 가 미시 인과를
    설명 못 함. 공간축: Δt 가 거리 무관, sync 윈도가 결정.
  - **직접 예측 (§2.3)**: per-link belated 가 시간적으로 white →
    Poisson. ACF ≈ 0 → 과거가 미래를 알려주지 않음. 어떤 강한 학습기도
    무력. perceptron 이상화 + kitchen-sink feature 에서도 AUC 0.58 천장.
  - **Dynamic T (§2.5)**: 거시 안정성 때문에 cost(T) 곡선이 T=64 근처에서
    shallow bowl. 어느 시점에서도 *극적으로* 좋은 T 가 없음 → 추출 가능
    신호 부재.

- **독립적 구조 실패 — Granularity Mismatch (§2.3 의 7.5:1 재인용)**
  - 예측 가능성이 완벽해도 코어 공유 timestep 구조가 stall 을 7.5:1 로
    낭비. ISN 논증과 독립. 어떤 워크로드에서도 sparse per-ts 피해자만
    있으면 동일.

- **포스터 §9 보조 요인 두 가지 (한 단락씩)**:
  - **미시 비선형성**: 개별 spike 발화 리듬 자체가 belated 와 무관하게
    매우 카오스. 거시 패턴만으로 *어느 spike 가 belated 될지* 예측 불가.
  - **실시간 NoC 라우터 contention 미모델**: 본 trace-driven 분석은
    deterministic hop latency 가정. 실제 HW 에서는 라우터 큐 contention 이
    도착 시간을 추가로 무작위화 → 예측 가능성을 *더 낮추는* 방향. 본
    한계 결과를 강화하면 했지 약화하지 않음.

- **결정적 한 문장 (boxed, 결론 anchor)**:
  > **항상성 SNN 워크로드에서 투기 천장은 예측기의 영리함이나 엔지니어링
  > 노력이 아니라 워크로드의 통계적 구조에 의해 결정된다.** ISN 항상성
  > (평활 캐스케이드) + 코어 입도 불일치 (7.5 : 1) 가 세 가속 경로를
  > 동시에 닫는다. 작동하는 유일한 control 은 **정적 최적 동기 주기
  > T = 64**.

#### 3.2 기여 및 한계 (0.5 페이지)

**기여 (포스터 C1–C4 박스 그대로)**:
- **C1 Methodology**: 재시뮬 0회 trace-driven 분해 프레임워크 (오라클
  천장 + 시공간 예측가능성 + 정책 리플레이).
- **C2 Mechanistic negative result**: ISN homeostasis ⇒ 평활 캐스케이드
  ⇒ 예측 저항성. *워크로드 클래스* 명제.
- **C3 Architectural insight**: 코어/뉴런 7.5:1 입도 불일치가 완벽 예측기
  도 패배시킴. 예측 품질 독립.
- **C4 Design guidance**: belated 가 아닌 *예측 가능한 것* 을 예측 (3.3).

**한계 (반드시 솔직히 기술 — limits study 의 정직함)**:
- 단일 워크로드 클래스 (Brunel SI). ISN 명제는 *이* 워크로드 클래스
  대상. 비-항상성 / 버스트 / feedforward 워크로드 일반성은 미검증.
- trace-driven 은 A1 feedback (stall 이 자코어 미래 spike 를 지연시키고,
  그것이 하류 belated 를 재타이밍) 을 모델링 안 함 → 본 연구의 static
  oracle 천장은 *과대평가* (편향 방향이 결론을 *강화* 하지 약화 안 함).
- Energy 축 정량화 미완 (cycle 단위 비용은 측정. RTL 전력 모델
  별도 필요). 단, recompute 가 redo_cyc 의 95% 라는 분해 결과는 recovery
  를 줄이면 latency 와 energy 가 동시에 감소함을 시사 — 3.3 의 lever 가
  energy 축에서도 유효할 강한 정황.
- NoC 라우터 contention 미모델 (3.1 에서 언급).

#### 3.3 향후 연구 방향 (1 페이지)

**핵심 메시지 (포스터 §10)**: "롤백 자체를 예측·감소시키기보다, 롤백
오버헤드를 자르는 하드웨어 설계로 방향 전환". 세 가지 구체 redirection:

1. **Recovery 비용 절감 — belated 예측 없이 recompute 자체 cheapen**
   - 근거: §2.2 의 redo 분해에서 recompute 가 redo_cyc 의 **95–97%**.
     restore 는 4.5–2.5% 뿐. 따라서 *예측 정확도와 독립*하게 recompute
     비용을 줄이는 HW 가 직접 lever.
   - 구체 후보: fine-grained per-neuron 체크포인트, 영향받은 dendritic
     compartment 만 incremental replay. trace-driven 으로 사전 검증
     가능 (`redo_recompute_cyc`, `rollback_events.dat` 의 Δt 분포 활용).

2. **예측 가능한 것 — per-link silence prediction**
   - 코어 간 spike 트래픽은 *희소*. 본 연구 측정: self-core 가 모든
     rollback 의 1.6% 뿐 (각 코어가 자기 자신에게 belated 보내는 비율).
     다수 링크-슬롯이 silent. local + remote spike history 가 "이 링크
     이번 주기엔 silent" 를 고-신뢰로 예측 가능 (예측 *대상의 정의*가
     예측 가능한 양).
   - 확신 가능한 silence prediction → 수신 코어가 그 링크에 대한
     checkpoint / sync 작업을 *생략* 가능 (sync/checkpoint elision).
     오예측 시 기존 rollback 으로 fall back. Net = f(silence 비율 ×
     정확도). 재시뮬 0 검증 가능 (`clean.dat` + `connection.npy`).

3. **토폴로지 보장 안전 투기 창 — deterministic NoC transit lower bound**
   - NoC 의 *최소* 전송 지연은 deterministic. K-hop 떨어진 코어가 보낸
     스파이크는 *그 전송 시간 이전에는 도착 불가* → 수신 코어는 그
     시간만큼은 **rollback 위험 0 으로 자유 전진** 가능 by construction.
     오예측 0.
   - HW 추가: 링크별 minimum-arrival 카운터. 투기를 그 카운터로
     게이팅.

**열린 축 명시 (반복)**:
- Energy 정량화: RTL 전력 모델 + idle-vs-recompute 에너지 치환 분석 필요.
- 일반성: 비-항상성 워크로드 (예: feedforward Poisson, sensory encoding
  패턴) 검증. 본 연구의 ISN 명제 *밖* 에서는 예측가능성이 살아 있을 수
  있음.

---

### 참고문헌 (20 페이지 분량 중 1 페이지)

필수:
1. H. Lee et al., "NeuroSync: A Scalable and Accurate Brain Simulator
   Using Safe and Efficient Speculation," HPCA 2022, pp. 633–647.
   *(baseline 아키텍처 + 79% 낭비 동기 motivation)*
2. N. Brunel, "Dynamics of Sparsely Connected Networks of Excitatory and
   Inhibitory Spiking Neurons," J. Comput. Neurosci., 2000.
   *(Brunel SI 워크로드 원전)*
3. D. A. Jiménez and C. Lin, "Dynamic Branch Prediction with
   Perceptrons," HPCA 2001. *(perceptron predictor 설계)*
4. D. R. Jefferson, "Virtual Time," ACM TOPLAS, 1985. *(Time-Warp /
   투기 병렬 시뮬레이션 계보)*
5. G. Karypis and V. Kumar, "A Fast and High Quality Multilevel Scheme
   for Partitioning Irregular Graphs," SIAM J. Sci. Comput., 1998.
   *(Metis 매핑)*

선택/보조:
6. M. Stimberg et al., "Brian 2, an intuitive and efficient neural
   simulator," eLife, 2019. *(워크로드 생성 프레임워크, dt=0.1ms
   표준화)*
7. T. P. Vogels et al., "Inhibitory plasticity balances excitation and
   inhibition in sensory pathways and memory networks," Science, 2011.
   *(ISN 항상성 배경 — 3.1 의 개념적 보조)*

---

### Abstract (마지막 페이지, 영문 1 페이지)

영문, 한 페이지. §2 elevator 의 영문판:

> NeuroSync is an HPCA'22-lineage speculative multicore SNN simulator
> that accelerates spiking neural network simulation by allowing each
> core to advance speculatively within a global sync period T, rolling
> back when a *belated spike*—a remote spike arriving after the receiver
> has already passed its target timestep—violates causality. By
> instrumenting NeuroSync we measure that **rollback and recovery
> consume 10.4 % of all cycles at the optimal T=64**, rising to
> **18.1 % at T=128**—a worthwhile acceleration target. We then close
> all three logical paths to reclaim this loss:
> (i) directly predicting belated spikes with an idealized perceptron
> predictor → **AUC 0.53–0.58** (essentially chance);
> (ii) predicting rollback via surrogate signals (network activity, NoC
> geometry) → **R² = 0.09 and corr ≈ 0**, both unusable;
> (iii) prediction-free balancing via per-block dynamic T → omniscient
> oracle ceiling of only **+1.99 %**.
> All three fail for one common reason: the workload's
> inhibition-stabilized (ISN) homeostasis produces a smoothing cascade
> that erases every signal a predictor could use, while an architectural
> **7.5 : 1 per-core granularity mismatch** defeats even a perfect
> predictor. The take-away is that rollback in homeostatic SNN workloads
> is workload-intrinsically unpredictable, and acceleration effort
> should redirect from "predict belatedness" to "cheapen recovery" or
> "predict the predictable."
>
> **Keywords**: Speculative Execution, Spiking Neural Networks, Brain
> Simulation, NeuroSync, Rollback Prediction, Inhibition-Stabilized
> Network, Limits Study.

---

## 4. Key Numbers 빠른 참조표

(모든 수치 출처 명시. 논문 인용은 반드시 이 표를 거쳐 검증.)

| 항목 | 값 | 출처 |
|---|---|---|
| 코어 / mesh / 뉴런 | 64 (4×16) / 8×8 / 4100 | example.cfg, brunel_workload.py |
| E / I / Poisson | 3200 / 800 / 100 | brunel_workload.py |
| Timestep (생물 시간) | dt = 0.1 ms | brunel_workload.py:53 |
| 시냅스 지연 | 15 ts = 1.5 ms | brunel_workload.py:36 |
| 막전위 / exc / inh τ | 20 / 5 / 10 ms | brunel_workload.py:65-67 |
| 시뮬 길이 | 1971 ts = 197.1 ms (=50 + 128×15) | example.cfg |
| Wall clock @T=64 | 11.2 분 simulate + ~2.4 분 init ≈ 13.5 분 | log file |
| **실시간 대비 slowdown** | **~3,400 ×** | 유도 (674.6 s / 0.197 s) |
| Mapping | Metis, ~64 뉴런/코어 | mapping/brunel_si/mapping_4100_64.npz |
| **redo_cyc T=64** | **10.42%** of total cycle | redo_cyc.dat TOTAL |
| **redo_cyc T=128** | **18.14%** of total cycle | redo_cyc.dat TOTAL |
| redo 분해 T=64 | restore 4.5% / recompute 95.5% of redo | redo_cyc.dat DECOMP |
| redo 분해 T=128 | restore 2.5% / recompute 97.5% of redo | redo_cyc.dat DECOMP |
| FSM 분해 T=64 | neu_comp 10.6% / sync_done 72.6% / rollback 10.4% / sync_wait 2.4% / neu_comp_end 4.1% / commit 0.01% | fsm_cyc.dat |
| FSM 분해 T=128 | 10.0 / 64.2 / 18.1 / 2.3 / 5.4 / 0.01 % | fsm_cyc.dat |
| 활성도 ↔ 롤백 (16-ts 빈) | r = +0.29, R² = 0.09 | plot_stage2.py |
| Activity-independent floor (intercept) | 18,426 (Σ Δt/빈) | dump_proxy_csv.py |
| 평활 캐스케이드 CV | spike 0.95 → rollback 0.40 → cycle 0.16 | stage2 outputs |
| 거리 ↔ Δt | corr = −0.007 (T=64) / −0.002 (T=128) | stage4_step4_horizon.txt |
| Δt 평균 | 35.4 ts (T=64) / 67.2 ts (T=128) ≈ T/2 | stage4_step4_horizon.txt |
| Δt vs hop 범위 | mean Δt 가 hop 0–14 에서 평탄 | stage4_step4_horizon.txt |
| Perceptron AUC | **0.53–0.58** (H=4..64 sweep) | stage4_step7_perceptron.txt |
| Belated rate per-(dst-core, ts) | 0.284 (T=64) / 0.300 (T=128) | stage4_step7_perceptron.txt |
| 미래-치팅 static-rate AUC 상한 | 0.65 (T=64) | stage4_step5_a4gate.txt |
| Per-link belated ACFdem | ≈ 0 | stage4_step3_autocorr.txt |
| Per-link R²_last-value | −0.9 (Poisson 신호) | stage4_step3_autocorr.txt |
| Per-timestep victim mass | mean 7.5 / median 6 of 64 | stage4_step6_cause.txt |
| Stall 손실 비율 (granularity) | **7.5 : 1** | stage4_step6_cause.txt |
| 코어 belated 만남률 | 30% of timesteps | stage4_step6_cause.txt |
| A4 gate 실현 net | −68% ~ −344% of ceiling | stage4_step5_a4gate.txt |
| A4 gate FP : TP | 5–6 : 1 | stage4_step5_a4gate.txt |
| A4 통과선 | +29.1% | stage4_step5_a4gate.txt |
| Fixed-T sweep T=1..128 | 9.89M, 5.74M, 3.65M, 2.60M, 2.09M, 1.85M, **1.81M**, 1.91M | SWEEP_total_cycles.txt |
| T=256 상태 | pathological — rollback explosion | stage3_T256_decision.txt |
| Oracle-A speedup vs T=64 | **+1.99%** (B=128) | stage3_oracle_results.txt |
| Oracle-A saturation 천장 | ~4% (B=64) | stage3_oracle_results.txt |
| Oracle-C 회수율 | 6.6% of +1.99% (실현 ~0.13%) | stage3_oracle_results.txt |
| 블록별 best T 시퀀스 | [128,64,32,128,64,32,64,64,64,64,128,64,64,64,64] | dynamicT_per_block.csv |
| Best T 분포 | T=64: 10/15, T=128: 3, T=32: 2 | dynamicT_per_block.csv |
| Best vs 2nd-best gap (block 2) | T=32 113,435 vs T=64 113,707 (0.24%) | dynamicT_per_block.csv |
| T=16 vs T=64 fixed-T speedup | 1.155× (T=64 가 +15.5% over T=16) | SWEEP_total_cycles.txt |
| Self-core rollback 비율 | 1.6% | stage4_predict.py:129-136 |
| Global History HW 부담 | 4 KB chip-wide (G=64, 8-bit) | derived |
| GHR overhead vs 기존 src_spike_history | ~0.3% | derived |

---

## 5. 그림 인벤토리 (논문 §-배치 안내)

모든 그림 `research/result_img/`. 포스터에 사용된 그림은 재사용, 일부는 thesis
layout 에 맞춰 재작성.

| 파일명 | 내용 | 권장 § 위치 |
|---|---|---|
| (신규) 0-1-2-3 spine 트리 | 본론 anchor 도해 | §2.1 |
| (신규) 한 sync period 타임라인 | 코어 내부 4단계 + barrier | §1.2 |
| `stage4_redo_decomp.png` | FSM 6-state 분해 + redo 내부 분해 (이번 작업 산출) | §2.2 |
| `stage2_brunel_si_rollback_intensity_T16_v1.png` | 롤백 강도 시계열 + cycle overlay | §2.2 또는 §2.4 |
| (신규) 평활 캐스케이드 화살표 도해 (CV 0.95→0.40→0.16) | C2 ISN 시각화 | §3.1 |
| `stage4_perceptron.png` | Perceptron H 스윕, AUC 0.53–0.58 | §2.3 |
| `stage4_a4gate_replay.png` | A4 gate replay, only oracle passes | §2.3 |
| `stage4_temporal_autocorr.png` | ACF dem ≈ 0, R²_lastval < 0 (Poisson 지문) | §2.3 또는 §3.1 |
| `stage4_cause_diagnosis.png` | per-ts victim mass (7.5:1) | §2.3 |
| `stage4_granularity_concentration.png` | 입도 분해 (per-src-core 가 옳음) | §2.3 |
| `poster_proxy_unusable.png` | activity + distance proxy 결합 2-panel | §2.4 |
| `stage2_brunel_si_rollback_vs_spike_scatter_T16_v1.png` | activity ↔ rollback scatter, R²=0.09 | §2.4 (좌) |
| `stage4_horizon_ceiling.png` | Δt × NoC hop (평탄), horizon cap 분석 | §2.4 (우) |
| `stage3_fixedT_total_cycles_with_T256.png` | U-curve + T=256 pathological | §2.5.1 |
| `stage3_brunel_si_fixedT_total_cycles.png` | U-curve (T=256 제외 깔끔 버전) | §2.5.1 (alt) |
| `stage3_oracleA_only_comparison_T256.png` | Oracle-A +1.99% | §2.5.2 |
| (신규) per-block best T 막대 차트 | dynamicT_per_block.csv 시각화 | §2.5.2 |
| `stage3_brunel_si_oracle_comparison.png` | Oracle A/B/C 비교 (보조) | §2.5.2 (선택) |

**작성자 참고**: 포스터의 그림 12개 (`research/paper/졸프포스터_정희찬_A1최종본.pdf`)
와 위 PNG 가 거의 1:1 대응. 새로 그릴 그림은 (a) 0-1-2-3 spine 트리,
(b) 한 sync period 타임라인 — 두 개만 필수. 평활 캐스케이드 화살표
도해는 옵션 (수치 박스로 본문 안에 넣어도 됨).

---

## 6. Defense Q & A (예상 심사 질문 + 방어 답변)

§3.1 / §3.2 의 논의 단락 씨앗으로 활용 가능.

**Q1. Perceptron AUC 0.53–0.58 은 통계적으로 0.5 보다 크다 — *어느 정도*
신호는 있지 않은가?**
> A. 통계적으로는 그렇다 (상한 0.58 은 표본 크기 기준 chance-level
> standard error 를 약간 초과). 그러나 *운영적 lift* 는 ≈ 0 — 다수결
> 베이스라인 대비 정확도 향상 없음. 그 미세 신호는 약한 단거리 자기상관
> 으로, A4 gate replay (§2.3) 에서 FP:TP ≈ 5–6, 실현 net 손실 -68%
> ~ -344% 로 무력화. **통계적으로 검출되지만 구조적으로 무용**.

**Q2. 활성도엔 R², 거리엔 r 사용 — 왜 통일 안 했는가?**
> A. R² = r² 이므로 변환 가능. 각 경우의 narrative 가 다르다:
> - 활성도: 약하지만 관계 있음 → R² (= "9% 설명") 가 예측력 metric 으로
>   자연스러움.
> - 거리: 관계 사실상 0 → r = −0.007 이 방향(미세 음)까지 보존, R²
>   (= 0.00) 은 "정확히 0" 으로 보여 정보 손실.
> 통일을 원하면 r 로: activity r=+0.29, distance r=−0.007. 결론 동일.

**Q3. "rollback 10.4%" 가 *recovery 포함값* 인가?**
> A. 그렇다 — 그리고 이것이 본 연구의 정량적 정정 한 가지. NeuroSync 의
> lazy recovery 모델: 롤백 시 영향받은 뉴런이 `rollback_state` 내부에서
> Δt timestep 재계산되고 모든 cycle 이 `redo_cyc` 에 누적. 분해 검증:
> **T=64 에서 95.5% 가 recompute, 4.5% 가 체크포인트 retrieve**. 10.4%
> 는 rollback + recovery 합산값이며, 분해 정합성 (restore + recompute
> == redo_cyc) 도 verified.

**Q4. 나머지 90% 의 hidden overhead 는 어디인가?**
> A. ~83% 는 *실제 SNN 연산* (neu_comp 10.6% 뉴런 막 업데이트 +
> sync_done 72.6% 시냅스 이벤트 전달). ~6.5% 는 비-롤백 sync 오버헤드
> (sync_wait barrier idle + commit + neu_comp_end). 나머지가 rollback.
> sync_done 이 실연산이라는 결정적 증거: T-독립 (T=64: 85.7M vs T=128:
> 81.2M, barrier 2배 차이에 5% 만 변화). barrier idle 이었다면 T=64 가
> 2배여야 함. *hidden overhead 박스는 존재하지 않음*.

**Q5. 왜 하필 Brunel SI? 결론이 이 워크로드에만 적용되지 않는가?**
> A. Brunel SI 선택 이유: (a) 생물학적 검증된 SNN 표준 벤치마크,
> (b) 가시적 진동 활성도 (CV=0.95, 시간적 변화 큰 워크로드 요건 충족),
> (c) **억제안정화 (ISN)** — 이것이 *root cause 로 발견된 성질*.
> 비-항상성 워크로드는 예측 한계의 *검증 자체가 안 됨*. 그렇다, C2
> ISN 명제는 *이 워크로드 클래스 대상* 명시적 한정 — 정확히 그것이
> C2 의 scope. 비-항상성 일반성은 §3.2 한계 + §3.3 future work.

**Q6. 더 강력한 예측기 (deep RNN, transformer) 라면 perceptron 이
실패한 곳에서 성공할 수 있지 않은가?**
> A. 가능성 낮음. 본 perceptron 은 *이상화* (float 가중치, 클리핑 없음,
> entity-vectorized 온라인) + kitchen-sink feature (local belated history,
> global average, remote activity) + H=64 까지 스윕. AUC 0.58 천장.
> 별개로 시간 자기상관 ≈ 0, 미래-치팅 static-rate 도 AUC 0.65 — 즉
> *치팅 정보까지 줘도* 운영 가능 AUC 불가. 신호 부재이지 약한 인코딩이
> 아님. 7.5:1 입도 손실은 오라클 (AUC=1.0) 도 구조적으로 패배시킴 →
> 예측 품질과 별개.

**Q7. 그냥 더 큰 T 로 sync 오버헤드를 amortize 하면 안 되는가?**
> A. Fixed-T sweep 에서 이미 T=128 에서 rollback 18.1%, 총 cycle T=64
> 대비 +5.6% 증가. T=256 은 pathological (rollback explosion → killed).
> U-curve 가 큰 T 쪽이 가파르고 비대칭 (rollback 깊이가 T 와 함께 자라
> 지만 sync 비용은 1/T 로만 감소). T=64 가 경험적 최적.

**Q8. dt = 0.1 ms 가 충분히 작은가? 이산화 자체가 artifact 를 만들 수
없는가?**
> A. dt = 0.1 ms 는 가장 빠른 시간 상수 (1.5 ms 시냅스 지연) 의 1/15,
> 가장 작은 막상수 (5 ms tau_exc) 의 1/50. SNN 시뮬레이션 표준값 (NEST,
> Brian2 기본). T 가 달라도 `clean.dat` (spike 출력) byte-identical
> 확인 — 이산화 artifact 없음.

**Q9. Trace-driven 분석은 한 T 의 trace 가 전체 동역학을 잡는다고
가정한다. 공정한가?**
> A. T=64 와 T=128 두 T 에서 trace 캡처 (운영 관심 영역 + U-curve
> 최적값 둘러쌈). 각각 모든 belated 이벤트 기록. 명시적 한계: A1
> feedback (stall 이 자코어 미래 spike 를 지연 → 하류 belated 재타이밍)
> 미모델. → static-trace oracle 이 per-core stall 천장을 *과대평가*.
> 편향 방향이 본 연구의 부정 결과를 *강화*하지 약화 안 함.

**Q10. 포스터 §9 가 NoC 라우터 contention 을 원인으로 언급. trace 는
정적 hop latency 만 사용 — gap 아닌가?**
> A. 그렇다, 그리고 그것이 결론을 *강화*. NeuroSync 본 구성은 deterministic
> per-hop latency. 본 분석은 깨끗한 정적 토폴로지를 본 것. 실제 HW
> 에서는 라우터 큐 contention 이 도착 시간을 추가 무작위화 → 예측가능성
> *더* 낮음. 모델링 안 한 이유: (a) 정적 분석만으로도 예측 경로 봉쇄
> 충분, (b) contention 모델링은 부정 결과를 *강화*만 함.

**Q11. 계측이 시뮬 거동을 안 바꿨다고 어떻게 보장하는가?**
> A. 3중 independent 검증:
> (i) `clean.dat` (스파이크 출력 시퀀스) byte-identical to baseline.
> (ii) 코어별 cyc byte-identical (T=64 redo 12,303,306; T=128 redo
> 22,956,017 — 계측 전 백업과 새 결과 정확 일치).
> (iii) 내부 정합성 — Σ fsm_cyc = cyc, fsm_cyc[rollback] = redo_cyc,
> restore + recompute = redo_cyc 모두 True.

---

## 7. 출처 파일 (truth set)

본 연구가 수정·작성한 코드 파일 (§2.2 Methodology 에서 인용):

| 파일 | 역할 |
|---|---|
| `neurosync/Core.pyx` | FSM (line 79–246); redo_cyc·fsm_cyc 계측 (line 170, 246) |
| `neurosync/RRManager.pyx` | rollback() (line 72–280); redo_restore/recompute 분해 |
| `neurosync/Checkpoint.pyx` | src_spike_history 비트맵 (line 22) — §2.3 local history feature 의 재사용 인프라 |
| `neurosync/Router.pyx` | sync_req (line 261), commit (line 245) — 전역 sync 트리 |
| `neurosync/Init.pyx` | init_sync_topology (line 16–72) — sync 트리 구축 |
| `neurosync/GlobalVars.py` | redo_cyc, redo_restore/recompute, fsm_cyc 선언 |
| `neurosync/Main.py` | per-T 실행 진입; redo_cyc.dat / fsm_cyc.dat 출력 (line 126+) |
| `research/oracle_analysis.py` | Oracle-A/B/C 천장, U-curve (Stage 3) |
| `research/stage3_T256_decision.py` | T=256 pathological 검증 |
| `research/stage4_predict.py` | Steps 1–7: 입도, ACF, horizon, A4 gate, cause, perceptron BP |
| `research/plot_stage2.py` | 활성도 ↔ 롤백 scatter, 평활 캐스케이드 CV |
| `research/plot_proxy_unusable.py` | 결합 activity + distance proxy 2-panel |
| `research/analyze_redo_decomp.py` | redo_cyc 분해 + FSM 분해 + 그림 |
| `research/dump_proxy_csv.py`, `research/dump_dynamicT_csv.py` | 포스터·논문용 CSV 추출 |

데이터 파일 (스키마 간략):
- `rollback_events.dat`: per-event `(spiked_ts, affecting_ts, Δt, src_pid, is_anti, rollback_gid)`. T=64: 278,971 events; T=128: 292,488 events.
- `clean.dat`: per-neuron spike list, ts-sorted, anti-cancelled pairs 제거.
- `redo_cyc.dat`: 코어별 `(ind, cyc, redo_cyc, restore, recompute)` 행 + TOTAL + DECOMP.
- `fsm_cyc.dat`: 코어별 6-state 분해 + TOTAL + FRAC + CHECK.
- `mapping_4100_64.npz`: Metis 출력, `node_list[core] = [gid, ...]`.
- `runspace/brunel_si/SWEEP_total_cycles.txt`: fixed-T sweep 총합.
- `runspace/brunel_si/stage3_oracle_results.txt`: Oracle 결과.
- `runspace/brunel_si/stage4_step{2..7}_*.txt`: 단계별 출력.

---

## 8. 작성자 주의사항

- **톤**: 자신감 있게, 정밀하게, 정직하게. 부정 결과가 기여. "원칙적으론
  X 가 될 수 있다" 식의 헷지를 증거 없이 쓰지 말 것 — 한계의 *위치*를
  확정하는 것이 논문의 임무.
- **수치 정확도**: 18.14% 를 18% 로, 1.99% 를 2% 로 반올림하지 말 것
  (섹션 헤더 제외). 심사위원이 cross-check.
- **명칭 일관성**: "Belated-Spike Predictor" (§2.3), "Proxy Predictor"
  (§2.4 — activity 와 distance 모두), "Dynamic T Balancing" (§2.5).
  포스터 §-라벨 그대로.
- **핵심 단위 구분 (심사 단골)**: *timestep* (생물 시간 0.1 ms) vs
  *cycle* (HW 실행 단위). Δt 는 timestep, redo_cyc 은 cycle. 절대
  혼용 금지.
- **7.5 : 1 결과가 가장 강한 단일 통찰** (C3). 워크로드-무관 (sparse
  per-ts victim 가진 어떤 SNN 도 동일), 아키텍처-특정 (NeuroSync 가
  *전체 코어* 가 아니라 *개별 뉴런* 만 롤백한다면 달라짐). §2.3 의
  소절 (5.6) 로 분리해 보여주고, §3.1 에서 다시 인용.
- **평활 캐스케이드 (spike 0.95 → rollback 0.40 → cycle 0.16)** 가
  C2 ISN homeostasis 의 가장 강한 경험적 지문. §3.1 의 anchor. 라벨된
  화살표 도해를 시각적으로 강조 고려.
- **한글-영문 혼용**: 본문 한글이지만 (i) 정확한 식별자 (Pearson r, R²,
  AUC, ISN), (ii) 코드 식별자 (`redo_cyc`, `rollback_state`), (iii)
  표준 영문 용어 (Time-Warp, Manhattan hop, perceptron) 는 그대로 사용.
  그림 라벨도 영문 유지 (포스터·코드 일치).
- **포스터와 일관**: 포스터 §1–10 의 narrative 와 결론 (모두 일치).
  논문에서 더 정밀히/풍부히 쓰되, 메시지를 *바꾸지 말 것*. 새로 추가된
  것은 §2.2 의 redo 분해 + FSM 분해 (이 세션 작업) — 이는 *논문에서
  처음 보고* 하는 정밀화 (포스터엔 미포함).
- **방어 가능성**: §6 의 11개 Q&A 가 발표·논문 심사 양쪽 대비. 답변
  골자를 본문에 미리 녹여두면 심사 시 따로 변호할 필요 줄어듦.

행운을 빕니다. 기여는 실재하고 증거는 견고합니다. 정직하게 쓰면
됩니다.
