# Tournament summary

216,000 games between 8 bots (168,000 between different bots, 48,000 mirror matches). Draws: 0. Median game length: 51 turns (plies).

Settings: line values per bot (default), 2 sequences to win, first seed 800000, 3000 deals per pairing. Command: `python tournament.py --bots expert expert:adapt=0 expert:hand=0 expert:fork=0 expert:infer=0 expert:count=0,infer=0 counter mixed_save --deals 3000 --seed 800000 --out results/ablation/games.csv.gz`

## Win-rate matrix

Row bot's win rate against the column bot, with the 95% margin. Margins come from paired deals (each deal is played once from each seat).

| bot \ opponent | expert | expert:adapt=0 | expert:hand=0 | expert:fork=0 | expert:infer=0 | expert:count=0,infer=0 | counter | mixed_save | avg vs field |
|---|---|---|---|---|---|---|---|---|---|
| **expert** | – | 48.7% ±0.9 | 49.9% ±0.6 | 49.9% ±0.2 | 49.9% ±0.4 | 50.5% ±0.8 | 48.8% ±0.9 | 50.3% ±0.9 | 49.7% |
| **expert:adapt=0** | 51.3% ±0.9 | – | 50.2% ±0.9 | 51.3% ±0.9 | 50.9% ±0.9 | 51.4% ±0.9 | 49.9% ±0.7 | 51.4% ±0.8 | 50.9% |
| **expert:hand=0** | 50.1% ±0.6 | 49.8% ±0.9 | – | 49.9% ±0.7 | 50.0% ±0.7 | 51.0% ±0.8 | 49.3% ±0.9 | 50.6% ±0.9 | 50.1% |
| **expert:fork=0** | 50.1% ±0.2 | 48.7% ±0.9 | 50.1% ±0.7 | – | 49.9% ±0.4 | 50.6% ±0.8 | 49.1% ±0.9 | 50.4% ±0.9 | 49.8% |
| **expert:infer=0** | 50.2% ±0.4 | 49.1% ±0.9 | 50.0% ±0.7 | 50.2% ±0.4 | – | 50.5% ±0.8 | 48.9% ±0.9 | 50.6% ±0.9 | 49.9% |
| **expert:count=0,infer=0** | 49.5% ±0.8 | 48.6% ±0.9 | 49.0% ±0.8 | 49.4% ±0.8 | 49.5% ±0.8 | – | 47.7% ±0.9 | 49.6% ±0.9 | 49.1% |
| **counter** | 51.2% ±0.9 | 50.2% ±0.7 | 50.7% ±0.9 | 50.9% ±0.9 | 51.1% ±0.9 | 52.3% ±0.9 | – | 51.8% ±0.8 | 51.2% |
| **mixed_save** | 49.7% ±0.9 | 48.6% ±0.8 | 49.4% ±0.9 | 49.6% ±0.9 | 49.4% ±0.9 | 50.4% ±0.9 | 48.2% ±0.8 | – | 49.3% |

Games per pairing: 6,000.

## Equilibrium of the meta-game

If each player secretly picks a bot, this mix of bots can't be exploited: no single bot wins more than 50% against it. The bootstrap redraws every win rate within its margin 500 times and re-solves, to show how stable the answer is. The last column is each bot's win rate against the equilibrium mix (Nash averaging, Balduzzi et al. 2018): unlike the average against the field, it can't be inflated by adding weak bots.

| bot | equilibrium weight | bootstrap 95% range | in the mix (share of resamples) | win rate vs the mix |
|---|---|---|---|---|
| expert | 0.0% | 0.0% – 0.0% | 0% | 48.8% |
| expert:adapt=0 | 0.0% | 0.0% – 100.0% | 35% | 49.9% |
| expert:hand=0 | 0.0% | 0.0% – 45.8% | 12% | 49.3% |
| expert:fork=0 | 0.0% | 0.0% – 0.0% | 2% | 49.1% |
| expert:infer=0 | 0.0% | 0.0% – 0.0% | 2% | 48.9% |
| expert:count=0,infer=0 | 0.0% | 0.0% – 0.0% | 0% | 47.7% |
| counter | 100.0% | 0.0% – 100.0% | 77% | 50.0% |
| mixed_save | 0.0% | 0.0% – 0.0% | 0% | 48.2% |

Game value: -0.0000 (a symmetric zero-sum game is worth 0).
Cross-check with nashpy's linear program: same mix, worst-case payoff +0.0000.

## Best responses

| against | best response | its win rate |
|---|---|---|
| expert | expert:adapt=0 | 51.3% |
| expert:adapt=0 | counter | 50.2% |
| expert:hand=0 | counter | 50.7% |
| expert:fork=0 | expert:adapt=0 | 51.3% |
| expert:infer=0 | counter | 51.1% |
| expert:count=0,infer=0 | counter | 52.3% |
| counter | counter | 50.0% |
| mixed_save | counter | 51.8% |

3 of 28 pairings differ from 50% after a Holm correction for multiple comparisons.

Beats every other bot (Holm-corrected): none.
Rock-paper-scissors cycles (all three wins Holm-corrected): none.

## Skill ladder or cycles?

A rating per bot explains 95.3% of the variation in the win-rate matrix; the remaining 4.7% is cyclic (rock-paper-scissors). Rating = the bot's average edge over 50% across all bots, itself included.

| bot | rating |
|---|---|
| counter | +1.0 points |
| expert:adapt=0 | +0.8 points |
| expert:hand=0 | +0.1 points |
| expert:infer=0 | -0.1 points |
| expert:fork=0 | -0.1 points |
| expert | -0.3 points |
| mixed_save | -0.6 points |
| expert:count=0,infer=0 | -0.8 points |

## Replicator dynamics

A population starts evenly split between the bots; each bot's share grows in proportion to how much better than average it does. Shares at t = 300:

| bot | start | end |
|---|---|---|
| expert | 12.5% | 1.3% |
| expert:adapt=0 | 12.5% | 32.8% |
| expert:hand=0 | 12.5% | 5.9% |
| expert:fork=0 | 12.5% | 2.0% |
| expert:infer=0 | 12.5% | 2.4% |
| expert:count=0,infer=0 | 12.5% | 0.2% |
| counter | 12.5% | 55.0% |
| mixed_save | 12.5% | 0.4% |

## Each strategy against mixed_save

mixed_save won the pilot, and each new idea is built on it, so this is what each idea adds (or costs). Significant = differs from 50% after the Holm correction.

| bot | win rate vs mixed_save | 95% margin | significant |
|---|---|---|---|
| counter | 51.8% | ±0.8 | yes |
| expert:adapt=0 | 51.4% | ±0.8 | yes |
| expert:hand=0 | 50.6% | ±0.9 | no |
| expert:infer=0 | 50.6% | ±0.9 | no |
| expert:fork=0 | 50.4% | ±0.9 | no |
| expert | 50.3% | ±0.9 | no |
| expert:count=0,infer=0 | 49.6% | ±0.9 | no |

## First-move advantage

Win rate of the player who moves first. 50% means no advantage.

| games | first player wins | 95% range | games played |
|---|---|---|---|
| expert vs itself | 54.6% | 53.3% – 55.9% | 6,000 |
| expert:adapt=0 vs itself | 53.6% | 52.4% – 54.9% | 6,000 |
| expert:hand=0 vs itself | 53.9% | 52.7% – 55.2% | 6,000 |
| expert:fork=0 vs itself | 54.9% | 53.6% – 56.1% | 6,000 |
| expert:infer=0 vs itself | 54.4% | 53.2% – 55.7% | 6,000 |
| expert:count=0,infer=0 vs itself | 54.9% | 53.6% – 56.1% | 6,000 |
| counter vs itself | 54.0% | 52.7% – 55.2% | 6,000 |
| mixed_save vs itself | 54.7% | 53.4% – 56.0% | 6,000 |
| all other games | 54.6% | 54.3% – 54.8% | 168,000 |

## Game length

Median length in plies (one ply = one player's turn).

| bot | against other bots | mirror matches |
|---|---|---|
| expert | 51 | 51 |
| expert:adapt=0 | 51 | 50 |
| expert:hand=0 | 51 | 51 |
| expert:fork=0 | 51 | 51 |
| expert:infer=0 | 51 | 52 |
| expert:count=0,infer=0 | 52 | 53 |
| counter | 51 | 51 |
| mixed_save | 51 | 52 |

## Jack use

Average per game played.

What the Jacks achieved: the share of two-eyed Jacks that completed a sequence or blocked an opponent's four, and of one-eyed Jacks that broke an opponent's four.

| bot | two-eyed Jacks | finished a sequence | blocked a four | one-eyed Jacks | broke a four | dead cards traded |
|---|---|---|---|---|---|---|
| expert | 1.26 | 45.7% | 54.2% | 1.11 | 99.3% | 0.34 |
| expert:adapt=0 | 1.25 | 48.8% | 51.1% | 1.10 | 99.5% | 0.29 |
| expert:hand=0 | 1.27 | 45.9% | 54.0% | 1.11 | 99.4% | 0.32 |
| expert:fork=0 | 1.27 | 45.5% | 54.3% | 1.12 | 99.4% | 0.34 |
| expert:infer=0 | 1.27 | 45.4% | 54.5% | 1.13 | 99.3% | 0.34 |
| expert:count=0,infer=0 | 1.27 | 44.2% | 55.7% | 1.14 | 99.4% | 0.35 |
| counter | 1.26 | 48.5% | 51.4% | 1.12 | 99.5% | 0.29 |
| mixed_save | 1.26 | 45.3% | 54.6% | 1.15 | 99.1% | 0.37 |

## Squares that win games

Share of 216,000 decided games in which the square was part of the winner's sequences. The four corners (free spaces) average 5.6%. Central squares lie on more of the 192 lines (up to 20, against 3 for a corner), so part of this is geometry; the next section separates the two.

| rank | square | row, col | lines through it | share |
|---|---|---|---|---|
| 1 | 5♥ | 4, 4 | 20 | 23.8% |
| 2 | 2♥ | 5, 4 | 20 | 23.8% |
| 3 | 4♥ | 4, 5 | 20 | 23.3% |
| 4 | 3♥ | 5, 5 | 20 | 22.3% |
| 5 | 9♥ | 6, 4 | 17 | 20.5% |
| 6 | 7♥ | 5, 3 | 17 | 20.5% |
| 7 | 4♣ | 3, 4 | 17 | 20.1% |
| 8 | 8♥ | 6, 3 | 15 | 20.0% |
| 9 | 6♥ | 4, 3 | 17 | 19.6% |
| 10 | 10♥ | 6, 5 | 17 | 19.4% |

## Squares beyond geometry

Needs random-vs-random games (include `random` in the tournament) to separate strategy from geometry.

## Charts

![win_matrix.png](win_matrix.png)
![convergence.png](convergence.png)
![first_move.png](first_move.png)
![hot_squares.png](hot_squares.png)
