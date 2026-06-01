import sys, os

sys.path.append("..")
from neurosync_api import *

# ===========================================================================
# Brunel SI-type workload  (졸업연구 Stage 0 — research_roadmap.md 0단계)
#
# 목표: 시간에 따라 네트워크 활성도가 높음 <-> 낮음으로 진동하고,
#       어떤 특정 상태로 수렴하지 않는, 신경과학적으로 유효한 워크로드.
#       => Brunel(2000) Synchronous Irregular(SI) regime:
#          - 개별 뉴런: 불규칙(irregular)하게 발화
#          - 집단(population) 발화율: 전역적으로 진동(synchronous)
#       이 진동이 롤백 강도의 시간적 변동을 만들어 동적 T 연구를 유효하게 함.
#
# 규모: example1(2080 뉴런) 대비 약 2x. 아래 KNOBS 한 줄 수정으로
#       손쉽게 스케일업 가능 (허용 상한 ~10x).
#
# SI 진동 튜닝 핵심 KNOB:  G(억제 우세도)↑,  D_DELAY(시냅스 지연)↑,
#                          EP_RATE(외부 구동) 조절
#   - 활동이 거의 침묵      -> EP_RATE↑  또는  I_DC↑
#   - 활동이 포화(항상 high) -> G↑  또는  EP_RATE↓
#   Stage 1에서 활성도 시계열을 시각화하며 위 KNOB을 조정한다.
# ===========================================================================

seed = 0
set_seed(seed)
network_gen_seed = seed

# ----------------------------- BRUNEL SI KNOBS -----------------------------
N_E      = 3200            # 흥분성 뉴런 수
N_I      = 800             # 억제성 뉴런 수            (Brunel 표준 4:1)
EPSILON  = 0.05            # 연결 확률 -> 뉴런당 입력 in-degree C = EPSILON * N
G        = 7.0             # 억제 우세도 g = |J_inh| / J_exc  (6→7: 지속 SI 위해 상향)
J_EXC    = 0.15 / 1000.    # 흥분성 시냅스 가중치       (example1과 동일 스케일)
D_DELAY  = 15              # 시냅스 지연 [timestep]    (1.5 ms @ dt=0.1ms)

# 외부 구동 (Brunel 의 외부 흥분성 Poisson 입력)
NPE      = 100             # 외부 Poisson 뉴런 수 (흥분성)
NPE_CONN = 400             # Poisson 뉴런당 무작위 연결 수
EP_RATE  = 50 * Hz         # 외부 Poisson 발화율 (20→50: 지속 SI 위해 구동 강화)
I_DC     = 1 * mV / ms     # 뉴런별 상시 전류 (example1과 동일; Brunel 충실재현 시 0)
# ---------------------------------------------------------------------------

N   = N_E + N_I
C_E = int(round(EPSILON * N_E))
C_I = int(round(EPSILON * N_I))

############################################
# Define Network Parameters
############################################

dt = 0.1 * ms
simtime = 1. * s           # 상한값. 실제 실행 구간은 example.cfg 의 max_timestep 이 제한

init_simulation(dt = dt, simtime = simtime)

############################################
# Define Neuron Parameters  (DLIF, example1과 동일)
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

# same params for exc and inh
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
# Set Initial States
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
# Define External Stimulus (excitatory Poisson drive)
############################################

I = I_DC * dt
I_list = np.empty(n_sim, dtype=float)
I_list.fill(float((I / mV).simplified))

create_external_stimulus(num_exc_poisson_neurons = NPE,
                         num_inh_poisson_neurons = 0,
                         exc_poisson_rates = EP_RATE,
                         inh_poisson_rates = 10 * Hz,      # 미사용 (npi=0)
                         exc_poisson_conn = NPE_CONN,
                         inh_poisson_conn = 0,
                         weight_exc_conn = J_EXC,
                         weight_inh_conn = J_EXC,          # 미사용 (npi=0)
                         I_list = I_list)

############################################
# Define Synapse Parameters (TRIPLET; baseline 에선 비가소성이라 미사용)
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
# Construct Brunel sparse random recurrent network
############################################
# 각 post 뉴런은 흥분성 C_E개 + 억제성 C_I개를 무작위(중복 없이)로 입력받는다.
#   - exc 시냅스 가중치 = J_EXC
#   - inh 시냅스 가중치 = G * J_EXC   (부호는 시뮬레이터가 source 타입으로 처리)
#   - 지연 = D_DELAY (Brunel 처럼 균일),  학습 = 비활성(baseline)

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
plastic_all = np.zeros(src_all.shape[0], dtype=bool)   # baseline: STDP off

conn_list = list(zip(src_all.tolist(),
                     dst_all.tolist(),
                     w_all.tolist(),
                     delay_all.tolist(),
                     plastic_all.tolist()))

create_connections(connection = conn_list, parameters = syn_params)

end_simulation()

print("brunel_si: N=%d (E=%d, I=%d), C_E=%d, C_I=%d, recurrent synapses=%d"
      % (N, N_E, N_I, C_E, C_I, len(conn_list)))
