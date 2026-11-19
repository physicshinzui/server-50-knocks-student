#!/bin/bash
set -euo pipefail
label=${1:?実行の名前が必要です}
input=${2:?入力ファイルの指定が必要です}
job_id=${PBS_JOBID:?計算ノード上のPBSジョブで実行してください}
run_dir="work/runs/$job_id"
mkdir -p work/runs
mkdir -p -- "$run_dir"
exec > "$run_dir/run.log" 2>&1

record_exit() {
    status=$?
    if [ "$status" -eq 0 ]; then
        echo 'status=OK'
    else
        echo "status=ERROR exit_code=$status"
    fi
}
trap record_exit EXIT
printf 'job_id=%s\nlesson=%s\nhost=%s\ninput=%s\n' "$job_id" "$label" "$(hostname)" "$input"
python3 -c 'import sys; print("python=" + sys.executable)'
if [ "$label" = first ] || [ "$label" = resources ]; then
    sleep 25
fi
if [ "$label" = python ]; then
    python3 -c 'import numpy; print("numpy=" + numpy.__version__)'
    OPENBLAS_NUM_THREADS=1 python3 tools/summarize_numpy.py "$input" > "$run_dir/result.json"
else
    python3 tools/summarize.py "$input" > "$run_dir/result.json"
fi
printf 'result=%s/result.json\n' "$run_dir"
