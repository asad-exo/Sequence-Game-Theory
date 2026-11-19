# Tournament summary

150,000 games between 5 bots (100,000 between different bots, 50,000 mirror matches). Draws: 3. Median game length: 58 turns (plies).

Settings: line values linear, 2 sequences to win, first seed 2026, 5000 deals per pairing. Command: `python tournament.py --roster pilot --values linear --deals 5000 --out results/values_linear/games.csv.gz`

## Win-rate matrix

Row bot's win rate against the column bot, with the 95% margin. Margins come from paired deals (each deal is played once from each seat).

| bot \ opponent | random | builder | blocker | mixed | mixed_save | avg vs field |
|---|---|---|---|---|---|---|
| **random** | – | 1.9% ±0.3 | 2.9% ±0.3 | 1.6% ±0.2 | 0.6% ±0.2 | 1.8% |
| **builder** | 98.1% ±0.3 | – | 49.2% ±0.9 | 37.6% ±0.8 | 29.6% ±0.8 | 53.6% |
| **blocker** | 97.0% ±0.3 | 50.8% ±0.9 | – | 40.4% ±0.8 | 29.7% ±0.8 | 54.5% |
| **mixed** | 98.4% ±0.2 | 62.4% ±0.8 | 59.6% ±0.8 | – | 41.0% ±0.8 | 65.4% |
| **mixed_save** | 99.4% ±0.2 | 70.4% ±0.8 | 70.3% ±0.8 | 59.0% ±0.8 | – | 74.8% |

Games per pairing: 10,000.

## Equilibrium of the meta-game

If each player secretly picks a bot, this mix of bots can't be exploited: no single bot wins more than 50% against it. The bootstrap redraws every win rate within its margin 500 times and re-solves, to show how stable the answer is. The last column is each bot's win rate against the equilibrium mix (Nash averaging, Balduzzi et al. 2018): unlike the average against the field, it can't be inflated by adding weak bots.

| bot | equilibrium weight | bootstrap 95% range | in the mix (share of resamples) | win rate vs the mix |
|---|---|---|---|---|
| random | 0.0% | 0.0% – 0.0% | 0% | 0.6% |
| builder | 0.0% | 0.0% – 0.0% | 0% | 29.6% |
| blocker | 0.0% | 0.0% – 0.0% | 0% | 29.7% |
| mixed | 0.0% | 0.0% – 0.0% | 0% | 41.0% |
| mixed_save | 100.0% | 100.0% – 100.0% | 100% | 50.0% |

Game value: -0.0000 (a symmetric zero-sum game is worth 0).
Cross-check with nashpy's linear program: same mix, worst-case payoff +0.0000.

## Best responses

| against | best response | its win rate |
|---|---|---|
| random | mixed_save | 99.4% |
| builder | mixed_save | 70.4% |
| blocker | mixed_save | 70.3% |
| mixed | mixed_save | 59.0% |
| mixed_save | mixed_save | 50.0% |

9 of 10 pairings differ from 50% after a Holm correction for multiple comparisons.

Beats every other bot (Holm-corrected): mixed_save.
Rock-paper-scissors cycles (all three wins Holm-corrected): none.

## Skill ladder or cycles?

A rating per bot explains 98.1% of the variation in the win-rate matrix; the remaining 1.9% is cyclic (rock-paper-scissors). Rating = the bot's average edge over 50% across all bots, itself included.

| bot | rating |
|---|---|
| mixed_save | +19.8 points |
| mixed | +12.3 points |
| blocker | +3.6 points |
| builder | +2.9 points |
| random | -38.6 points |

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
| mixed | 41.0% | ±0.8 | yes |
| blocker | 29.7% | ±0.8 | yes |
| builder | 29.6% | ±0.8 | yes |
| random | 0.6% | ±0.2 | yes |

## Jack timing

Each variant differs from mixed only in when it plays Jacks. Win rate against mixed:

| variant | win rate vs mixed | 95% margin |
|---|---|---|
| mixed_save | 59.0% | ±0.8 |

## First-move advantage

Win rate of the player who moves first. 50% means no advantage.

| games | first player wins | 95% range | games played |
|---|---|---|---|
| random vs itself | 52.4% | 51.4% – 53.4% | 10,000 |
| builder vs itself | 55.0% | 54.0% – 56.0% | 10,000 |
| blocker vs itself | 54.1% | 53.2% – 55.1% | 10,000 |
| mixed vs itself | 54.2% | 53.2% – 55.2% | 10,000 |
| mixed_save vs itself | 54.8% | 53.8% – 55.7% | 10,000 |
| all other games | 52.5% | 52.2% – 52.8% | 100,000 |

## Game length

Median length in plies (one ply = one player's turn).

| bot | against other bots | mirror matches |
|---|---|---|
| random | 54 | 80 |
| builder | 53 | 47 |
| blocker | 62 | 71 |
| mixed | 56 | 59 |
| mixed_save | 55 | 61 |

## Jack use

Average per game played.

What the Jacks achieved: the share of two-eyed Jacks that completed a sequence or blocked an opponent's four, and of one-eyed Jacks that broke an opponent's four.

| bot | two-eyed Jacks | finished a sequence | blocked a four | one-eyed Jacks | broke a four | dead cards traded |
|---|---|---|---|---|---|---|
| random | 1.23 | 2.0% | 3.0% | 1.19 | 16.3% | 0.87 |
| builder | 1.24 | 29.7% | 0.8% | 1.19 | 14.1% | 0.20 |
| blocker | 1.55 | 21.5% | 12.1% | 1.51 | 17.2% | 1.37 |
| mixed | 1.39 | 28.1% | 9.6% | 1.34 | 15.7% | 0.55 |
| mixed_save | 1.37 | 55.6% | 44.0% | 1.09 | 97.4% | 0.82 |

## Squares that win games

Share of 149,997 decided games in which the square was part of the winner's sequences. The four corners (free spaces) average 4.3%. Central squares lie on more of the 192 lines (up to 20, against 3 for a corner), so part of this is geometry; the next section separates the two.

| rank | square | row, col | lines through it | share |
|---|---|---|---|---|
| 1 | 5♥ | 4, 4 | 20 | 28.3% |
| 2 | 4♥ | 4, 5 | 20 | 27.8% |
| 3 | 2♥ | 5, 4 | 20 | 27.5% |
| 4 | 3♥ | 5, 5 | 20 | 27.2% |
| 5 | 9♥ | 6, 4 | 17 | 23.0% |
| 6 | 10♥ | 6, 5 | 17 | 22.4% |
| 7 | 7♥ | 5, 3 | 17 | 22.3% |
| 8 | 4♣ | 3, 4 | 17 | 22.2% |
| 9 | 6♥ | 4, 3 | 17 | 21.6% |
| 10 | 3♣ | 3, 5 | 17 | 21.4% |

## Squares beyond geometry

Random-vs-random games (9,998) show what geometry and luck alone produce. Lift = a square's share among strategic bots' wins (139,295 games) divided by its share under random play; above 1, strategy uses the square more than geometry predicts.

|  | square | row, col | lift |
|---|---|---|---|
| most | 2♥ | 5, 4 | ×1.56 |
| most | 9♥ | 6, 4 | ×1.53 |
| most | 4♥ | 4, 5 | ×1.48 |
| most | 5♥ | 4, 4 | ×1.48 |
| most | 3♥ | 5, 5 | ×1.48 |
| least | 2♠ | 0, 1 | ×0.34 |
| least | 10♠ | 1, 9 | ×0.33 |
| least | 6♦ | 9, 8 | ×0.32 |
| least | 6♣ | 1, 0 | ×0.32 |
| least | 5♦ | 8, 9 | ×0.30 |

## Charts

![win_matrix.png](win_matrix.png)
![convergence.png](convergence.png)
![first_move.png](first_move.png)
![hot_squares.png](hot_squares.png)
![square_lift.png](square_lift.png)
