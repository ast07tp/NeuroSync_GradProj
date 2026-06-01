#!/bin/bash
# Stage 3 — 고정 T 스윕 (brunel_si v1, 순차 실행으로 CPU thrash 방지)
# step0: v1 dataset 재생성 (현재 dataset이 v2일 수 있으므로 표준 v1로 되돌림)
# 이후 T=1,2,4,8,32,64,128 순차 시뮬 (T=16은 기존 runspace/brunel_si 재사용)
# 각 T 완료까지 대기 후 다음 T. 결과 누적 cyc 를 durable 파일로 저장.
set -u
ROOT=/home/heechan/26_GRADPROJ/NeuroSync_GradProj
cd "$ROOT"
PROG=/tmp/sweep_progress.log
RESULT="$ROOT/runspace/brunel_si/SWEEP_total_cycles.txt"
: > "$PROG"
echo "# Stage3 fixed-T sweep (brunel_si v1)  $(date)" | tee "$RESULT"
echo "# columns: T  final_timestep  final_cumulative_cyc" >> "$RESULT"

echo "[sweep] step0: v1 dataset 재생성" | tee -a "$PROG"
( cd "$ROOT/benchmark/brunel_si" && python3 brunel_workload.py ) >>"$PROG" 2>&1
tail -1 "$PROG"

for T in 1 2 4 8 32 64 128; do
  cfg=/tmp/sweep_T${T}.cfg
  sed "s/^sync_period = \[16\]/sync_period = [${T}]/" example.cfg > "$cfg"
  log="runspace/brunel_si/brunel_si_peri${T}_10pretrace_eng/log"
  echo "[sweep] T=$T start $(date +%T)" | tee -a "$PROG"
  python3 run.py "$cfg" > /tmp/sweep_run_T${T}.out 2>&1

  waited=0
  while true; do
    if [ -f "$log" ] && grep -q "Simulation Done" "$log" 2>/dev/null; then
      break
    fi
    sleep 20; waited=$((waited+20))
    if [ $waited -ge 2400 ]; then
      echo "[sweep] T=$T TIMEOUT(${waited}s) — skip" | tee -a "$PROG"
      break
    fi
    # 컴파일 단계(초기 ~90s)엔 Main.py 미존재 가능 → 90s 이후에만 crash 판정
    if [ $waited -ge 120 ] && ! pgrep -f "python3 Main.py" >/dev/null 2>&1 \
       && ! grep -q "Simulation Done" "$log" 2>/dev/null; then
      echo "[sweep] T=$T PROC_GONE without Done — skip" | tee -a "$PROG"
      break
    fi
  done

  fc=$(grep -oE 'cyc [0-9]+' "$log" 2>/dev/null | tail -1 | awk '{print $2}')
  ft=$(grep -oE '^[0-9]+ /' "$log" 2>/dev/null | tail -1 | tr -d ' /')
  echo "${T} ${ft:-NA} ${fc:-NA}" >> "$RESULT"
  echo "[sweep] T=$T done $(date +%T)  final ts=${ft:-NA} cyc=${fc:-NA}" | tee -a "$PROG"
done

echo "[sweep] ALL DONE $(date +%T)" | tee -a "$PROG"
echo "--- $RESULT ---"; cat "$RESULT"
