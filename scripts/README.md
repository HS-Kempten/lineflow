# Benchmarks

This folder holds code to reproduce the results from our paper

```
@InProceedings{pmlr-v267-muller25c,
  title = {{L}ine{F}low: A Framework to Learn Active Control of Production Lines},
  author = {M\"{u}ller, Kai and Wenzel, Martin and Windisch, Tobias},
  booktitle = {Proceedings of the 42nd International Conference on Machine Learning},
  pages = {45212--45235},
  year = {2025},
  editor = {Singh, Aarti and Fazel, Maryam and Hsu, Daniel and Lacoste-Julien, Simon and Berkenkamp, Felix and Maharaj, Tegan and Wagstaff, Kiri and Zhu, Jerry},
  volume = {267},
  series = {Proceedings of Machine Learning Research},
  month = {13--19 Jul},
  publisher = {PMLR},
  url = {https://proceedings.mlr.press/v267/muller25c.html},
}
```

## Scenarios


### Part distribution

Run `part_distribution/run_part_distribution_k.sh` with `k=3,4,5`.

### Waiting time

Run `waiting_time/run_waiting_time.sh` for WT and  `waiting_time/run_waiting_time_jump.sh` for WTJ

### Worker assignment

Run `worker_assignment/run_worker_assignmen_k.sh` with `k=3,4,5`.

### Complex line

Run `complex_line/run_complex_line.sh` to run all complex line benchmarks, i.e., recurrent PPO with and without
curriculum learning as well as stacked PPO with curriculum learning.


## Parallelization

The central file is `train.py`, which is triggered with specific parameters for each benchmark
scenario and RL algorithm. More specifically, each benchmark scenario triggers another run script
for each algorithm, for instance `run_a2c.sh` which looks like:


```bash
#!/bin/bash

SEED=$1
ENV=$2
N=$3
INFO=$4
TOTAL_STEPS=$5

LR=("0.01" "0.001" "0.0005" "0.01" "0.001" "0.0005")
ENTCOEF=("0.0"  "0.0"   "0.0"    "0.001" "0.001" "0.001")

for i in "${!LR[@]}"; do
    echo "Running config $i: lr=${LR[$i]}, ent_coef=${ENTCOEF[$i]}"
    python3 train.py --deterministic \
        --env="$ENV" --n_cells="$N" --model=A2C \
        --seed="$SEED" --info="$INFO" --total_step="$TOTAL_STEPS" \
        --learning_rate="${LR[$i]}" \
        --ent_coef="${ENTCOEF[$i]}"
done
```

In our experiments, the benchmarks where executed within a slurm cluster and these shell scripts
looked like:

```bash
#!/bin/bash
#SBATCH --partition=<PARTITION>
#SBATCH --mem=10G                 
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --array=0-5%3             

SEED=$1
ENV=$2
N=$3
INFO=$4
TOTAL_STEPS=$5

declare -a LR=("0.01" "0.001" "0.0005" "0.01" "0.001" "0.0005")
declare -a ENTCOEF=("0.0"  "0.0"   "0.0"    "0.001" "0.001" "0.001" )

srun python3 train.py --deterministic \
    --env=$ENV --n_cells=$N --model=A2C \
    --seed=$SEED --info="$INFO" --total_step=$TOTAL_STEPS \
    --learning_rate="${LR[$SLURM_ARRAY_TASK_ID]}" \
    --ent_coef="${ENTCOEF[$SLURM_ARRAY_TASK_ID]}"
```
