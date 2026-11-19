# Comparison of two runs

- Run A: `results/pilot/games.csv.gz`
- Run B: `results/values_flat/games.csv.gz`

## Win rates

Row bot's win rate against the column bot in each run. z is the difference divided by its standard error; |z| of 1.96 or more is beyond what chance usually explains.

| pairing | run A | run B | B - A (points) | z | verdict |
|---|---|---|---|---|---|
| random vs builder | 1.3% ±0.2 | 1.3% ±0.2 | -0.0 | -0.06 | within chance |
| random vs blocker | 1.0% ±0.2 | 1.8% ±0.3 | +0.8 | +4.89 | beyond chance |
| random vs mixed | 0.9% ±0.2 | 0.9% ±0.2 | +0.0 | +0.00 | within chance |
| random vs mixed_save | 0.4% ±0.1 | 0.4% ±0.1 | -0.1 | -0.79 | within chance |
| builder vs blocker | 47.3% ±0.8 | 54.9% ±0.9 | +7.6 | +12.40 | beyond chance |
| builder vs mixed | 43.2% ±0.8 | 43.0% ±0.8 | -0.2 | -0.33 | within chance |
| builder vs mixed_save | 38.0% ±0.8 | 37.0% ±0.8 | -1.0 | -1.66 | within chance |
| blocker vs mixed | 45.6% ±0.8 | 36.7% ±0.8 | -8.9 | -15.27 | beyond chance |
| blocker vs mixed_save | 38.7% ±0.8 | 28.5% ±0.8 | -10.2 | -17.55 | beyond chance |
| mixed vs mixed_save | 43.8% ±0.8 | 42.6% ±0.8 | -1.1 | -2.00 | beyond chance |

5 of 10 differences are beyond chance; about 0.5 would be expected by luck alone if nothing had changed.

## Rankings and equilibrium

| bot | avg vs field A | avg vs field B | equilibrium A | equilibrium B |
|---|---|---|---|---|
| random | 0.9% | 1.1% | 0.0% | 0.0% |
| builder | 56.8% | 58.4% | 0.0% | 0.0% |
| blocker | 59.0% | 52.1% | 0.0% | 0.0% |
| mixed | 63.5% | 65.5% | 0.0% | 0.0% |
| mixed_save | 69.8% | 72.9% | 100.0% | 100.0% |

Ranking A: mixed_save > mixed > blocker > builder > random

Ranking B: mixed_save > mixed > builder > blocker > random

The rankings are different.

## First-move advantage

| games | run A | run B |
|---|---|---|
| random vs itself | 52.4% | 52.4% |
| builder vs itself | 53.5% | 54.6% |
| blocker vs itself | 55.1% | 54.7% |
| mixed vs itself | 54.4% | 54.2% |
| mixed_save vs itself | 54.8% | 55.6% |
| all other games | 52.4% | 52.6% |
