<configuration>

pretrace_engine = 10은 pre-trace를 병렬로 업데이트하는 엔진 개수
(하드웨어와 성능 트레이드오프)

Each core processes up to 128 neurons, 32,768 synapses, and 4,096 remote traces
example1 workload: 2080 neurons (mini Brunel)
ㄴexample_workload.py와 같이 이미 만들어진 // pip install brian2 이후 brian2로도 검증작업?

8 neurons per core & 256 core : N cycles, 10T wall time
130 neurons per core & 16 core: 2N cycles, T wall time
논문에선 64칩 64코어 총 4096코어로 고정: 추후 워크로드 커지면(ex. Full brunel) 반영

diff runspace/lazy/example1_peri1_10pretrace_eng/multicore_spike_out_clean.dat \
     runspace/lazy/example1_peri16_10pretrace_eng/multicore_spike_out_clean.dat
로 정확성 검증 가능
----------------------------------------------------------------------

발표자료 제작: 
1. 과제내용(주제: 뉴로싱크 시뮬레이터가 무엇인지 (SW 시뮬레이터인데, 하드웨어 시뮬레이션 시뮬레이터인가? / 그 시뮬레이터로 뭘 하려고 하는가?))
2. 현재까지 진행정도(논문 공부: 각 논문의 의의 / 데이터 추출 / 주제 선정 /시뮬레이터 코드 수정하여 예측기 제작중)
3. 앞으로 할일(시뮬레이터 수정 및 알고리즘 최적화 / workload 바꿔서 취약점 분석[푸아송 분포 뭐시기 - 이전 사이클의 롤백이 현재 사이클과 무관한 상황이 온다면?])

@config 설정 : 4칩 16코어, 총 64코어 : 코어당 약 32개 뉴런 관리

@그래프 그리기 : 잘 나오는지, 저장 경로와 저장 이름 체크

@tail -n 20 runspace/lazy/폴더이름/log
rm -rf runspace/lazy

@투기실행 시작조건과 종료조건
warmup before speculation: neuron network yet to be stabilized, rollback might explode
cooldown: 50 + 128*7 = 946, 50 + 128*15 = **1971**

@128 타임스탭 동안 평균 소모 사이클, 최고 최저 소모 사이클 분석하기 (웜업-시작-종료 구간은 제외)
평균적으로 제일 좋은 T 존재
특정 T의 최소 사이클이 평균에서 우월한 T의 최고 사이클보다 좋은 구간 존재
-> 정확한 T 조절은 반드시 이득으로 이어진다?

git status
git add .
git commit -m "중간 저장: NumPy 호환 수정, 시뮬레이션 실행 확인, 시각화 코드 추가

- fix: gen_submetis.py, Parse.py NumPy ragged array dtype=object 수정 (NumPy 1.24+ 호환)
- feat: plot_speedup_comparison.py 추가
- feat: plot_cycle_per_timestep.py 추가 (T 리스트 일괄 처리)
- feat: plot_cycles_per_128ts.py 추가 (warmup/cooldown 제외, 정규화 비교)
- data: runspace/lazy/ 시뮬레이션 결과 포함"

git push origin my-research


1971 사이클에 대해 데이터 싹 뽑기 (plot 3종류 그리기)
클로드코드 가동(재시작 요구)
클로드코드 셋업 (.md 파일 수정 / plan mode 설정)


뉴로싱크 핵심 내용 정리하기 (프리트레이스 엔진, 시뮬레이션 병목의 구성, 시뮬레이션 병목의 타파 방향)


동적 알고리즘 다루기: 어떤 데이터를 참고하는게 가장 타당한가? 
ㄴ 직관적으로는 rollback에 소모된 사이클 수 (inter core 통신이 필요하긴 함: 제일 느린 코어 기준으로)
ㄴ 소규모 네트워크에서는, 발화를 퍼셉트론 예측기로 예측하는 방식으로 global history를 보고 예측 가능할지도... 
(자신 제외 모든 뉴런이기에, example1 기준으로는 불가능)
근데, 발화가 이루어지면 사이클 소모 늘어나는건 맞아?(개념 빈약 상태)
언제 사이클 소모가 증가하는가? (코어간 롤백 명령 통신)



롤백 시점과 롤백 및 사이클 사이 관계 (제미나이 분석 참조 : 이거 예측이 되는 문제인가?)

시뮬레이터와 하드웨어 사이 관계 (조교님 졸업논문 확인하고 공부해보기)

동기화 주기 T를 맞추기 위해 하드웨어적으로 어떤 load가 추가되는가?
이러한 하드웨어 load 추가는 이 시뮬레이터에서 어디에 반영되었는가?
T-speculation이라는 기법 자체가 하드웨어에 대대적인 변화 야기. opus로, 코드 전반에 이 영향이 어떻게 표출되는지 확인받기

-------------------------------------------------------------------------------------

<주제 심화>

1. 예측
발화 예측을 높은 정확도로 하는 방법?
정확한 타이밍으로 예측한다면, 롤백 자체를 줄일 수 있다..?

결국 근본적으로 예측을 해야 T를 조절하는게 의미가 있다?

2. 국소적 / 투표


3. 워크로드의 차이에 따른 동기화 주기
수면& 마취 시 워크로드와 활발한 움직임 와중 워크로드의 사이클 및 롤백 패턴 분석,


