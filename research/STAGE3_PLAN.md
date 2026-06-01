# STAGE 3 PLAN — oracle 상한선 (durable; /compact·/clear 안전용)

> 이 파일 + CLAUDE.md + MODIFICATIONS.md 로 컨텍스트 정리 후에도 Stage 3 재개 가능.

## 목표 (roadmap 3단계)
워크로드 전체를 아는 oracle 이 동적으로 T를 바꾸면, 고정 T=16 대비
**workload 전체 소요 사이클**을 얼마나 줄이는지(이론적 최대 가속) 측정.

## 워크로드
brunel_si **v1**(`brunel_workload.py`, G=7/EP=50 균질). 스윕 전 v1 dataset 재생성 필수
(현재 dataset 가 v2일 수 있음 — `run_T_sweep.sh` step0 이 처리).

## STEP 1 — 고정 T 스윕 (실행중/실행대기)
- 드라이버: `run_T_sweep.sh` (백그라운드, **순차** 실행 → CPU thrash 방지).
- T = 1,2,4,8,32,64,128 순차 시뮬. **T=16 은 기존 `runspace/brunel_si/brunel_si_peri16_10pretrace_eng` 재사용**.
- 산출(durable): `runspace/brunel_si/SWEEP_total_cycles.txt`  (열: `T  final_ts  final_cyc`)
- 진행로그: `/tmp/sweep_progress.log` , per-T 실행로그 `/tmp/sweep_run_T<T>.out`
- per-T 결과: `runspace/brunel_si/brunel_si_peri<T>_10pretrace_eng/{log, rollback_events.dat, *.dat}`
- **메트릭 정의**: "workload 전체 소요 사이클" = 각 T 로그의 마지막 `... cyc <X>` 누적값(=max_timestep까지 총 HW cycle).

## STEP 2 — 그래프 (스윕 완료 후)
- x=고정 T(1,2,4,8,16,32,64,128 로그스케일), y=workload 전체 소요 사이클.
- 저장: `result_img/stage3_brunel_si_fixedT_total_cycles.png`
- 데이터 소스: `SWEEP_total_cycles.txt` + 기존 T=16 로그.

## STEP 3 — oracle 알고리즘 ≥3종 (스윕 완료 후, **설계·설명이 핵심**)
서로 다른 관점에서 최소 3가지 고안·설명 후 적용해 전체 사이클 측정, 고정 T=16·각 고정 T 와 비교(speedup).
후보 관점(데이터 확인 후 확정·정교화):
- (P1) **구간별 하한 포락선**: 고정-T 스윕의 per-block(예 128ts) 최소 cyc 합 = 자유 T 전환 상한.
- (P2) **롤백거리 예산 기반**: rollback_events.dat 의 Σdelta_t/구간을 알고, 구간별 "롤백예산 ≤ 임계" 유지하는 최대 T 선택.
- (P3) **전역 단일 최적 T**: 워크로드 전체에 최적인 단일 고정 T(=스윕 최소점) — 동적 oracle 의 보수적 하한/대조군.
- (P4 옵션) 비용모델 해석적 oracle.
- 저장: `result_img/stage3_brunel_si_oracle_comparison.png` + 수치 표.

## 상태 체크리스트  — ✅ STAGE 3 완료 (2026-05-18)
- [x] STEP1 스윕 완료 (SWEEP_total_cycles.txt: T=1..128 7행 + T=16 기존, all final_ts=1970 Done)
- [x] STEP2 그래프 (`result_img/stage3_brunel_si_fixedT_total_cycles.png`; U자형 최소=T=64)
- [x] STEP3 oracle 3종 설계·설명·적용·비교 ([STAGE3_ORACLE_DESIGN.md], `oracle_analysis.py`,
      `result_img/stage3_brunel_si_oracle_comparison.png`, `runspace/brunel_si/stage3_oracle_results.txt`)
- 핵심: best 고정T=64(vs T16 1.155×). Oracle-A(상한) vs best고정T = 1.020× (gap 1.95%),
  Oracle-C 는 gap 6.6%만 회수 → 동적T 천장 ~2%, ISN 항상성과 정합. baseline T16→T64 재설정 권고.

## 재개 방법 (컨텍스트 정리 후)
`cat runspace/brunel_si/SWEEP_total_cycles.txt` 와 `/tmp/sweep_progress.log` 로 STEP1 상태 확인 →
미완이면 대기, 완료면 STEP2(그래프)·STEP3(oracle 설계) 진행. CLAUDE.md 로드맵의 'Stage 3' 줄도 갱신.
