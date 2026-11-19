# Comparison of two runs

- Run A: `results/pilot/games.csv.gz`
- Run B: `results/one_sequence/games.csv.gz`

## Win rates

Row bot's win rate against the column bot in each run. z is the difference divided by its standard error; |z| of 1.96 or more is beyond what chance usually explains.

| pairing | run A | run B | B - A (points) | z | verdict |
|---|---|---|---|---|---|
| random vs builder | 1.3% ±0.2 | 3.7% ±0.4 | +2.4 | +10.72 | beyond chance |
| random vs blocker | 1.0% ±0.2 | 2.6% ±0.3 | +1.6 | +8.74 | beyond chance |
| random vs mixed | 0.9% ±0.2 | 2.4% ±0.3 | +1.5 | +8.26 | beyond chance |
| random vs mixed_save | 0.4% ±0.1 | 0.9% ±0.2 | +0.4 | +3.68 | beyond chance |
| builder vs blocker | 47.3% ±0.8 | 49.7% ±0.8 | +2.4 | +4.13 | beyond chance |
| builder vs mixed | 43.2% ±0.8 | 44.8% ±0.7 | +1.6 | +2.87 | beyond chance |
| builder vs mixed_save | 38.0% ±0.8 | 36.5% ±0.7 | -1.4 | -2.61 | beyond chance |
| blocker vs mixed | 45.6% ±0.8 | 44.8% ±0.7 | -0.9 | -1.60 | within chance |
| blocker vs mixed_save | 38.7% ±0.8 | 33.8% ±0.8 | -4.9 | -8.61 | beyond chance |
| mixed vs mixed_save | 43.8% ±0.8 | 39.9% ±0.7 | -3.9 | -7.18 | beyond chance |

9 of 10 differences are beyond chance; about 0.5 would be expected by luck alone if nothing had changed.

## Rankings and equilibrium

| bot | avg vs field A | avg vs field B | equilibrium A | equilibrium B |
|---|---|---|---|---|
| random | 0.9% | 2.4% | 0.0% | 0.0% |
| builder | 56.8% | 56.8% | 0.0% | 0.0% |
| blocker | 59.0% | 56.5% | 0.0% | 0.0% |
| mixed | 63.5% | 62.0% | 0.0% | 0.0% |
| mixed_save | 69.8% | 72.2% | 100.0% | 100.0% |

Ranking A: mixed_save > mixed > blocker > builder > random

Ranking B: mixed_save > mixed > builder > blocker > random

The rankings are different.

## First-move advantage

| games | run A | run B |
|---|---|---|
| random vs itself | 52.4% | 52.3% |
| builder vs itself | 53.5% | 52.9% |
| blocker vs itself | 55.1% | 54.5% |
| mixed vs itself | 54.4% | 52.7% |
| mixed_save vs itself | 54.8% | 54.6% |
| all other games | 52.4% | 52.2% |
