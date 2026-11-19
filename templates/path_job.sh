#!/bin/bash
#PBS -N s50path
#PBS -l select=1:ncpus=1:ngpus=0:mem=256mb
#PBS -l walltime=00:03:00
#PBS -q cpu-s
#PBS -j oe
set -euo pipefail
cd "${PBS_O_WORKDIR:?PBSで投入してください}"
export PATH="[ここをwork/binへのパスに変更]:$PATH"
job_id=${PBS_JOBID:?計算ノード上のPBSジョブで実行してください}
run_dir="work/runs/$job_id"
mkdir -p -- "$run_dir"
exec > "$run_dir/run.log" 2>&1
printf 'job_id=%s\nlesson=path\nhost=%s\n' "$job_id" "$(hostname)"
printf 'tool=%s\n' "$(command -v mytool)"
printf 'output=%s\n' "$(mytool)"
echo 'status=OK'
