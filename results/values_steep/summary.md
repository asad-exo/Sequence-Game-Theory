# Tournament summary

150,000 games between 5 bots (100,000 between different bots, 50,000 mirror matches). Draws: 2. Median game length: 49 turns (plies).

Settings: line values steep, 2 sequences to win, first seed 2026, 5000 deals per pairing. Command: `python tournament.py --roster pilot --values steep --deals 5000 --out results/values_steep/games.csv.gz`

## Win-rate matrix

Row bot's win rate against the column bot, with the 95% margin. Margins come from paired deals (each deal is played once from each seat).

| bot \ opponent | random | builder | blocker | mixed | mixed_save | avg vs field |
|---|---|---|---|---|---|---|
| **random** | – | 1.6% ±0.2 | 0.9% ±0.2 | 1.0% ±0.2 | 0.4% ±0.1 | 1.0% |
| **builder** | 98.5% ±0.2 | – | 46.7% ±0.8 | 42.9% ±0.8 | 38.7% ±0.8 | 56.7% |
| **blocker** | 99.1% ±0.2 | 53.3% ±0.8 | – | 47.7% ±0.8 | 41.3% ±0.8 | 60.4% |
| **mixed** | 99.0% ±0.2 | 57.1% ±0.8 | 52.3% ±0.8 | – | 44.8% ±0.8 | 63.3% |
| **mixed_save** | 99.6% ±0.1 | 61.3% ±0.8 | 58.7% ±0.8 | 55.2% ±0.8 | – | 68.7% |

Games per pairing: 10,000.

## Equilibrium of the meta-game

If each player secretly picks a bot, this mix of bots can't be exploited: no single bot wins more than 50% against it. The bootstrap redraws every win rate within its margin 500 times and re-solves, to show how stable the answer is. The last column is each bot's win rate against the equilibrium mix (Nash averaging, Balduzzi et al. 2018): unlike the average against the field, it can't be inflated by adding weak bots.

| bot | equilibrium weight | bootstrap 95% range | in the mix (share of resamples) | win rate vs the mix |
|---|---|---|---|---|
| random | 0.0% | 0.0% – 0.0% | 0% | 0.4% |
| builder | 0.0% | 0.0% – 0.0% | 0% | 38.7% |
| blocker | 0.0% | 0.0% – 0.0% | 0% | 41.3% |
| mixed | 0.0% | 0.0% – 0.0% | 0% | 44.8% |
| mixed_save | 100.0% | 100.0% – 100.0% | 100% | 50.0% |

Game value: -0.0000 (a symmetric zero-sum game is worth 0).
Cross-check with nashpy's linear program: same mix, worst-case payoff +0.0000.

## Best responses

| against | best response | its win rate |
|---|---|---|
| random | mixed_save | 99.6% |
| builder | mixed_save | 61.3% |
| blocker | mixed_save | 58.7% |
| mixed | mixed_save | 55.2% |
| mixed_save | mixed_save | 50.0% |

10 of 10 pairings differ from 50% after a Holm correction for multiple comparisons.

Beats every other bot (Holm-corrected): mixed_save.
Rock-paper-scissors cycles (all three wins Holm-corrected): none.

## Skill ladder or cycles?

A rating per bot explains 99.5% of the variation in the win-rate matrix; the remaining 0.5% is cyclic (rock-paper-scissors). Rating = the bot's average edge over 50% across all bots, itself included.

| bot | rating |
|---|---|
| mixed_save | +15.0 points |
| mixed | +10.6 points |
| blocker | +8.3 points |
| builder | +5.3 points |
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
| mixed | 44.8% | ±0.8 | yes |
| blocker | 41.3% | ±0.8 | yes |
| builder | 38.7% | ±0.8 | yes |
| random | 0.4% | ±0.1 | yes |

## Jack timing

Each variant differs from mixed only in when it plays Jacks. Win rate against mixed:

| variant | win rate vs mixed | 95% margin |
|---|---|---|
| mixed_save | 55.2% | ±0.8 |

## First-move advantage

Win rate of the player who moves first. 50% means no advantage.

| games | first player wins | 95% range | games played |
|---|---|---|---|
| random vs itself | 52.4% | 51.4% – 53.4% | 10,000 |
| builder vs itself | 54.4% | 53.4% – 55.4% | 10,000 |
| blocker vs itself | 54.4% | 53.4% – 55.4% | 10,000 |
| mixed vs itself | 53.1% | 52.1% – 54.1% | 10,000 |
| mixed_save vs itself | 54.5% | 53.6% – 55.5% | 10,000 |
| all other games | 52.3% | 52.0% – 52.6% | 100,000 |

## Game length

Median length in plies (one ply = one player's turn).

| bot | against other bots | mirror matches |
|---|---|---|
| random | 47 | 80 |
| builder | 46 | 41 |
| blocker | 50 | 53 |
| mixed | 48 | 49 |
| mixed_save | 48 | 52 |

## Jack use

Average per game played.

What the Jacks achieved: the share of two-eyed Jacks that completed a sequence or blocked an opponent's four, and of one-eyed Jacks that broke an opponent's four.

| bot | two-eyed Jacks | finished a sequence | blocked a four | one-eyed Jacks | broke a four | dead cards traded |
|---|---|---|---|---|---|---|
| random | 1.15 | 2.0% | 3.3% | 1.10 | 25.0% | 0.78 |
| builder | 1.13 | 42.4% | 0.5% | 0.98 | 21.4% | 0.14 |
| blocker | 1.27 | 33.9% | 17.3% | 1.20 | 35.0% | 0.28 |
| mixed | 1.22 | 37.3% | 10.8% | 1.14 | 35.3% | 0.18 |
| mixed_save | 1.22 | 56.5% | 43.5% | 1.03 | 99.7% | 0.23 |

## Squares that win games

Share of 149,998 decided games in which the square was part of the winner's sequences. The four corners (free spaces) average 6.8%. Central squares lie on more of the 192 lines (up to 20, against 3 for a corner), so part of this is geometry; the next section separates the two.

| rank | square | row, col | lines through it | share |
|---|---|---|---|---|
| 1 | 4♥ | 4, 5 | 20 | 25.3% |
| 2 | 5♥ | 4, 4 | 20 | 25.1% |
| 3 | 2♥ | 5, 4 | 20 | 25.0% |
| 4 | 3♥ | 5, 5 | 20 | 23.5% |
| 5 | 8♥ | 6, 3 | 15 | 20.7% |
| 6 | 9♥ | 6, 4 | 17 | 19.8% |
| 7 | 7♥ | 5, 3 | 17 | 19.8% |
| 8 | 5♣ | 3, 3 | 15 | 19.7% |
| 9 | 4♣ | 3, 4 | 17 | 19.5% |
| 10 | 6♥ | 4, 3 | 17 | 19.4% |

## Squares beyond geometry

Random-vs-random games (9,998) show what geometry and luck alone produce. Lift = a square's share among strategic bots' wins (139,613 games) divided by its share under random play; above 1, strategy uses the square more than geometry predicts.

|  | square | row, col | lift |
|---|---|---|---|
| most | 8♥ | 6, 3 | ×1.44 |
| most | 2♥ | 5, 4 | ×1.41 |
| most | 10♣ | 7, 2 | ×1.35 |
| most | 4♥ | 4, 5 | ×1.34 |
| most | 9♣ | 6, 2 | ×1.32 |
| least | 7♣ | 2, 0 | ×0.50 |
| least | 4♦ | 7, 9 | ×0.49 |
| least | 6♦ | 9, 8 | ×0.48 |
| least | 5♦ | 8, 9 | ×0.43 |
| least | 6♣ | 1, 0 | ×0.38 |

## Charts

![win_matrix.png](win_matrix.png)
![convergence.png](convergence.png)
![first_move.png](first_move.png)
![hot_squares.png](hot_squares.png)
![square_lift.png](square_lift.png)
