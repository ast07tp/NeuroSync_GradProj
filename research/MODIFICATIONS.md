# MODIFICATIONS — 코드/파일 수정 원장

> 규칙: 시뮬레이터/스크립트/cfg/워크로드를 건드릴 때마다 이 파일을 갱신.
> 이후 작업은 가급적 **복제 후 수정 + 새 이름 결과파일** 로 진행(롤백 용이).
> 원복은 git 기준(`git diff`, `git checkout <file>`).

## 시뮬레이터 (neurosync/) — Stage 1 롤백 계측

| 파일 | 변경 | 성격 |
|------|------|------|
| `neurosync/GlobalVars.py` | `rollback_events = None` 전역 추가 | additive |
| `neurosync/RRManager.pyx` | `rollback()` 내 `delta_t` 계산 직후, `GV.rollback_events`에 `(spiked_timestep, affecting_timestep, delta_t, src_pid, is_anti, rollback_gid)` append | **additive·non-invasive** — 로깅만, 롤백/상태 로직·시뮬 결과(spike 출력) 불변 |
| `neurosync/Main.py` | `init()`에서 `GV.rollback_events=[]`; `stat()`에서 `rollback_events.dat` 출력 | additive |

### Stage 3-B 롤백사이클 계측 (투기-게이팅 oracle 정밀 측정)

| 파일 | 변경 | 성격 |
|------|------|------|
| `neurosync/GlobalVars.py` | `redo_cyc = None` 전역 추가 | additive |
| `neurosync/Core.pyx` | `step()` 의 `rollback_state` 분기 진입 시 `GV.redo_cyc[self.ind] += 1` (해당 분기 1회 진입 = line 242 `GV.cyc+=1` 로 1 HW cyc 소모) | **additive·non-invasive** — 순수 관찰, FSM·`rollback_consuming_cyc`·`GV.cyc`·spike 출력 불변 |
| `neurosync/Main.py` | `init()`에서 `GV.redo_cyc=[0..]`; `stat()`에서 `redo_cyc.dat`(per-core cyc·redo + TOTAL redo_frac) 출력 | additive |
| `example_specgate.cfg` | **신규**. `result_folder_name=brunel_si_specgate`(runspace 분리, Stage3 `runspace/brunel_si` 보존), `workload_name=brunel_si`(v1 dataset·mapping 재사용) | 신규 |
| `run_specgate.sh` | **신규**. T=64/128 순차 재실행 드라이버(step0 없음=v1 dataset 재사용, sed로 sync_period 치환) | 신규 |

- ✅ 검증완료(non-invasive): specgate T=64 log `cyc=1,808,130`·T=128 `cyc=1,909,086` 모두 Stage3 값과 **정확 일치**, `clean.dat` 스파이크 **바이트 동일**. 계측 신뢰 확정.
- ✅ 결과: `redo_frac`(= rollback_state 사이클/전체 = 완벽 stall-oracle 천장) **T=64 10.42%, T=128 18.14%**(코어별 균일 9.4–11.8 / 17.2–19.8%). 해석추정(9/17%) 초과. 결합(stall+큰T)≈12.6%.
- 산출(durable, 신규): `runspace/brunel_si_specgate/brunel_si_peri{64,128}_10pretrace_eng/{log,redo_cyc.dat,multicore_spike_out_*.dat,...}` (서브폴더 prefix=workload_name=`brunel_si`, result_folder_name 아님)

### Task1 — 고정 T=256 + 글로벌 동적-T 사망진단

| 파일 | 변경 | 성격 |
|------|------|------|
| `stage3_T256_decision.py` | **신규**. oracle_analysis 재사용, T=256 포함 fixed-T 그래프 + Oracle-A only 비교 + 동적-T 포기 판정 | 신규 분석 |
| `/tmp/chain_T256.cfg` (example.cfg sed) | `sync_period[16]→[256]`, result_folder=brunel_si → `runspace/brunel_si/brunel_si_peri256...` (원본 example.cfg 불변) | 일시 |

- T=256: **병리적**(rollback-explosion, 100%CPU 63min, ts1586/1971서 cyc≥4,578,669, >31min/block 무진척 → kill). Oracle-A 후보서 제외(완료 T 1..128 만으로 포락선).
- 판정: per-block 최적 T∈{1..128}(B=128) = 1.773M = 최적고정T(=64) 대비 **+1.99% (≤5%)** → **글로벌 동적-T 깔끔히 폐기**. 신본선 = 코어별 speculative-advance+예측 stall.
- 산출(durable): `result_img/stage3_fixedT_total_cycles_with_T256.png`, `result_img/stage3_oracleA_only_comparison_T256.png`, `runspace/brunel_si/{brunel_si_peri256_10pretrace_eng/,stage3_T256_decision.txt}`

→ `.pyx` 변경 후 `cd neurosync && python3 setup.py build_ext --inplace` 필요(run.py도 복사본 재컴파일).

## 설정 / 워크로드

| 파일 | 변경 |
|------|------|
| `example.cfg` | `result_folder_name`/`workload_name`=`brunel_si`, `sync_period=[16]` (사용자: `max_timestep=1971`) |
| `benchmark/brunel_si/brunel_workload.py` | **신규** Brunel SI 워크로드. **retune: `G` 6→7, `EP_RATE` 20→50Hz** (지속 진동). 그 외 KNOB(N_E3200/N_I800/EPSILON0.05/D15) 유지 |

## 분석 스크립트 (루트, 신규 생성)

| 파일 | 역할 | 비고 |
|------|------|------|
| `plot_activity.py` | Stage 1: #1 발화생성 / #3 belated 전달 시계열 | 세션 중 in-place 재작성됨 → 이후엔 버전 분기 |
| `plot_cycle_per16ts.py` | log → 16-ts당 소모 cycle 시계열 | |
| `plot_stage2.py` | Stage 2: 롤백강도 vs time, +소모cycle overlay, spike↔롤백 상관/산점도 | |

## 산출물 (재생성 대상, result_img/)

`stage1_brunel_si_spike_timeseries_T16.png`, `stage2_brunel_si_rollback_intensity_T16.png`,
`stage2_brunel_si_rollback_vs_spike_scatter_T16.png`, `brunel_si_cycle_per16ts_T16.png`
런 산출: `runspace/brunel_si/brunel_si_peri16_10pretrace_eng/{log,err,multicore_spike_out_*.dat,rollback_events.dat}`

## v2 — 시변 외부구동 (tail 평탄화/ISN 검증)

| 파일 | 내용 |
|------|------|
| `benchmark/brunel_si/brunel_workload_v2.py` | **신규**. v1 복제 + 외부 Poisson을 공통 OU rate λ(t)∈[12,100]Hz(μ50,τ300ts) 시변으로 교체. 시뮬레이터·neurosync_api 무수정 |
| `example_v2.cfg` | **신규**. `workload_name=brunel_si`(dataset·mapping 재사용), `result_folder_name=brunel_si_v2`(runspace 분리, v1 보존) |

- ⚠️ **상태**: `benchmark/brunel_si/dataset`는 현재 **v2(OU)** 로 덮어써짐. v1 표준 복원 = `cd benchmark/brunel_si && python3 brunel_workload.py` 후 `run.py example.cfg`.
- 결과: `runspace/brunel_si`(v1)·`runspace/brunel_si_v2`(v2) 둘 다 보존. `result_img/*_v1.png`(표준)·`*_v2.png`(비교) 보존.
- 플롯 스크립트는 **무수정**(인자로 run_folder 전달). v2 그림은 v1 스크립트를 v2 폴더로 실행 후 `_v2`로 rename — 스크립트 복제 없이 롤백·비교 보존.
- 결론: v1≈v2 (CV 0.95→0.90, cycle CV 0.16 동일) → tail 평탄화는 ISN 항상성(본질), 결함 아님. 표준 워크로드는 v1.

## Stage 3 — oracle 상한선 (고정 T 스윕 + oracle 3종)

| 파일 | 역할 | 성격 |
|------|------|------|
| `run_T_sweep.sh` | **신규**. 고정 T=1,2,4,8,32,64,128 순차 시뮬(step0=v1 dataset 재생성). 결과 누적 cyc → `SWEEP_total_cycles.txt` | 신규 드라이버, 시뮬레이터 무수정 |
| `STAGE3_ORACLE_DESIGN.md` | **신규**. oracle 3종(A 포락선/B 전역단일/C 롤백예산) 관점·알고리즘·해석 설계문서 (산출 핵심) | 문서 |
| `plot_stage3_fixedT.py` | **신규**. STEP2: 고정 T vs workload 총사이클(로그 최종 cyc) 그래프 | 신규, 무수정 분석 |
| `oracle_analysis.py` | **신규**. STEP3: oracle A/B/C 적용·speedup·비교fig+표, B=64 민감도 | 신규, 무수정 분석 |

- 산출(durable): `runspace/brunel_si/SWEEP_total_cycles.txt`, `runspace/brunel_si/stage3_oracle_results.txt`,
  `result_img/stage3_brunel_si_fixedT_total_cycles.png`, `result_img/stage3_brunel_si_oracle_comparison.png`,
  per-T 런 `runspace/brunel_si/brunel_si_peri{1,2,4,8,32,64,128}_10pretrace_eng/{log,rollback_events.dat,...}`
- 시뮬레이터/cfg/워크로드 **무수정**. example.cfg 는 sed 복제(`/tmp/sweep_T*.cfg`)로만 T 치환 → 원본 불변.
- ⚠️ **dataset 상태 갱신**: 스윕 step0 가 `cd benchmark/brunel_si && python3 brunel_workload.py` 실행 →
  `benchmark/brunel_si/dataset` 는 이제 **v1(표준)** 상태(이전 v2 경고 해소). v2 필요시 `brunel_workload_v2.py`+`example_v2.cfg` 재실행.
- 결론: best 고정T=64. 동적T 천장(Oracle-A vs best고정T)=1.020×(gap 1.95%), Oracle-C gap 6.6% 회수
  → 동적화보다 **상수 T 재선정(T16→T64, +15.5%)** 이 핵심 레버. ISN 항상성 정합.

## Stage 4 — trace-driven 예측가능성 (A4 gate, 재시뮬 0회, 시뮬레이터 무수정)

| 파일 | 역할 | 성격 |
|------|------|------|
| `stage4_predict.py` | **신규**. step1 인프라 · step2 granularity · step3 시간자기상관 · step4 Δt×NoC+cap · step5 A4 gate(단위정합) · step6 원인진단(A1/A2/B, per-ts) · **step7 perceptron BP**(Jiménez–Lin, online, 이상화, per-ts 타겟). `mapping_4100_64.npz`+`rollback_events.dat`(T64/128)+`redo_cyc.dat` 만 read | 신규, **read-only 분석**(시뮬/cfg/워크로드 무수정) |
| `STAGE4_FINDINGS.md` | **신규**. 효과크기·무력원인·다음전략후보 단일 정밀 정리(다음 결정 근거) | 문서 |

- 산출(durable): `result_img/stage4_{granularity_concentration,temporal_autocorr,horizon_ceiling,a4gate_replay,cause_diagnosis}.png`,
  `runspace/brunel_si/stage4_step{2,3,4,5,6,7}_*.txt`, `result_img/stage4_perceptron.png`
- step6 원인진단(사용자 가설 검증): **A2 결정적**(per-ts victim 7.5/64, 헛정지:victim **7.5:1**, 코어 30% ts 강제정지) + B 보강(belated AUC causal 0.53≈무작위/cheat 0.65 약 = 내재적 예측불가) + A1 전제성립(corr victim↔source +0.10~+0.38, Step5 oracle 과대평가). → per-core stall 폐기 확정. BP 정확 재적용 3안 = `STAGE4_FINDINGS.md` §6.
- step7 perceptron BP 정면 확인: per-(dst-core,*ts*) 타겟(belated율 T64 0.284/T128 0.300, 비-degenerate)서 이상화 perceptron(local+global hist H4~64+kitchen-sink) **AUC 0.53–0.58·majority 대비 acc lift≈0** = 2-bit/last-value 동급, 컨닝 static(0.52)·usable BP(~0.95)에 못 미침 → '직접 belated 예측'(0-1-2-3 의 (2)) **airtight**(예측기 약함 아닌 신호 부재; A2 와 독립). 상세 `STAGE4_FINDINGS.md` §5-B.
- 단위 검증: event수 T64=278,971 / T128=292,488(헤더-1) 일치. redo_frac T64=0.1042/T128=0.1814 = Stage3-B 값 재확인.
  ⚠️ 분석 중 발견·수정한 버그: step5 초안이 64코어합산 `redo_cyc`를 단일코어 `CYC_T*`에 가산(단위 불일치, oracle net −173% 비현실값) → 무단위 천장-회수율로 전면 재작성(피드백 [[feedback-verify-data-granularity]] 적용).
- 결론: **A4 = FAIL(latency)**. 시간 forecasting≈0(Poisson), Δt⊥NoC기하, 실현 예측기 net 천장회수 −68~−344%(FP:TP≈5–6) ≪ 통과선 +29%. oracle 만 통과. 글로벌 동적-T 와 동일 근원(ISN 항상성). energy 축만 미정(추후). 다음 전략 = `STAGE4_FINDINGS.md` §4, 사용자 추후 선택.

## 문서/메모리

`CLAUDE.md`(현재단계·로드맵표 A4 FAIL 갱신), `research_roadmap.md`(§4 FAIL·§5/6 보류), `STAGE4_FINDINGS.md`(신규 단일진실원), `outline.md`(**신규** — 영문 연구 포스터 아웃라인 단일소스: limits-study 제목·0-1-2-3 척추·그림 인벤토리·핵심수치표; 타 LLM 포스터 생성용. 수치는 STAGE4_FINDINGS/roadmap/SWEEP와 정합 검증완, 그림 8개 경로 resolve 확인), `~/.claude/.../memory/`(피드백·프로젝트·인덱스)
