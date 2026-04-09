"""
plot_cycle_per_timestep.py
--------------------------
역할:
    지정한 T 값 목록 각각에 대해 timestep별 사이클 소모 그래프를 개별 파일로 저장합니다.
    - 파란 선(좌측 Y축): 각 timestep에서 소모된 증분 사이클 수 (부하 변동 파악)
    - 빨간 선(우측 Y축): 누적 사이클 수 (전체 진행 추이)

사용법:
    python3 plot_cycle_per_timestep.py

출력:
    {SAVE_DIR}/Cycle_per_Timestep_T{T값}.png  (T 개수만큼 생성)
"""

import os
import re
import matplotlib.pyplot as plt

# ================================================================
# [설정] 실험 환경에 맞게 아래 값들을 수정하세요
# ================================================================
T_VALUES     = [1, 2, 4, 8, 16, 32, 64, 128, 256]   # 분석할 T 값 목록
PRETRACE_ENG = 10                                # pretrace_engine 값
WORKLOAD     = "example1"                        # 워크로드 이름
RUNSPACE_PATH = "./runspace/lazy_doubled_timestep/"               # 실험 결과 폴더 경로
SAVE_DIR     = "./../result_pictures/"              # 그래프 저장 경로
# ================================================================


def parse_log(log_path: str):
    """
    log 파일에서 timestep별 사이클 정보를 파싱합니다.

    log 파일 한 줄 형식:
        {current_timestep} / {max_timestep} ... cyc {cumulative_cycles}, elapsed {time} (s)
    예시:
        992 / 992 ... cyc 1234567, elapsed 3.14 (s)

    Returns:
        timesteps         : 각 기록 시점의 timestep 번호 리스트
        cumulative_cycles : 누적 사이클 수 리스트
        incremental_cycles: 직전 기록 대비 증분 사이클 수 리스트
    """
    if not os.path.exists(log_path):
        return None, None, None

    with open(log_path, "r") as f:
        lines = f.readlines()

    timesteps          = []
    cumulative_cycles  = []
    incremental_cycles = []
    prev_cyc = 0

    for line in lines:
        match = re.search(r"(\d+) / \d+ \.\.\. cyc (\d+)", line)
        if match:
            ts       = int(match.group(1))
            curr_cyc = int(match.group(2))
            timesteps.append(ts)
            cumulative_cycles.append(curr_cyc)
            incremental_cycles.append(curr_cyc - prev_cyc)
            prev_cyc = curr_cyc

    return timesteps, cumulative_cycles, incremental_cycles


def plot_cycle_analysis(
    timesteps, cumulative_cycles, incremental_cycles,
    t_value: int, save_dir: str, workload: str
) -> None:
    """timestep별 증분 사이클과 누적 사이클을 이중 Y축으로 시각화합니다."""

    fig, ax1 = plt.subplots(figsize=(14, 6))
    title = f"NeuroSync Cycle Analysis — {workload}, T={t_value}"
    fig.suptitle(title, fontsize=14, fontweight="bold")

    # --- 파란 선: 증분 사이클 (좌측 Y축) ---
    color_inc = "#2563EB"
    ax1.set_xlabel("Simulation Timestep", fontsize=12)
    ax1.set_ylabel("Incremental Cycles (per Timestep)", fontsize=12, color=color_inc)
    # ax1.plot(
    #     timesteps, incremental_cycles,
    #     color=color_inc, linewidth=1.2, marker="o", markersize=2,
    #     label="Incremental Cycles"
    # )
    ax1.plot(
        timesteps, incremental_cycles,
        color=color_inc, linewidth=1.2,
        marker="o", markersize=5,           # 2 → 5
        markeredgecolor="white",            # 흰 테두리 추가
        markeredgewidth=0.8,
        label="Incremental Cycles"
    )
    ax1.tick_params(axis="y", labelcolor=color_inc)
    ax1.grid(True, linestyle="--", alpha=0.4)

    # --- 빨간 선: 누적 사이클 (우측 Y축) ---
    color_cum = "#DC2626"
    ax2 = ax1.twinx()
    ax2.set_ylabel("Cumulative Cycles", fontsize=12, color=color_cum)
    ax2.plot(
        timesteps, cumulative_cycles,
        color=color_cum, linewidth=2,
        label="Cumulative Cycles"
    )
    # ax2.plot(
    #     timesteps, cumulative_cycles,
    #     color=color_cum, linewidth=2,
    #     marker="D", markersize=4,           # 다이아몬드 마커 추가
    #     markeredgecolor="white",
    #     markeredgewidth=0.8,
    #     label="Cumulative Cycles"
    # )
    ax2.tick_params(axis="y", labelcolor=color_cum)

    # 범례 통합
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=10)

    # 최종 누적 사이클 수 오른쪽 끝에 표시
    ax2.annotate(
        f"Final: {cumulative_cycles[-1]:,}",
        xy=(timesteps[-1], cumulative_cycles[-1]),
        xytext=(-60, -20), textcoords="offset points",
        fontsize=9, color=color_cum,
        arrowprops=dict(arrowstyle="->", color=color_cum, lw=1)
    )

    plt.tight_layout()

    os.makedirs(save_dir, exist_ok=True)
    output_file = os.path.join(save_dir, f"Cycle_per_Timestep_T{t_value}.png")
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"  [저장 완료] {output_file}")
    plt.close()   # 다음 그래프와 겹치지 않도록 닫기


# ================================================================
# 메인 실행: T_VALUES 목록을 순회하며 그래프 생성
# ================================================================
if __name__ == "__main__":
    print(f"총 {len(T_VALUES)}개 T값 처리 시작: {T_VALUES}\n")

    success = []
    skipped = []

    for t in T_VALUES:
        folder_name = f"{WORKLOAD}_peri{t}_{PRETRACE_ENG}pretrace_eng"
        log_path    = os.path.join(RUNSPACE_PATH, folder_name, "log")

        print(f"[T={t}] log 파싱 중: {log_path}")
        timesteps, cumulative_cycles, incremental_cycles = parse_log(log_path)

        if timesteps is None or len(timesteps) == 0:
            print(f"  [건너뜀] log 파일 없음 또는 데이터 비어있음\n")
            skipped.append(t)
            continue

        print(f"  {len(timesteps)}개 timestep, 최종 누적 사이클: {cumulative_cycles[-1]:,}")
        plot_cycle_analysis(
            timesteps, cumulative_cycles, incremental_cycles,
            t, SAVE_DIR, WORKLOAD
        )
        success.append(t)
        print()

    # 최종 요약
    print("=" * 50)
    print(f"완료: {len(success)}개  →  T = {success}")
    if skipped:
        print(f"건너뜀: {len(skipped)}개  →  T = {skipped}")
        print("  (해당 T값의 시뮬레이션 결과가 없거나 example.cfg에 포함되지 않은 T값입니다)")
    print(f"\n그래프 저장 위치: {os.path.abspath(SAVE_DIR)}")


# """
# plot_cycle_per_timestep.py
# --------------------------
# 역할:
#     특정 Synchronization Period(T) 하나에 대해 timestep별 사이클 소모를 분석합니다.
#     - 파란 선(좌측 Y축): 각 timestep에서 소모된 증분 사이클 수 (부하 변동 파악)
#     - 빨간 선(우측 Y축): 누적 사이클 수 (전체 진행 추이)

# 사용법:
#     python3 plot_cycle_per_timestep.py

# 출력:
#     {SAVE_DIR}/Cycle_per_Timestep_T{T_VALUE}.png
# """

# import os
# import re
# import matplotlib.pyplot as plt

# # ================================================================
# # [설정] 실험 환경에 맞게 아래 값들을 수정하세요
# # ================================================================
# T_VALUE      = 2                               # 분석할 Synchronization Period 값
# PRETRACE_ENG = 10                               # pretrace_engine 값
# WORKLOAD     = "example1"                       # 워크로드 이름
# RUNSPACE_PATH = "./runspace/lazy/"              # 실험 결과 폴더 경로
# SAVE_DIR     = "./../result_pictures/"             # 그래프 저장 경로
# # ================================================================


# def parse_log(log_path: str):
#     """
#     log 파일에서 timestep별 사이클 정보를 파싱합니다.

#     log 파일 한 줄 형식:
#         {current_timestep} / {max_timestep} ... cyc {cumulative_cycles}, elapsed {time} (s)
#     예시:
#         992 / 992 ... cyc 1234567, elapsed 3.14 (s)

#     Returns:
#         timesteps         : 각 기록 시점의 timestep 번호 리스트
#         cumulative_cycles : 누적 사이클 수 리스트
#         incremental_cycles: 직전 기록 대비 증분 사이클 수 리스트
#     """
#     if not os.path.exists(log_path):
#         return None, None, None

#     with open(log_path, "r") as f:
#         lines = f.readlines()

#     timesteps          = []
#     cumulative_cycles  = []
#     incremental_cycles = []
#     prev_cyc = 0

#     for line in lines:
#         match = re.search(r"(\d+) / \d+ \.\.\. cyc (\d+)", line)
#         if match:
#             ts       = int(match.group(1))
#             curr_cyc = int(match.group(2))
#             timesteps.append(ts)
#             cumulative_cycles.append(curr_cyc)
#             incremental_cycles.append(curr_cyc - prev_cyc)
#             prev_cyc = curr_cyc

#     return timesteps, cumulative_cycles, incremental_cycles


# def plot_cycle_analysis(
#     timesteps, cumulative_cycles, incremental_cycles,
#     t_value: int, save_dir: str, workload: str
# ) -> None:
#     """timestep별 증분 사이클과 누적 사이클을 이중 Y축으로 시각화합니다."""

#     fig, ax1 = plt.subplots(figsize=(14, 6))
#     title = f"NeuroSync Cycle Analysis — {workload}, T={t_value}"
#     fig.suptitle(title, fontsize=14, fontweight="bold")

#     # --- 파란 선: 증분 사이클 (좌측 Y축) ---
#     color_inc = "#2563EB"
#     ax1.set_xlabel("Simulation Timestep", fontsize=12)
#     ax1.set_ylabel("Incremental Cycles (per Timestep)", fontsize=12, color=color_inc)
#     ax1.plot(
#         timesteps, incremental_cycles,
#         color=color_inc, linewidth=1.2, marker="o", markersize=2,
#         label="Incremental Cycles"
#     )
#     ax1.tick_params(axis="y", labelcolor=color_inc)
#     ax1.grid(True, linestyle="--", alpha=0.4)

#     # --- 빨간 선: 누적 사이클 (우측 Y축) ---
#     color_cum = "#DC2626"
#     ax2 = ax1.twinx()
#     ax2.set_ylabel("Cumulative Cycles", fontsize=12, color=color_cum)
#     ax2.plot(
#         timesteps, cumulative_cycles,
#         color=color_cum, linewidth=2,
#         label="Cumulative Cycles"
#     )
#     ax2.tick_params(axis="y", labelcolor=color_cum)

#     # 범례 통합
#     lines1, labels1 = ax1.get_legend_handles_labels()
#     lines2, labels2 = ax2.get_legend_handles_labels()
#     ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=10)

#     # 최종 누적 사이클 수 오른쪽 끝에 표시
#     ax2.annotate(
#         f"Final: {cumulative_cycles[-1]:,}",
#         xy=(timesteps[-1], cumulative_cycles[-1]),
#         xytext=(-60, -20), textcoords="offset points",
#         fontsize=9, color=color_cum,
#         arrowprops=dict(arrowstyle="->", color=color_cum, lw=1)
#     )

#     plt.tight_layout()

#     os.makedirs(save_dir, exist_ok=True)
#     # @@
#     output_file = os.path.join(save_dir, f"Cycle_per_Timestep_T{t_value}.png")
#     plt.savefig(output_file, dpi=300, bbox_inches="tight")
#     print(f"[저장 완료] {output_file}")
#     plt.show()


# # ================================================================
# # 메인 실행
# # ================================================================
# if __name__ == "__main__":
#     folder_name = f"{WORKLOAD}_peri{T_VALUE}_{PRETRACE_ENG}pretrace_eng"
#     log_path    = os.path.join(RUNSPACE_PATH, folder_name, "log")

#     print(f"log 파일 파싱 중: {log_path}")
#     timesteps, cumulative_cycles, incremental_cycles = parse_log(log_path)

#     if timesteps is None or len(timesteps) == 0:
#         print(f"[오류] log 파일이 없거나 데이터가 비어 있습니다: {log_path}")
#     else:
#         print(f"  총 {len(timesteps)}개 timestep 데이터 파싱 완료")
#         print(f"  최종 누적 사이클: {cumulative_cycles[-1]:,}")
#         plot_cycle_analysis(
#             timesteps, cumulative_cycles, incremental_cycles,
#             T_VALUE, SAVE_DIR, WORKLOAD
#         )