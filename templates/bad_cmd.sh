#!/bin/bash
#PBS -N s50badcmd
#PBS -l select=1:ncpus=1:ngpus=0:mem=256mb
#PBS -l walltime=00:03:00
#PBS -q cpu-s
#PBS -j oe
set -euo pipefail
cd "${PBS_O_WORKDIR:?PBSで投入してください}"
nonexistent_tool --version
bash tools/run_lesson.sh bad-cmd data/original/samples.tsv
