#!/usr/bin/env bash
# Reproduce the whole study: every experiment in results/, then every report and figure.
#
#     bash run_study.sh            # all experiments, then python study.py
#
# Each experiment is deterministic: the same command gives the same games on any machine,
# with any number of workers (the test suite replays a sample of every published log).
# Rough running times on a 2-core machine are noted (about 3 hours in all); more cores scale
# almost linearly.
set -euo pipefail

T="python tournament.py"

# The pilot: the five original strategies (about 4 minutes).
$T --roster pilot --deals 5000 --seed 2026 --out results/pilot/games.csv.gz

# The main tournament: all 18 fast strategies, 1,026,000 games (about 50 minutes).
$T --deals 3000 --seed 200000 --out results/full/games.csv.gz

# Jack timing: the five Jack policies on 5,000 deals (about 5 minutes).
$T --roster jacks --deals 5000 --seed 300000 --out results/jacks/games.csv.gz

# Robustness: the pilot on fresh deals, under other line values, and under the
# one-sequence rule (about 5 minutes each).
$T --roster pilot --deals 5000 --seed 100000 --out results/replication/games.csv.gz
$T --roster pilot --deals 5000 --seed 5000000 --out results/replication2/games.csv.gz
$T --roster pilot --values linear --deals 5000 --out results/values_linear/games.csv.gz
$T --roster pilot --values flat --deals 5000 --out results/values_flat/games.csv.gz
$T --roster pilot --values steep --deals 5000 --out results/values_steep/games.csv.gz
$T --roster pilot --sequences-to-win 1 --deals 5000 --out results/one_sequence/games.csv.gz

# Sweeps: how much to defend, and how much noisy choice costs (about 10 minutes each).
$T --bots mixed_save:defend=0 mixed_save:defend=0.25 mixed_save:defend=0.5 mixed_save:defend=0.75 \
   mixed_save mixed_save:defend=1.5 mixed_save:defend=2 mixed_save:defend=3 mixed_save:defend=4 \
   --deals 3000 --seed 400000 --out results/sweep_defend/games.csv.gz
$T --bots logit:lam=0.03 logit:lam=0.1 logit:lam=0.3 logit logit:lam=3 logit:lam=10 mixed_save \
   --deals 3000 --seed 500000 --out results/sweep_lambda/games.csv.gz

# Follow-ups to the main tournament.
# Is card counting's small edge real? (about 10 minutes)
$T --bots counter bayes mixed_save --deals 15000 --seed 700000 --no-mirror --out results/counting/games.csv.gz
# Why doesn't combining ideas help? expert with one component removed at a time (about 25 minutes).
$T --bots expert expert:adapt=0 expert:hand=0 expert:fork=0 expert:infer=0 expert:count=0,infer=0 \
   counter mixed_save --deals 3000 --seed 800000 --out results/ablation/games.csv.gz

# Lookahead: Monte Carlo sampling over the hidden cards (seconds per game; about 15 minutes).
$T --bots mixed_save counter sampler --deals 300 --seed 600000 --no-mirror --out results/sampler/games.csv.gz

# Counter-strategy hunts (double oracle): from the equilibrium, and from a wider pool (about 30 minutes).
python hunt.py --pool counter --iterations 8 --screen-deals 400 --confirm-deals 4000 --finalists 4 \
   --random 24 --seed 900000 --out results/hunt
python hunt.py --pool counter bayes forker mixed_save --iterations 6 --screen-deals 400 --confirm-deals 4000 \
   --finalists 4 --random 24 --seed 1500000 --out results/hunt_wide
# The wide hunt's find, tested directly: card counting x doubled defence (about 10 minutes).
$T --bots mixed_save mixed_save:defend=2 counter mixed:attack=0.5,jacks=save,count=1 --deals 10000 \
   --seed 1800000 --no-mirror --out results/defence_counting/games.csv.gz

# Every report, comparison and figure (a few minutes).
python study.py
