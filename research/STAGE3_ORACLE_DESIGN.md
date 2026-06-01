# STAGE 3 — Oracle 알고리즘 설계 및 설명 (핵심 산출물)

> roadmap 3단계. "워크로드 전체를 아는 oracle 이 동적 T 를 적용했을 때, 고정 T 대비
> 전체 사이클을 얼마나 줄이는가(= 동적 T 의 이론적 최대 가속)" 를 **서로 다른 3가지 관점**
> 으로 정의·구현·측정한다. 본 문서는 *설계와 해석* 이 핵심이며, 수치는
> `oracle_analysis.py` 가 스윕 완료 후 채운다.

---

## 0. 공통 전제 — 왜 "per-block 고정-T 측정값"을 oracle 의 빌딩블록으로 쓸 수 있는가

1. **스파이크 트래픽은 T 불변**: NeuroSync 의 정확성 보장상 sync_period T 가
   무엇이든 *최종 스파이크 출력은 동일*하다(`CLAUDE.md` 정확성 검증). 즉 "언제 어떤
   뉴런이 발화하는가" 라는 워크로드 자체는 T 와 무관하고, T 는 오직 **투기 깊이 →
   롤백량 → HW 사이클**에만 영향을 준다.
2. **동기화 경계에서 상태가 확정**: 매 sync_period 마다 체크포인트/리싱크가 일어나
   경계 시점의 네트워크 상태는 well-defined. 따라서 워크로드를 블록으로 자르고
   "블록 b 를 고정 T 로 돌렸을 때의 사이클 cost[T][b]" 를 측정해, 블록마다 다른 T
   를 골라 이어붙이는 것은 **oracle 상한선의 표준 이상화**(블록 간 결합 0, 전환비용
   0 가정)다. 이는 STAGE3_PLAN.md 의 P1("자유 T 전환 상한")과 동일한 정의다.
3. **블록 = oracle 의 T 전환 단위**: 본 분석의 1차 블록폭 **B = 128 ts**
   (= 스윕 최대 T = 가장 거친 자연 sync 주기). 더 잘게 자르면 상한이 더 느슨(높은
   speedup)해지고 더 거칠면 B 단일고정에 수렴 → B 는 oracle 의 *결정 입도*
   파라미터임을 명시. 워밍업 `[0,50)` 은 투기 없음 → T 불변 구간이라 모든
   알고리즘에 동일 prefix 로 더해져 비교에 영향 없음.

> **메트릭**: "workload 전체 소요 사이클" = 각 실행 로그의 마지막 누적 `cyc` 값
> (ts 0→max 까지 총 HW cycle). oracle 총사이클 = warmup prefix + Σ_b (선택 T 의
> 블록 cost). 재구성합이 로그 최종 cyc 와 일치하는지 sanity check 한다.

---

## 1. Oracle-A — 구간별 최소-사이클 포락선 (Per-block min-cycle envelope)

**관점**: *전지적·무제약.* oracle 이 워크로드 전체의 per-block 사이클을 완벽히
알고, **블록마다 자유롭게 T 를 바꿔도 전환비용이 0** 이라고 가정한다.

**알고리즘**:
```
for each block b:
    T*(b) = argmin_T  cost[T][b]          # 그 블록에서 가장 싼 고정 T
oracle_A_total = warmup + Σ_b min_T cost[T][b]
```

**무엇을 한정하는가**: 동적 T 가 줄 수 있는 **이론적 최대(가장 느슨한 상한)**.
어떤 실제 예측기도 (a) 미래를 완벽히 알 수 없고 (b) 전환비용이 0 일 수 없으므로,
Oracle-A 의 speedup 을 절대 넘을 수 없다. → 동적 T 연구의 **천장**.

**해석 포인트**: Oracle-A speedup 이 작으면(예 <1.1×) 워크로드 자체가
"T 에 둔감" → 동적 T 의 여지가 구조적으로 작음을 뜻한다. 이는 Stage 0/2 의
**ISN 항상성·평활 캐스케이드**(스파이크 CV0.95→롤백 CV0.40→cycle CV0.16)와
직접 연결되는 핵심 해석 — 활성도가 흔들려도 cycle 이 평탄하면 per-block
최소 포락선도 고정-T 최소선에 가깝다.

---

## 2. Oracle-B — 전역 단일 최적 T (Global single best-T)

**관점**: *전지적이나 단일결정.* oracle 이 전체를 알지만 **워크로드 내내 단 하나의
T** 만 쓸 수 있다(전환 금지).

**알고리즘**:
```
T_global = argmin_T  total_fixed[T]         # 스윕 곡선의 최소점
oracle_B_total = total_fixed[T_global]
```

**무엇을 한정하는가**: "튜닝을 잘 한 고정 T" 의 한계. 사용자가 요구한
**"고정 T 의 최소 사이클"** 기준선이 바로 이것. 동적 T 의 진짜 이득은
*T=16 대비*가 아니라 **이 Oracle-B(최적 고정 T) 대비** 얼마나 더 줄이느냐로
평가해야 공정하다(동적 알고리즘이 단지 더 좋은 상수 T 를 흉내낸 것에 불과한지
구분).

**해석 포인트**: Oracle-A ≈ Oracle-B 이면 → "블록마다 바꿔봐야 더 좋은 상수 T
하나 쓰는 것과 거의 같다" → 동적 T 무용. Oracle-A ≪ Oracle-B 이면 → 시간적으로
최적 T 가 변한다 → 동적 T 유효. 이 격차(A–B gap)가 **동적 T 가 노릴 수 있는
실제 파이**다.

---

## 3. Oracle-C — 롤백거리 예산 게이트 (Rollback-budget gated, realizable-policy ceiling)

**관점**: *전지적이되 "배치 가능한 신호"로만.* 실제 예측기는 미래 사이클을 직접
볼 수 없다. 그러나 Stage 2 에서 동적 T 의 입력신호로 지목한 **롤백거리 강도
ΣΔt** 는 직전 주기에서 측정 가능하다. Oracle-C 는 "완벽한 롤백-인지 정책이
도달 가능한 천장"을 묻는다 — *직접 사이클 최소화가 아니라, 롤백 위험을 일정
예산 이하로 유지하면서 투기 깊이(T)를 최대화* 하는 규칙.

**알고리즘**:
```
intensity[T][b] = Σ Δt  (rollback_events.dat, spiked_timestep∈block b, 고정 T 실행)
for budget β in grid:
    for each block b:
        T_β(b) = max{ T : intensity[T][b] ≤ β }   # 예산 지키는 가장 깊은 투기
                 (없으면 최소 T)
    realized(β) = warmup + Σ_b cost[ T_β(b) ][b]
β* = argmin_β realized(β)        # oracle 은 최적의 단일 예산을 안다
oracle_C_total = realized(β*)
```

**왜 별개의 관점인가**:
- A/B 는 *사이클 자체*를 직접 최소화(예측기가 알 수 없는 양). C 는 *롤백거리*
  라는 **인과적으로 관측 가능한 대용신호**로 T 를 정함 → "현실적 정책의 상한".
- 자유도: B(단일 T) < **C(예산 1개 + 규칙)** < A(블록별 자유 T). 따라서
  `oracle_A ≤ oracle_C ≤ oracle_B` (사이클 기준, 작을수록 빠름)가 기대되며,
  C 가 A–B gap 의 **몇 %를 회수**하는지가 곧 "롤백신호 기반 동적 T 의 가망성".
- oracle 이 β* 를 안다는 것은 정당: oracle 은 완전한 hindsight 로 *정책
  파라미터 1개*를 최적화할 뿐(여전히 per-block 미래사이클은 직접 안 봄).
  → Stage 4(롤백강도→다음 T 알고리즘 3종) 의 **성능 상한·설계 표적**을 제공.

**해석 포인트**: intensity[T][b] 는 T 가 클수록 보통 증가(투기 깊을수록 롤백거리
누적↑). 예산 규칙은 이 트레이드오프를 직접 표현한다. β* 가 크면 "거의 항상 큰 T
허용" → 워크로드가 롤백에 관대, β* 가 작고 C≈A 면 "롤백신호만으로 거의 최적
스케줄 복원 가능" → Stage 4 예측기 강력한 정당화.

---

## 4. 비교·보고 방식

| 산출 | 내용 |
|------|------|
| 표 | 각 고정 T 총사이클, T=16, Oracle-A/B/C 총사이클 + speedup(vs T=16, vs Oracle-B) |
| fig 좌 | 고정 T 곡선(log x) + Oracle-A/C 수평선 + Oracle-B 최소점 마커 |
| fig 우 | 시간축 per-block 선택 T 궤적(Oracle-A vs Oracle-C) — 동적 스케줄 가시화 |
| 저장 | `result_img/stage3_brunel_si_oracle_comparison.png`, `runspace/brunel_si/stage3_oracle_results.txt` |

**핵심 질문 3개** (결과로 답할 것):
1. A–B gap 이 의미있게 큰가? → 동적 T 의 존재 이유.
2. Oracle-C 가 gap 의 몇 %를 회수하는가? → 롤백신호 기반(Stage 4) 가망성.
3. 최적 고정 T(Oracle-B)는 T=16 대비 얼마인가? → baseline 재설정 필요성.

> robustness: 1차 B=128. 부차적으로 B=64 로도 oracle 재계산해 상한의 입도
> 민감도를 한 줄 보고(상한 정의의 한계 명시).
