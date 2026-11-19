# Tournament summary

150,000 games between 5 bots (100,000 between different bots, 50,000 mirror matches). Draws: 5. Median game length: 49 turns (plies).

Settings: line values per bot (default), 2 sequences to win, first seed 100000, 5000 deals per pairing. Command: `python tournament.py --roster pilot --deals 5000 --seed 100000 --out results/replication/games.csv.gz`

## Win-rate matrix

Row bot's win rate against the column bot, with the 95% margin. Margins come from paired deals (each deal is played once from each seat).

| bot \ opponent | random | builder | blocker | mixed | mixed_save | avg vs field |
|---|---|---|---|---|---|---|
| **random** | – | 1.7% ±0.3 | 1.0% ±0.2 | 0.9% ±0.2 | 0.3% ±0.1 | 1.0% |
| **builder** | 98.3% ±0.3 | – | 49.3% ±0.8 | 43.2% ±0.8 | 38.7% ±0.8 | 57.4% |
| **blocker** | 99.0% ±0.2 | 50.7% ±0.8 | – | 44.2% ±0.8 | 38.6% ±0.8 | 58.1% |
| **mixed** | 99.1% ±0.2 | 56.8% ±0.8 | 55.8% ±0.8 | – | 44.5% ±0.8 | 64.1% |
| **mixed_save** | 99.7% ±0.1 | 61.3% ±0.8 | 61.4% ±0.8 | 55.5% ±0.8 | – | 69.4% |

Games per pairing: 10,000.

## Equilibrium of the meta-game

If each player secretly picks a bot, this mix of bots can't be exploited: no single bot wins more than 50% against it. The bootstrap redraws every win rate within its margin 500 times and re-solves, to show how stable the answer is. The last column is each bot's win rate against the equilibrium mix (Nash averaging, Balduzzi et al. 2018): unlike the average against the field, it can't be inflated by adding weak bots.

| bot | equilibrium weight | bootstrap 95% range | in the mix (share of resamples) | win rate vs the mix |
|---|---|---|---|---|
| random | 0.0% | 0.0% – 0.0% | 0% | 0.3% |
| builder | 0.0% | 0.0% – 0.0% | 0% | 38.7% |
| blocker | 0.0% | 0.0% – 0.0% | 0% | 38.6% |
| mixed | 0.0% | 0.0% – 0.0% | 0% | 44.5% |
| mixed_save | 100.0% | 100.0% – 100.0% | 100% | 50.0% |

Game value: -0.0000 (a symmetric zero-sum game is worth 0).
Cross-check with nashpy's linear program: same mix, worst-case payoff +0.0000.

## Best responses

| against | best response | its win rate |
|---|---|---|
| random | mixed_save | 99.7% |
| builder | mixed_save | 61.3% |
| blocker | mixed_save | 61.4% |
| mixed | mixed_save | 55.5% |
| mixed_save | mixed_save | 50.0% |

9 of 10 pairings differ from 50% after a Holm correction for multiple comparisons.

Beats every other bot (Holm-corrected): mixed_save.
Rock-paper-scissors cycles (all three wins Holm-corrected): none.

## Skill ladder or cycles?

A rating per bot explains 99.4% of the variation in the win-rate matrix; the remaining 0.6% is cyclic (rock-paper-scissors). Rating = the bot's average edge over 50% across all bots, itself included.

| bot | rating |
|---|---|
| mixed_save | +15.6 points |
| mixed | +11.2 points |
| blocker | +6.5 points |
| builder | +5.9 points |
| random | -39.2 points |

## Replicator dynamics

A population starts evenly split between the bots; each bot's share grows in proportion to how much better than average it does. Shares at t = 300:

| bot | start | end |
|---|---|---|
| random | 20.0% | 0.0% |
| builder | 20.0% | 0.0% |
| blocker | 20.0% | 0.0% |
| mixed | 20.0% | 0.0% |
| mixed_save | 20.0% | 100.0% |

## Each strategy against mixed_save

mixed_save won the pilot, and each new idea is built on it, so this is what each idea adds (or costs). Significant = differs from 50% after the Holm correction.

| bot | win rate vs mixed_save | 95% margin | significant |
|---|---|---|---|
| mixed | 44.5% | ±0.8 | yes |
| builder | 38.7% | ±0.8 | yes |
| blocker | 38.6% | ±0.8 | yes |
| random | 0.3% | ±0.1 | yes |

## Jack timing

Each variant differs from mixed only in when it plays Jacks. Win rate against mixed:

| variant | win rate vs mixed | 95% margin |
|---|---|---|
| mixed_save | 55.5% | ±0.8 |

## First-move advantage

Win rate of the player who moves first. 50% means no advantage.

| games | first player wins | 95% range | games played |
|---|---|---|---|
| random vs itself | 53.3% | 52.3% – 54.3% | 10,000 |
| builder vs itself | 53.6% | 52.6% – 54.6% | 10,000 |
| blocker vs itself | 54.9% | 53.9% – 55.9% | 10,000 |
| mixed vs itself | 52.5% | 51.6% – 53.5% | 10,000 |
| mixed_save vs itself | 54.0% | 53.1% – 55.0% | 10,000 |
| all other games | 52.6% | 52.3% – 52.9% | 100,000 |

## Game length

Median length in plies (one ply = one player's turn).

| bot | against other bots | mirror matches |
|---|---|---|
| random | 47 | 80 |
| builder | 45 | 41 |
| blocker | 50 | 55 |
| mixed | 48 | 49 |
| mixed_save | 47 | 52 |

## Jack use

Average per game played.

What the Jacks achieved: the share of two-eyed Jacks that completed a sequence or blocked an opponent's four, and of one-eyed Jacks that broke an opponent's four.

| bot | two-eyed Jacks | finished a sequence | blocked a four | one-eyed Jacks | broke a four | dead cards traded |
|---|---|---|---|---|---|---|
| random | 1.14 | 2.0% | 3.4% | 1.10 | 24.3% | 0.79 |
| builder | 1.12 | 41.5% | 0.5% | 0.99 | 22.4% | 0.13 |
| blocker | 1.28 | 31.6% | 17.4% | 1.23 | 33.9% | 0.35 |
| mixed | 1.20 | 36.2% | 10.9% | 1.15 | 34.4% | 0.18 |
| mixed_save | 1.21 | 56.8% | 43.2% | 1.02 | 99.5% | 0.26 |

## Squares that win games

Share of 149,995 decided games in which the square was part of the winner's sequences. The four corners (free spaces) average 5.7%. Central squares lie on more of the 192 lines (up to 20, against 3 for a corner), so part of this is geometry; the next section separates the two.

| rank | square | row, col | lines through it | share |
|---|---|---|---|---|
| 1 | 5♥ | 4, 4 | 20 | 25.9% |
| 2 | 2♥ | 5, 4 | 20 | 25.7% |
| 3 | 4♥ | 4, 5 | 20 | 25.4% |
| 4 | 3♥ | 5, 5 | 20 | 24.5% |
| 5 | 8♥ | 6, 3 | 15 | 21.4% |
| 6 | 9♥ | 6, 4 | 17 | 21.4% |
| 7 | 7♥ | 5, 3 | 17 | 21.0% |
| 8 | 4♣ | 3, 4 | 17 | 20.8% |
| 9 | 6♥ | 4, 3 | 17 | 20.5% |
| 10 | 5♣ | 3, 3 | 15 | 20.1% |

## Squares beyond geometry

Random-vs-random games (9,995) show what geometry and luck alone produce. Lift = a square's share among strategic bots' wins (139,606 games) divided by its share under random play; above 1, strategy uses the square more than geometry predicts.

|  | square | row, col | lift |
|---|---|---|---|
| most | 2♥ | 5, 4 | ×1.46 |
| most | 8♥ | 6, 3 | ×1.42 |
| most | 9♥ | 6, 4 | ×1.40 |
| most | A♣ | 7, 5 | ×1.37 |
| most | 7♥ | 5, 3 | ×1.37 |
| least | 7♣ | 2, 0 | ×0.43 |
| least | 4♦ | 7, 9 | ×0.38 |
| least | 5♦ | 8, 9 | ×0.36 |
| least | 6♦ | 9, 8 | ×0.33 |
| least | 6♣ | 1, 0 | ×0.29 |

## Charts

![win_matrix.png](win_matrix.png)
![convergence.png](convergence.png)
![first_move.png](first_move.png)
![hot_squares.png](hot_squares.png)
![square_lift.png](square_lift.png)
