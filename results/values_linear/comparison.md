# Comparison of two runs

- Run A: `results/pilot/games.csv.gz`
- Run B: `results/values_linear/games.csv.gz`

## Win rates

Row bot's win rate against the column bot in each run. z is the difference divided by its standard error; |z| of 1.96 or more is beyond what chance usually explains.

| pairing | run A | run B | B - A (points) | z | verdict |
|---|---|---|---|---|---|
| random vs builder | 1.3% ±0.2 | 1.9% ±0.3 | +0.6 | +3.20 | beyond chance |
| random vs blocker | 1.0% ±0.2 | 2.9% ±0.3 | +1.9 | +9.98 | beyond chance |
| random vs mixed | 0.9% ±0.2 | 1.6% ±0.2 | +0.7 | +4.41 | beyond chance |
| random vs mixed_save | 0.4% ±0.1 | 0.6% ±0.2 | +0.2 | +1.86 | within chance |
| builder vs blocker | 47.3% ±0.8 | 49.2% ±0.9 | +1.9 | +3.07 | beyond chance |
| builder vs mixed | 43.2% ±0.8 | 37.6% ±0.8 | -5.6 | -9.59 | beyond chance |
| builder vs mixed_save | 38.0% ±0.8 | 29.6% ±0.8 | -8.4 | -14.60 | beyond chance |
| blocker vs mixed | 45.6% ±0.8 | 40.4% ±0.8 | -5.2 | -8.78 | beyond chance |
| blocker vs mixed_save | 38.7% ±0.8 | 29.7% ±0.8 | -9.0 | -15.26 | beyond chance |
| mixed vs mixed_save | 43.8% ±0.8 | 41.0% ±0.8 | -2.8 | -4.84 | beyond chance |

9 of 10 differences are beyond chance; about 0.5 would be expected by luck alone if nothing had changed.

## Rankings and equilibrium

| bot | avg vs field A | avg vs field B | equilibrium A | equilibrium B |
|---|---|---|---|---|
| random | 0.9% | 1.8% | 0.0% | 0.0% |
| builder | 56.8% | 53.6% | 0.0% | 0.0% |
| blocker | 59.0% | 54.5% | 0.0% | 0.0% |
| mixed | 63.5% | 65.4% | 0.0% | 0.0% |
| mixed_save | 69.8% | 74.8% | 100.0% | 100.0% |

Ranking A: mixed_save > mixed > blocker > builder > random

Ranking B: mixed_save > mixed > blocker > builder > random

The rankings are identical.

## First-move advantage

| games | run A | run B |
|---|---|---|
| random vs itself | 52.4% | 52.4% |
| builder vs itself | 53.5% | 55.0% |
| blocker vs itself | 55.1% | 54.1% |
| mixed vs itself | 54.4% | 54.2% |
| mixed_save vs itself | 54.8% | 54.8% |
| all other games | 52.4% | 52.5% |
