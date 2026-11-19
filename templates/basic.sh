#!/bin/bash
#PBS -N s50first
#PBS -l select=1:ncpus=[CPU個数]:ngpus=[GPU個数]:mem=[メモリ]
#PBS -l walltime=[時:分:秒]
#PBS -q [CPUキュー]
#PBS -j oe
set -euo pipefail
cd "${PBS_O_WORKDIR:?PBSで投入してください}"
bash tools/run_lesson.sh first data/original/samples.tsv
