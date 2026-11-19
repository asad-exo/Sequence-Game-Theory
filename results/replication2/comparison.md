# Comparison of two runs

- Run A: `results/pilot/games.csv.gz`
- Run B: `results/replication2/games.csv.gz`

## Win rates

Row bot's win rate against the column bot in each run. z is the difference divided by its standard error; |z| of 1.96 or more is beyond what chance usually explains.

| pairing | run A | run B | B - A (points) | z | verdict |
|---|---|---|---|---|---|
| random vs builder | 1.3% ±0.2 | 1.7% ±0.3 | +0.4 | +2.15 | beyond chance |
| random vs blocker | 1.0% ±0.2 | 1.0% ±0.2 | -0.0 | -0.29 | within chance |
| random vs mixed | 0.9% ±0.2 | 0.8% ±0.2 | -0.1 | -0.94 | within chance |
| random vs mixed_save | 0.4% ±0.1 | 0.3% ±0.1 | -0.1 | -1.15 | within chance |
| builder vs blocker | 47.3% ±0.8 | 47.8% ±0.8 | +0.5 | +0.87 | within chance |
| builder vs mixed | 43.2% ±0.8 | 43.0% ±0.8 | -0.2 | -0.32 | within chance |
| builder vs mixed_save | 38.0% ±0.8 | 38.2% ±0.8 | +0.2 | +0.33 | within chance |
| blocker vs mixed | 45.6% ±0.8 | 45.8% ±0.8 | +0.1 | +0.17 | within chance |
| blocker vs mixed_save | 38.7% ±0.8 | 39.1% ±0.8 | +0.3 | +0.56 | within chance |
| mixed vs mixed_save | 43.8% ±0.8 | 44.0% ±0.8 | +0.2 | +0.34 | within chance |

1 of 10 differences are beyond chance; about 0.5 would be expected by luck alone if nothing had changed.

## Rankings and equilibrium

| bot | avg vs field A | avg vs field B | equilibrium A | equilibrium B |
|---|---|---|---|---|
| random | 0.9% | 0.9% | 0.0% | 0.0% |
| builder | 56.8% | 56.8% | 0.0% | 0.0% |
| blocker | 59.0% | 59.0% | 0.0% | 0.0% |
| mixed | 63.5% | 63.6% | 0.0% | 0.0% |
| mixed_save | 69.8% | 69.6% | 100.0% | 100.0% |

Ranking A: mixed_save > mixed > blocker > builder > random

Ranking B: mixed_save > mixed > blocker > builder > random

The rankings are identical.

## First-move advantage

| games | run A | run B |
|---|---|---|
| random vs itself | 52.4% | 51.7% |
| builder vs itself | 53.5% | 54.0% |
| blocker vs itself | 55.1% | 54.9% |
| mixed vs itself | 54.4% | 53.0% |
| mixed_save vs itself | 54.8% | 54.6% |
| all other games | 52.4% | 52.6% |
