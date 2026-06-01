import sys, os

sys.path.append("..")
from neurosync_api import *
import neurosync_api as napi          # 모듈 전역 external_stimulus 접근용

# ===========================================================================
# Brunel SI-type workload  v2  (research_roadmap.md 0단계 — tail 평탄화 해결판)
#
# v1(brunel_workload.py) 대비 유일한 차이:
#   외부 Poisson 구동을 *균질(homogeneous)* → *시변(inhomogeneous)* 으로 교체.
#   공통 rate λ(t) 를 느린 OU(random-walk) 로 변동시켜, 외부 구동 자체가
#   전 구간 계속 출렁이게 함 → 네트워크 활성도가 비수렴·지속 변동(특히
#   1500ts↑ tail 평탄화 해소). 신경과학적으로도 자연 입력은 비정상(non-stationary).
#
#   v1 은 그대로 보존(롤백 가능). 본 스크립트는 benchmark/brunel_si/dataset 을
#   덮어쓰며, example_v2.cfg 로 실행 시 runspace/brunel_si_v2/ 에 결과 저장.
# ===========================================================================

seed = 0
set_seed(seed)
network_gen_seed = seed

# ----------------------------- BRUNEL SI KNOBS -----------------------------
N_E      = 3200            # 흥분성 뉴런 수
N_I      = 800             # 억제성 뉴런 수            (Brunel 표준 4:1)
EPSILON  = 0.05            # 연결 확률 -> 뉴런당 입력 in-degree C = EPSILON * N
G        = 7.0             # 억제 우세도 g = |J_inh| / J_exc  (retune 유지)
J_EXC    = 0.15 / 1000.    # 흥분성 시냅스 가중치       (example1과 동일 스케일)
D_DELAY  = 15              # 시냅스 지연 [timestep]    (1.5 ms @ dt=0.1ms)

# 외부 구동: 시변(OU) Poisson  --- v2 신규 KNOB ---
NPE      = 100             # 외부 Poisson 뉴런 수 (흥분성)
NPE_CONN = 400             # Poisson 뉴런당 무작위 연결 수
EP_MEAN  = 50.0            # 공통 rate λ(t) 평균 [Hz]
EP_MIN   = 12.0            # λ(t) 하한 [Hz]
EP_MAX   = 100.0           # λ(t) 상한 [Hz]
EP_TAU_TS = 300            # OU 시정수 [timestep] (network 고유주기 ~300보다 느린 envelope)
EP_STD   = 22.0            # λ(t) 정상상태 표준편차 [Hz] (큰 high<->low 변동 유도)
I_DC     = 1 * mV / ms     # 뉴런별 상시 전류 (v1과 동일)
# ---------------------------------------------------------------------------

N   = N_E + N_I
C_E = int(round(EPSILON * N_E))
C_I = int(round(EPSILON * N_I))

############################################
# Define Network Parameters
############################################

dt = 0.1 * ms
simtime = 1. * s           # 상한값. 실제 실행 구간은 cfg 의 max_timestep 이 제한

init_simulation(dt = dt, simtime = simtime)

n_ts  = int(round(float((simtime / dt).simplified)))   # 총 timestep 수 (=10000)
dt_s  = float((dt / s).simplified)                      # dt [초] (=1e-4)

############################################
# Define Neuron Parameters  (DLIF, v1과 동일)
############################################

r_ar_max  = 5. * ms
threshold = -50. * mV

tau_mem = 20 * ms
tau_inh = 10.0 * ms
tau_exc = 5.0 * ms
El   = -60 * mV
E_0  = El
reversal_vI = -80 * mV
reversal_vE = 0 * mV

decay_gE = 1. - 1. / float(tau_exc / dt)
decay_gI = 1. - 1. / float(tau_inh / dt)
decay_v  = 1. - 1. / float(tau_mem / dt)

neu_params = [{
    "r_ar_max"    : int(r_ar_max / dt),
    "reversal_vE" : float(reversal_vE / mV),
    "reversal_vI" : float(reversal_vI / mV),
    "decay_gE"    : float(decay_gE),
    "decay_gI"    : float(decay_gI),
    "decay_v"     : float(decay_v),
    "E_0"         : float(E_0 / mV),
    "E_L"         : float(E_0 / mV),
    "model"       : "DLIF"
} for _ in range(2)]

############################################
# Set Initial States  (v1과 동일)
############################################

n_sim = N

vm_list = float(El / mV) + float((threshold - El) / mV) * np.random.rand(n_sim)
vm_list = np.asarray(vm_list, dtype=float)
gE_list = np.zeros(n_sim, dtype=float)
gI_list = np.zeros(n_sim, dtype=float)
threshold_list = np.empty(n_sim, dtype=float)
threshold_list.fill(float(threshold / mV))
type_list = [0 if i < N_E else 1 for i in range(n_sim)]
type_list = np.asarray(type_list, dtype=np.uint8)

state_dict = [{
    "v_t"       : vm_list[gid],
    "gE_t"      : gE_list[gid],
    "gI_t"      : gI_list[gid],
    "threshold" : threshold_list[gid],
    "neu_type"  : type_list[gid]
} for gid in range(n_sim)]

create_neurons(num_exc_neurons = N_E,
               num_inh_neurons = N_I,
               initial_states  = state_dict,
               parameters      = neu_params)

############################################
# Define External Stimulus  (먼저 균질로 생성 후 spike train만 시변으로 교체)
############################################

I = I_DC * dt
I_list = np.empty(n_sim, dtype=float)
I_list.fill(float((I / mV).simplified))

create_external_stimulus(num_exc_poisson_neurons = NPE,
                         num_inh_poisson_neurons = 0,
                         exc_poisson_rates = EP_MEAN * Hz,
                         inh_poisson_rates = 10 * Hz,      # 미사용 (npi=0)
                         exc_poisson_conn = NPE_CONN,
                         inh_poisson_conn = 0,
                         weight_exc_conn = J_EXC,
                         weight_inh_conn = J_EXC,          # 미사용 (npi=0)
                         I_list = I_list)

# --- v2 핵심: 균질 Poisson spike train 을 시변(OU) Poisson 으로 덮어쓰기 ---
# 공통 rate λ(t): OU 과정 (모든 Poisson 뉴런이 공유 → coherent network 변조)
sigma_step = EP_STD * np.sqrt(2.0 / EP_TAU_TS)
lam = np.empty(n_ts, dtype=np.float64)
lam[0] = EP_MEAN
for k in range(1, n_ts):
    lam[k] = lam[k-1] + (EP_MEAN - lam[k-1]) / EP_TAU_TS \
             + sigma_step * np.random.randn()
    if lam[k] < EP_MIN: lam[k] = EP_MIN
    elif lam[k] > EP_MAX: lam[k] = EP_MAX

p_t = lam * dt_s                                    # timestep별 발화확률 (rate[Hz]*dt[s])
draws = np.random.rand(NPE, n_ts) < p_t[None, :]    # 뉴런별 독립 Bernoulli, 공통 λ(t)
new_spikes = [[int(x) for x in np.flatnonzero(draws[n])] for n in range(NPE)]

assert len(napi.external_stimulus["poisson_neurons"]["spikes"]) == NPE
napi.external_stimulus["poisson_neurons"]["spikes"] = new_spikes
napi.external_stimulus["poisson_neurons"]["external"] = True

############################################
# Define Synapse Parameters (TRIPLET; baseline 비가소성)
############################################

gmax = 0.3 / 100.
tau_stdp = 20 * ms
tau_stdp_triplet = 100 * ms
alpha = (3 * Hz * tau_stdp * 3).simplified
eta = 2e-2 / 2000
eta_triplet = 2e-3 / 2000

decay_stdp = 1. - 1. / float(tau_stdp / dt)
decay_triplet = 1. - 1. / float(tau_stdp_triplet / dt)

syn_params = {
    "decay_stdp"    : decay_stdp,
    "decay_triplet" : decay_triplet,
    "alpha"         : float(alpha),
    "eta_stdp"      : float(eta),
    "eta_triplet"   : float(eta_triplet),
    "gmax"          : float(gmax),
    "rule"          : "TRIPLET"
}

############################################
# Construct Brunel sparse random recurrent network (v1과 동일)
############################################

J_INH = G * J_EXC

src_chunks, dst_chunks, w_chunks = [], [], []
for post in range(N):
    pre_e = np.random.choice(N_E, C_E, replace=False)
    pre_i = N_E + np.random.choice(N_I, C_I, replace=False)

    src_chunks.append(pre_e)
    dst_chunks.append(np.full(C_E, post, dtype=np.int64))
    w_chunks.append(np.full(C_E, J_EXC, dtype=np.float64))

    src_chunks.append(pre_i)
    dst_chunks.append(np.full(C_I, post, dtype=np.int64))
    w_chunks.append(np.full(C_I, J_INH, dtype=np.float64))

src_all = np.concatenate(src_chunks).astype(np.int64)
dst_all = np.concatenate(dst_chunks).astype(np.int64)
w_all   = np.concatenate(w_chunks).astype(np.float64)
delay_all   = np.full(src_all.shape[0], D_DELAY, dtype=np.int64)
plastic_all = np.zeros(src_all.shape[0], dtype=bool)

conn_list = list(zip(src_all.tolist(),
                     dst_all.tolist(),
                     w_all.tolist(),
                     delay_all.tolist(),
                     plastic_all.tolist()))

create_connections(connection = conn_list, parameters = syn_params)

end_simulation()

_tot = sum(len(s) for s in new_spikes)
print("brunel_si_v2: N=%d (E=%d,I=%d) syn=%d | OU Poisson λ∈[%.0f,%.0f]Hz "
      "μ=%.0f τ=%dts | poisson spikes=%d (mean %.1f/neuron)"
      % (N, N_E, N_I, len(conn_list), lam.min(), lam.max(),
         EP_MEAN, EP_TAU_TS, _tot, _tot / NPE))
