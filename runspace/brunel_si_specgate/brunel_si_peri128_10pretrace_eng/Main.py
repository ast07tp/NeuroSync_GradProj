import sys
import Core
import NoC
import GlobalVars as GV

import EnumList as EL
import numpy as np

import Init
import copy


from timeit import default_timer as timer


def init():
    workload_path = sys.argv[1] + "/"
    mapper_path = sys.argv[2]
    mapping_name = sys.argv[3]
    hw_mapping_name = sys.argv[4]
    GV.sim_params["chip_x"] = int(sys.argv[5])
    GV.sim_params["chip_y"] = int(sys.argv[6])
    GV.sim_params["max_core_x_in_chip"] = int(sys.argv[7])
    GV.sim_params["max_core_y_in_chip"] = int(sys.argv[8])
    GV.sim_params["max_syn_delay"] = int(sys.argv[9])
    GV.sim_params["max_sync_period"] = int(sys.argv[10])
    GV.sim_params["accum_width"] = int(sys.argv[11])
    GV.sim_params["max_timestep"] = int(sys.argv[12])
    GV.sim_params["num_pretrace_engine"] = int(sys.argv[13])
    
    GV.sim_params["setup_timestep"] = int(sys.argv[14])
    GV.sim_params["cur_sync_period"] = 1
    GV.sim_params["prev_sync_period"] = 1
    

    GV.sim_params["workload_path"] = workload_path
    GV.sim_params["history_width"] = GV.sim_params["max_syn_delay"] + GV.sim_params["max_sync_period"] + 2

    GV.sim_params["chip_num"] = GV.sim_params["chip_x"] * GV.sim_params["chip_y"]
    GV.sim_params["used_core_num"] = GV.sim_params["chip_num"] * GV.sim_params["max_core_x_in_chip"] * GV.sim_params["max_core_y_in_chip"]

    GV.sim_params["max_core_x_in_total"] = GV.sim_params["chip_x"] * GV.sim_params["max_core_x_in_chip"]
    GV.sim_params["max_core_y_in_total"] = GV.sim_params["chip_y"] * GV.sim_params["max_core_y_in_chip"]

    GV.neu_consts = [{} for _ in range(EL.NeutypeIndex.neutype_max.value)]
    GV.syn_consts = {}

    Init.init_network(workload_path + "network_parameter.npy")
    Init.load_stimulus(workload_path+"stimulus.npy")
    Init.load_constant(workload_path+"neuron_parameter.npy", workload_path+"synapse_parameter.npy")

    print("Start Connection Initialization\n")
    sys.stdout.flush()

    conn_list, neu_states = Init.load_connection(
        workload_path + "connection.npy",
        workload_path + "initial_states.npy",
        mapper_path + "/" + mapping_name,
        mapper_path + "/" + hw_mapping_name)

    print("End Connection Initialization\n")
    sys.stdout.flush()

    GV.NoC = NoC.NoC()
    GV.cyc = [0 for _ in range(GV.sim_params['used_core_num'])]
    GV.redo_cyc = [0 for _ in range(GV.sim_params['used_core_num'])]  # [research Stage3-B]
    GV.redo_restore_cyc = [0 for _ in range(GV.sim_params['used_core_num'])]    # [research Stage4-energy]
    GV.redo_recompute_cyc = [0 for _ in range(GV.sim_params['used_core_num'])]  # [research Stage4-energy]
    GV.fsm_cyc = [[0]*6 for _ in range(GV.sim_params['used_core_num'])]         # [research Stage4-energy] FSM 상태별
    GV.timestep = [0 for _ in range(GV.sim_params['used_core_num'])]
    GV.chkpt_timestep = [0 for _ in range(GV.sim_params['used_core_num'])]
    GV.cores = [Core.Core(ind, conn_list[ind], neu_states[ind]) for ind in range(GV.sim_params['used_core_num'])]
    Init.init_sync_topology()

    GV.spike_out = [[] for _ in range(GV.sim_params["total_neu_num"] + GV.sim_params["total_poisson_num"])]
    GV.rollback_events = []

    state_file = open("state.dat", "w")
    spike_file = open("multicore_spike_out_raw.dat", "w")
    GV.debug_list = {"spike" : spike_file, "state" : state_file}


def simulate():
    GV.sync_root.prev_time = timer()

    simulation_end = False
    counter = 0
    while not simulation_end:
        for core in GV.cores:
            core.core_advance()

        GV.NoC.noc_advance()

        for core in GV.cores:
            if GV.timestep[core.ind] >= GV.sim_params["max_timestep"]:
                simulation_end = True


def stat():
    if GV.debug_list["spike"]:
        for neu in range(GV.sim_params['total_neu_num'] + GV.sim_params['total_poisson_num']):
            GV.debug_list["spike"].write(str(neu) + ": " + str(GV.spike_out[neu]) + "\n")

    spike_out_clean = copy.deepcopy(GV.spike_out)
    for spike_out_per_neu in spike_out_clean:
        remove_spikes = []
        for spike_timestep in spike_out_per_neu:
            if spike_timestep < 0:
                assert (-spike_timestep in spike_out_per_neu)
                remove_spikes.append(spike_timestep)

        for remove_spike in remove_spikes:
            spike_out_per_neu.remove(remove_spike)
            spike_out_per_neu.remove(-remove_spike)
    f = open("multicore_spike_out_clean.dat", "w")
    for neu in range(GV.sim_params['total_neu_num'] + GV.sim_params['total_poisson_num']):
        f.write(str(neu) + ": " + str(spike_out_clean[neu]) + "\n")

    # [research] dump rollback-triggering belated spikes (Stage1 #3 / Stage2 distance)
    rb = open("rollback_events.dat", "w")
    rb.write("# spiked_timestep affecting_timestep delta_t src_pid is_anti rollback_gid\n")
    for ev in GV.rollback_events:
        rb.write(" ".join(str(x) for x in ev) + "\n")
    rb.close()

    # [research Stage3-B] per-core cycles spent in rollback_state (= wasted
    # speculation mass). 완벽 투기-게이팅 oracle 상한 = (Σcyc - Σredo) / Σcyc.
    # 계측은 순수 관찰(FSM·cyc·spike 출력 불변) → cyc 는 Stage3 동일 T 런과 일치해야 함.
    rc = open("redo_cyc.dat", "w")
    rc.write("# core_ind  cyc  redo_cyc(rollback_state)  restore_cyc  recompute_cyc\n")
    for ind in range(GV.sim_params['used_core_num']):
        rc.write("%d %d %d %d %d\n" % (ind, GV.cyc[ind], GV.redo_cyc[ind],
                                       GV.redo_restore_cyc[ind], GV.redo_recompute_cyc[ind]))
    tot_c, tot_r = sum(GV.cyc), sum(GV.redo_cyc)
    tot_restore, tot_recomp = sum(GV.redo_restore_cyc), sum(GV.redo_recompute_cyc)
    rc.write("# TOTAL cyc=%d redo=%d  redo_frac=%.6f  max_core_cyc=%d\n"
             % (tot_c, tot_r, (tot_r / tot_c if tot_c else 0.0), max(GV.cyc)))
    # [research Stage4-energy] redo_cyc 분해 검증: restore+recompute == redo (불변)
    rc.write("# DECOMP restore=%d recompute=%d  sum=%d  match=%s  "
             "restore_frac_of_redo=%.6f recompute_frac_of_redo=%.6f  "
             "recompute_frac_of_total=%.6f\n"
             % (tot_restore, tot_recomp, tot_restore + tot_recomp,
                str(tot_restore + tot_recomp == tot_r),
                (tot_restore / tot_r if tot_r else 0.0),
                (tot_recomp / tot_r if tot_r else 0.0),
                (tot_recomp / tot_c if tot_c else 0.0)))
    rc.close()

    # [research Stage4-energy] FSM 상태별 사이클 분해 (T 동안 소모 사이클이 어디로 가는가).
    #   0=neu_comp(유용연산) 1=neu_comp_end 2=sync_wait(idle barrier) 3=commit 4=sync_done 5=rollback
    names = ["neu_comp", "neu_comp_end", "sync_wait", "commit", "sync_done", "rollback"]
    fc = open("fsm_cyc.dat", "w")
    fc.write("# core_ind " + " ".join(names) + "\n")
    state_tot = [0]*6
    for ind in range(GV.sim_params['used_core_num']):
        fc.write("%d %s\n" % (ind, " ".join(str(x) for x in GV.fsm_cyc[ind])))
        for s in range(6):
            state_tot[s] += GV.fsm_cyc[ind][s]
    grand = sum(state_tot)
    fc.write("# TOTAL " + " ".join("%s=%d" % (names[s], state_tot[s]) for s in range(6)) + "\n")
    fc.write("# FRAC  " + " ".join("%s=%.6f" % (names[s], (state_tot[s]/grand if grand else 0.0))
                                   for s in range(6)) + "\n")
    fc.write("# CHECK sum_states=%d cyc=%d match=%s  rollback_state=%d redo_cyc=%d match_redo=%s\n"
             % (grand, tot_c, str(grand == tot_c),
                state_tot[5], tot_r, str(state_tot[5] == tot_r)))
    fc.close()


def run():
    init()

    print("Initialized Simulation States\n")
    sys.stdout.flush()
    
    simulate()

    print("Simulation Done\n")
    sys.stdout.flush()
    
    stat()

run()
