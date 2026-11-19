#!/bin/bash
#PBS -N s50gpu
#PBS -l select=1:ncpus=1:ngpus=[GPU個数]:mem=512mb
#PBS -l walltime=00:03:00
#PBS -q [GPUキュー]
#PBS -j oe
set -euo pipefail
cd "${PBS_O_WORKDIR:?PBSで投入してください}"
job_id=${PBS_JOBID:?計算ノード上のPBSジョブで実行してください}
run_dir="work/runs/$job_id"
mkdir -p -- "$run_dir"
exec > "$run_dir/run.log" 2>&1
printf 'job_id=%s\nlesson=gpu\nhost=%s\n' "$job_id" "$(hostname)"
gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader | awk 'NR==1 {print}')
printf 'gpu=%s\n' "$gpu_name"
nvidia-smi
echo 'status=OK'
