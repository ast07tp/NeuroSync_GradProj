#!/bin/bash
# Stage3-B 정밀: redo_cyc 계측본으로 T=64, T=128 순차 재실행 (브런치 보존: 별도
# result_folder=brunel_si_specgate). dataset 은 Stage3 sweep step0 가 만든 v1 재사용
# (재생성 안 함). 각 런 redo_cyc.dat = rollback_state 소모 사이클(낭비투기 질량).
set -u
ROOT=/home/heechan/26_GRADPROJ/NeuroSync_GradProj
cd "$ROOT"
PROG=/tmp/specgate_progress.log
: > "$PROG"
echo "# Stage3-B specgate (redo_cyc 계측, T=64/128)  $(date)" | tee "$PROG"

for T in 64 128; do
  cfg=/tmp/specgate_T${T}.cfg
  sed "s/^sync_period = \[64\]/sync_period = [${T}]/" example_specgate.cfg > "$cfg"
  # run.py 는 서브폴더 prefix 에 workload_name(brunel_si) 사용(result_folder_name 아님)
  log="runspace/brunel_si_specgate/brunel_si_peri${T}_10pretrace_eng/log"
  echo "[specgate] T=$T start $(date +%T)" | tee -a "$PROG"
  python3 run.py "$cfg" > /tmp/specgate_run_T${T}.out 2>&1

  waited=0
  while true; do
    if [ -f "$log" ] && grep -q "Simulation Done" "$log" 2>/dev/null; then
      break
    fi
    sleep 20; waited=$((waited+20))
    if [ $waited -ge 2400 ]; then
      echo "[specgate] T=$T TIMEOUT(${waited}s) — skip" | tee -a "$PROG"; break
    fi
    if [ $waited -ge 120 ] && ! pgrep -f "python3 Main.py" >/dev/null 2>&1 \
       && ! grep -q "Simulation Done" "$log" 2>/dev/null; then
      echo "[specgate] T=$T PROC_GONE without Done — skip" | tee -a "$PROG"; break
    fi
  done

  fc=$(grep -oE 'cyc [0-9]+' "$log" 2>/dev/null | tail -1 | awk '{print $2}')
  rdir=$(dirname "$log")
  tot=$(tail -1 "$rdir/redo_cyc.dat" 2>/dev/null)
  echo "[specgate] T=$T done $(date +%T)  log_final_cyc=${fc:-NA}  ${tot:-NO_redo_cyc.dat}" \
    | tee -a "$PROG"
done
echo "[specgate] ALL DONE $(date +%T)" | tee -a "$PROG"
