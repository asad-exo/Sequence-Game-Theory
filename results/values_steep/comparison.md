# Comparison of two runs

- Run A: `results/pilot/games.csv.gz`
- Run B: `results/values_steep/games.csv.gz`

## Win rates

Row bot's win rate against the column bot in each run. z is the difference divided by its standard error; |z| of 1.96 or more is beyond what chance usually explains.

| pairing | run A | run B | B - A (points) | z | verdict |
|---|---|---|---|---|---|
| random vs builder | 1.3% ±0.2 | 1.6% ±0.2 | +0.2 | +1.25 | within chance |
| random vs blocker | 1.0% ±0.2 | 0.9% ±0.2 | -0.1 | -0.88 | within chance |
| random vs mixed | 0.9% ±0.2 | 1.0% ±0.2 | +0.1 | +0.88 | within chance |
| random vs mixed_save | 0.4% ±0.1 | 0.4% ±0.1 | +0.0 | +0.11 | within chance |
| builder vs blocker | 47.3% ±0.8 | 46.7% ±0.8 | -0.6 | -1.00 | within chance |
| builder vs mixed | 43.2% ±0.8 | 42.9% ±0.8 | -0.3 | -0.58 | within chance |
| builder vs mixed_save | 38.0% ±0.8 | 38.7% ±0.8 | +0.7 | +1.22 | within chance |
| blocker vs mixed | 45.6% ±0.8 | 47.7% ±0.8 | +2.1 | +3.58 | beyond chance |
| blocker vs mixed_save | 38.7% ±0.8 | 41.3% ±0.8 | +2.6 | +4.38 | beyond chance |
| mixed vs mixed_save | 43.8% ±0.8 | 44.8% ±0.8 | +1.0 | +1.77 | within chance |

2 of 10 differences are beyond chance; about 0.5 would be expected by luck alone if nothing had changed.

## Rankings and equilibrium

| bot | avg vs field A | avg vs field B | equilibrium A | equilibrium B |
|---|---|---|---|---|
| random | 0.9% | 1.0% | 0.0% | 0.0% |
| builder | 56.8% | 56.7% | 0.0% | 0.0% |
| blocker | 59.0% | 60.4% | 0.0% | 0.0% |
| mixed | 63.5% | 63.3% | 0.0% | 0.0% |
| mixed_save | 69.8% | 68.7% | 100.0% | 100.0% |

Ranking A: mixed_save > mixed > blocker > builder > random

Ranking B: mixed_save > mixed > blocker > builder > random

The rankings are identical.

## First-move advantage

| games | run A | run B |
|---|---|---|
| random vs itself | 52.4% | 52.4% |
| builder vs itself | 53.5% | 54.4% |
| blocker vs itself | 55.1% | 54.4% |
| mixed vs itself | 54.4% | 53.1% |
| mixed_save vs itself | 54.8% | 54.5% |
| all other games | 52.4% | 52.3% |
