#!/bin/bash
#PBS -N s50python
#PBS -l select=1:ncpus=1:ngpus=0:mem=256mb
#PBS -l walltime=00:03:00
#PBS -q cpu-s
#PBS -j oe
set -euo pipefail
cd "${PBS_O_WORKDIR:?PBSで投入してください}"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate [環境名]
bash tools/run_lesson.sh python data/original/samples.tsv
