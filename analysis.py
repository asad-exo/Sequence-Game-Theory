"""Analyse a tournament CSV with game theory.

    python analysis.py results/games.csv            # writes summary.md and the charts next to the CSV
    python analysis.py results/games.csv --out figs

Or step by step in a notebook:

    import analysis
    games = analysis.load_games("results/games.csv")
    M, half_width, n_games = analysis.win_matrix(games)
    mix, value = analysis.equilibrium(M)

What it computes:
- Win-rate matrix: how often each bot (row) beats each opponent (column). This is
  the payoff matrix of the "meta-game" where each player picks a bot.
- Equilibrium: the mix of bots no opponent can exploit (a Nash equilibrium of that
  symmetric zero-sum meta-game), plus a bootstrap showing how stable it is.
- Best responses, bots that beat everyone, and rock-paper-scissors cycles, with
  Holm-corrected tests so that many pairings don't produce false alarms.
- How much of the matrix is a skill ladder and how much is cycles.
- Replicator dynamics: which bots take over a population that copies winners.
- Each bot against mixed_save (the pilot champion), and the Jack-timing variants
  against mixed.
- First-move advantage from mirror matches; what each bot's Jacks achieved; which
  squares win games, with and without the board's geometry factored out.
- A convergence chart: how the headline estimate settles as deals accumulate.
"""

import argparse
import itertools
import math
import os

import numpy as np
import pandas as pd

from board import CELL_CARD, CORNERS, LINES_THROUGH, SIZE, pretty

Z = 1.96  # 95% confidence intervals


# ---- loading ------------------------------------------------------------------

def load_games(path):
    """Read a tournament CSV. Adds `score0`: 1 if seat 0 won, 0.5 for a draw, 0 if it lost."""
    games = pd.read_csv(path)
    games[["seqs0", "seqs1"]] = games[["seqs0", "seqs1"]].fillna("").astype(str)
    games["score0"] = games["winner_seat"].map({0: 1.0, 1: 0.0, -1: 0.5})
    return games.sort_values("game_id").reset_index(drop=True)


def bot_order(games):
    """Bots in the order they were given to tournament.py."""
    mirror = games.loc[games["mirror"] == 1, "seat0"]
    order = list(dict.fromkeys(mirror))
    for name in pd.concat([games["seat0"], games["seat1"]]):
        if name not in order:
            order.append(name)
    return order


# ---- the meta-game ------------------------------------------------------------

def win_matrix(games, bots=None):
    """Row bot's win rate against the column bot (draws count as half a win).

    Returns (M, half_width, n_games). half_width is the 95% confidence margin.
    Each deal is played twice with the seats swapped, so the margin is computed
    over deals (the average of the two games), which removes most of the luck of
    the deal.
    """
    bots = bots or bot_order(games)
    rank = {b: i for i, b in enumerate(bots)}
    pairs = games[(games["mirror"] == 0) & games["seat0"].isin(rank) & games["seat1"].isin(rank)]
    seat0_first = pairs["seat0"].map(rank) < pairs["seat1"].map(rank)
    table = pd.DataFrame({
        "a": np.where(seat0_first, pairs["seat0"], pairs["seat1"]),
        "b": np.where(seat0_first, pairs["seat1"], pairs["seat0"]),
        "seed": pairs["seed"],
        "score": np.where(seat0_first, pairs["score0"], 1 - pairs["score0"]),
    })
    per_deal = table.groupby(["a", "b", "seed"])["score"].agg(["mean", "size"])
    stats = per_deal.groupby(["a", "b"]).agg(mean=("mean", "mean"), sd=("mean", "std"),
                                             deals=("mean", "size"), games=("size", "sum"))

    M = pd.DataFrame(0.5, index=bots, columns=bots)
    half = pd.DataFrame(np.nan, index=bots, columns=bots)
    n = pd.DataFrame(0, index=bots, columns=bots)
    for (a, b), row in stats.iterrows():
        margin = Z * row["sd"] / np.sqrt(row["deals"]) if row["deals"] > 1 else np.nan
        M.loc[a, b], M.loc[b, a] = row["mean"], 1 - row["mean"]
        half.loc[a, b] = half.loc[b, a] = margin
        n.loc[a, b] = n.loc[b, a] = row["games"]
    for bot in bots:
        n.loc[bot, bot] = int(((games["mirror"] == 1) & (games["seat0"] == bot)).sum())
    return M, half, n


def equilibrium(M):
    """Nash equilibrium of the symmetric zero-sum game with payoffs M - 0.5.

    Solved as a linear program: maximise v such that the mix x scores at least v
    against every opponent. Returns (mix as a Series, game value). The value of a
    symmetric zero-sum game is 0, so v should come out at about 0.
    """
    from scipy.optimize import linprog

    A = M.to_numpy(dtype=float) - 0.5
    n = len(A)
    cost = np.zeros(n + 1)
    cost[-1] = -1.0                                         # maximise v
    a_ub = np.hstack([-A.T, np.ones((n, 1))])               # v - x.A[:, j] <= 0 for each j
    a_eq = np.hstack([np.ones((1, n)), np.zeros((1, 1))])   # the mix adds up to 1
    result = linprog(cost, A_ub=a_ub, b_ub=np.zeros(n), A_eq=a_eq, b_eq=[1.0],
                     bounds=[(0, 1)] * n + [(None, None)], method="highs")
    if not result.success:
        raise RuntimeError(result.message)
    mix = np.clip(result.x[:n], 0, None)
    mix[mix < 1e-9] = 0.0
    return pd.Series(mix / mix.sum(), index=M.index), result.x[-1]


def nashpy_check(M):
    """Solve the same game with nashpy. Returns (mix, worst-case payoff), or None if nashpy is missing."""
    try:
        import nashpy
        A = M.to_numpy(dtype=float) - 0.5
        row, _ = nashpy.Game(A).linear_program()
    except (ImportError, AttributeError):  # nashpy missing or too old
        return None
    return pd.Series(row, index=M.index), float((row @ A).min())


def bootstrap_equilibrium(M, half, reps=500, seed=0):
    """How stable is the equilibrium? Redraw every win rate within its sampling
    error and re-solve, `reps` times. Returns mean weight, 95% range, and how often
    each bot is part of the equilibrium mix (weight above 1%)."""
    rng = np.random.default_rng(seed)
    base = M.to_numpy(dtype=float)
    se = np.nan_to_num((half / Z).to_numpy(dtype=float))
    upper = np.triu_indices(len(base), 1)
    draws = []
    for _ in range(reps):
        sample = base.copy()
        sample[upper] = np.clip(base[upper] + rng.normal(0.0, se[upper]), 0, 1)
        sample[(upper[1], upper[0])] = 1 - sample[upper]
        mix, _ = equilibrium(pd.DataFrame(sample, index=M.index, columns=M.columns))
        draws.append(mix.to_numpy())
    draws = np.array(draws)
    return pd.DataFrame({
        "mean": draws.mean(axis=0),
        "low": np.percentile(draws, 2.5, axis=0),
        "high": np.percentile(draws, 97.5, axis=0),
        "in_mix": (draws > 0.01).mean(axis=0),
    }, index=M.index)


def best_responses(M):
    """For each opponent, the bot that beats it most often."""
    rows = []
    for opponent in M.columns:
        best = M[opponent].idxmax()
        rows.append({"opponent": opponent, "best_response": best, "win_rate": M.loc[best, opponent]})
    return pd.DataFrame(rows).set_index("opponent")


def pairwise_tests(M, half):
    """One row per pairing: the first bot's win rate, its z against 50%, the p-value,
    and the Holm-adjusted p-value over all pairings (Holm 1979). With many bots, some
    pairings cross the usual 95% line by luck alone; Holm's correction allows for that."""
    rows = []
    for a, b in itertools.combinations(M.index, 2):
        rate, se = float(M.loc[a, b]), float(half.loc[a, b]) / Z
        if not np.isfinite(se):
            z, p = float("nan"), 1.0
        elif se == 0:
            z, p = (float("inf"), 0.0) if rate != 0.5 else (0.0, 1.0)
        else:
            z = (rate - 0.5) / se
            p = math.erfc(abs(z) / math.sqrt(2))
        rows.append({"a": a, "b": b, "win_rate": rate, "z": z, "p": p})
    tests = pd.DataFrame(rows, columns=["a", "b", "win_rate", "z", "p"])
    adjusted, running, m = np.ones(len(tests)), 0.0, len(tests)
    for rank, i in enumerate(np.argsort(tests["p"].to_numpy(), kind="stable")):
        running = max(running, min(1.0, (m - rank) * tests["p"].iloc[i]))
        adjusted[i] = running
    tests["p_holm"] = adjusted
    return tests


def clear_wins(M, half, alpha=0.05):
    """Boolean matrix: True where the row bot beats the column bot, Holm-corrected."""
    wins = pd.DataFrame(False, index=M.index, columns=M.columns)
    for row in pairwise_tests(M, half).itertuples():
        if row.p_holm < alpha:
            if row.win_rate > 0.5:
                wins.loc[row.a, row.b] = True
            elif row.win_rate < 0.5:
                wins.loc[row.b, row.a] = True
    return wins


def transitivity(M):
    """Split the meta-game into a skill ladder and cycles.

    With A = M - 0.5, the ratings that best explain A are its row means r, and the
    ladder part is r_i - r_j; what is left is purely cyclic (rock-paper-scissors).
    This is the Hodge decomposition used by Balduzzi et al. (2018).
    Returns (ratings, share of A's variation explained by the ladder)."""
    A = M.to_numpy(dtype=float) - 0.5
    np.fill_diagonal(A, 0.0)
    r = A.mean(axis=1)
    ladder = r[:, None] - r[None, :]
    total = float((A ** 2).sum())
    share = float((ladder ** 2).sum()) / total if total > 0 else 1.0
    return pd.Series(r, index=M.index), share


def dominant_bots(M, half):
    """Bots that clearly beat every other bot."""
    wins = clear_wins(M, half)
    return [b for b in M.index if all(wins.loc[b, o] for o in M.columns if o != b)]


def cycles(M, half):
    """Rock-paper-scissors triples (a beats b, b beats c, c beats a), all clear wins."""
    wins = clear_wins(M, half)
    found = []
    for a, b, c in itertools.permutations(M.index, 3):
        if a == min(a, b, c, key=list(M.index).index) and wins.loc[a, b] and wins.loc[b, c] and wins.loc[c, a]:
            found.append((a, b, c))
    return found


def replicator(M, t_end=300.0, points=3001):
    """Replicator dynamics: a population starts evenly split between the bots, and
    each bot's share grows in proportion to how much better than average it scores.
    Returns population shares over time (rows = time). Needs nashpy."""
    import nashpy

    n = len(M)
    times = np.linspace(0.0, t_end, points)
    shares = nashpy.Game(M.to_numpy(dtype=float)).replicator_dynamics(
        y0=np.full(n, 1.0 / n), timepoints=times)
    return pd.DataFrame(shares, index=times, columns=M.index)


# ---- other questions -------------------------------------------------------------

def _estimate(label, scores):
    scores = pd.Series(scores, dtype=float)
    n = len(scores)
    mean = scores.mean() if n else np.nan
    margin = Z * scores.std() / np.sqrt(n) if n > 1 else np.nan
    return {"games": label, "first_player_win_rate": mean, "low": mean - margin, "high": mean + margin, "n": n}


def first_move(games, bots=None):
    """Win rate of the player who moves first. In a mirror match both seats run the
    same bot, so any edge for seat 0 is pure first-move advantage."""
    bots = bots or bot_order(games)
    mirror = games[games["mirror"] == 1]
    rows = [_estimate(f"{bot} vs itself", mirror.loc[mirror["seat0"] == bot, "score0"])
            for bot in bots if (mirror["seat0"] == bot).any()]
    rows.append(_estimate("all other games", games.loc[games["mirror"] == 0, "score0"]))
    return pd.DataFrame(rows).set_index("games")


def jack_usage(games, bots=None):
    """Per bot and per game: Jacks played, dead cards traded and, if the CSV has the
    columns (tournaments run after the pilot), what the Jacks achieved: two-eyed Jacks
    that finished a sequence or blocked an opponent four, and one-eyed Jacks that
    broke an opponent four."""
    bots = bots or bot_order(games)
    effects = "jack_finish0" in games.columns
    rows = []
    for bot in bots:
        parts = []
        for seat in (0, 1):
            mine = games[games[f"seat{seat}"] == bot]
            columns = {
                "two_eyed_jacks": mine[f"two_eyed{seat}"],
                "one_eyed_jacks": mine[f"one_eyed{seat}"],
                "dead_cards_traded": mine[f"dead_swaps{seat}"],
            }
            if effects:
                columns["wild_finished"] = mine[f"jack_finish{seat}"]
                columns["wild_blocked"] = mine[f"jack_block{seat}"]
                columns["removal_broke_four"] = mine[f"jack_break{seat}"]
            parts.append(pd.DataFrame(columns))
        rows.append(pd.concat(parts).mean().rename(bot))
    return pd.DataFrame(rows)


def versus(M, half, opponent):
    """Every other bot's win rate against `opponent`, with its 95% margin and whether
    it differs from 50% after the Holm correction."""
    tests = pairwise_tests(M, half)
    rows = []
    for bot in M.index:
        if bot == opponent:
            continue
        match = tests[((tests["a"] == bot) & (tests["b"] == opponent))
                      | ((tests["a"] == opponent) & (tests["b"] == bot))]
        rows.append({"bot": bot, "win_rate": M.loc[bot, opponent], "margin": half.loc[bot, opponent],
                     "significant": bool(len(match)) and bool(match["p_holm"].iloc[0] < 0.05)})
    return pd.DataFrame(rows).set_index("bot") if rows else pd.DataFrame()


def running_estimate(games, a, b):
    """a's running win rate against b, deal by deal (both seatings averaged), with
    a 95% band. Shows how the estimate settles as games accumulate."""
    pair = games[((games["seat0"] == a) & (games["seat1"] == b))
                 | ((games["seat0"] == b) & (games["seat1"] == a))]
    score = np.where(pair["seat0"] == a, pair["score0"], 1 - pair["score0"])
    per_deal = pd.Series(score, index=pair.index).groupby(pair["seed"]).mean().sort_index()
    n = np.arange(1, len(per_deal) + 1)
    mean = per_deal.cumsum().to_numpy() / n
    var = (per_deal.pow(2).cumsum().to_numpy() / n - mean ** 2) * n / np.maximum(n - 1, 1)
    margin = Z * np.sqrt(np.clip(var, 0, None) / n)
    margin[0] = np.nan
    return pd.DataFrame({"deals": n, "mean": mean, "low": mean - margin, "high": mean + margin})


def square_frequency(games, winner=None):
    """Share of decided games in which each square was part of the winner's sequences.

    Returns (10x10 array, number of decided games). Pass `winner` to look only at
    games won by one bot.
    """
    decided = games[games["winner_seat"] >= 0]
    if winner is not None:
        decided = decided[decided["winner"] == winner]
    return _square_counts(decided)


def _square_counts(decided):
    counts = np.zeros(SIZE * SIZE)
    for seat, s0, s1 in zip(decided["winner_seat"], decided["seqs0"], decided["seqs1"]):
        text = s0 if seat == 0 else s1
        cells = {int(c) for seq in text.split(";") if seq for c in seq.split("-")}
        counts[list(cells)] += 1
    return (counts / max(len(decided), 1)).reshape(SIZE, SIZE), len(decided)


LINES_PER_SQUARE = np.array([len(LINES_THROUGH[c]) for c in range(SIZE * SIZE)]).reshape(SIZE, SIZE)


def square_lift(games):
    """How much more often each square wins for strategic bots than for random play.

    Random-vs-random games show what board geometry and luck alone produce, so the
    ratio (strategic share / random share) is what strategy adds. Returns
    (lift 10x10, strategic games, random games), or None without random mirror games."""
    random_games = games[(games["seat0"] == "random") & (games["seat1"] == "random")
                         & (games["winner_seat"] >= 0)]
    strategic = games[(games["winner_seat"] >= 0) & (games["winner"] != "random")
                      & ~((games["seat0"] == "random") & (games["seat1"] == "random"))]
    if len(random_games) < 100 or len(strategic) < 100:
        return None
    base, n_random = _square_counts(random_games)
    freq, n_strategic = _square_counts(strategic)
    with np.errstate(divide="ignore", invalid="ignore"):
        lift = np.where(base > 0, freq / base, np.nan)
    for cell in CORNERS:
        lift[divmod(cell, SIZE)] = np.nan
    return lift, n_strategic, n_random


# ---- charts -----------------------------------------------------------------------

SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, NEUTRAL = "#e1e0d9", "#c3c2b7", "#f0efec"
BLUE, RED = "#2a78d6", "#e34948"
BLUE_RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
             "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]


def _pyplot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10,
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "axes.edgecolor": AXIS, "axes.titlecolor": INK,
    })
    return plt


def _ink_for(rgba):
    """White or ink text, whichever reads better on this fill."""
    from matplotlib.colors import to_rgb

    def luminance(color):
        channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in to_rgb(color)]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    fill = luminance(rgba)
    on_white = (1.05) / (fill + 0.05)
    on_ink = (fill + 0.05) / (luminance(INK) + 0.05)
    return "white" if on_white > on_ink else INK


def _titles(fig, ax, title, subtitle):
    """Left-aligned title and subtitle just above everything the axes draws."""
    to_fig = fig.transFigure.inverted()
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    content = ax.get_tightbbox(renderer).transformed(to_fig)
    left, top = content.x0, max(content.y1, ax.get_position().y1) + 0.025
    sub = fig.text(left, top, subtitle, ha="left", va="bottom", fontsize=9, color=INK2, linespacing=1.4)
    height = sub.get_window_extent(renderer).transformed(to_fig).height
    fig.text(left, top + height + 0.015, title, ha="left", va="bottom", fontsize=13,
             fontweight="bold", color=INK)


def _clean(ax):
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)


def plot_win_matrix(M, path):
    plt = _pyplot()
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    from matplotlib.patches import Rectangle
    from matplotlib.ticker import PercentFormatter

    bots = list(M.index)
    n = len(bots)
    values = M.to_numpy(dtype=float)
    off_diagonal = values[~np.eye(n, dtype=bool)]
    # Colour saturates 25 points from 50%, so close matchups stay readable even when
    # a weak bot (like random) loses almost every game. The numbers carry the rest.
    widest = float(np.abs(off_diagonal - 0.5).max())
    span = min(0.25, max(0.05, np.ceil(widest * 20) / 20))
    norm = TwoSlopeNorm(vcenter=0.5, vmin=0.5 - span, vmax=0.5 + span)
    cmap = LinearSegmentedColormap.from_list("win_rate", [RED, NEUTRAL, BLUE])

    fig, ax = plt.subplots(figsize=(1.05 * n + 3.0, 0.85 * n + 1.9))
    mesh = ax.pcolormesh(np.ma.masked_where(np.eye(n, dtype=bool), values), cmap=cmap, norm=norm,
                         edgecolors=SURFACE, linewidth=2)
    for i in range(n):
        ax.add_patch(Rectangle((i, i), 1, 1, facecolor=NEUTRAL, edgecolor=SURFACE, linewidth=2))
        for j in range(n):
            fill = NEUTRAL if i == j else cmap(norm(values[i, j]))
            ax.text(j + 0.5, i + 0.5, "–" if i == j else f"{values[i, j]:.0%}",
                    ha="center", va="center", fontsize=11, color=_ink_for(fill))
    ax.set_xlim(0, n)
    ax.set_ylim(n, 0)
    ax.set_xticks(np.arange(n) + 0.5, labels=bots, rotation=30, ha="right")
    ax.set_yticks(np.arange(n) + 0.5, labels=bots)
    ax.set_xlabel("Opponent")
    ax.set_ylabel("Bot")
    _clean(ax)
    bar = fig.colorbar(mesh, ax=ax, fraction=0.05, pad=0.03,
                       extend="both" if widest > span else "neither")
    bar.outline.set_visible(False)
    bar.ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    bar.ax.tick_params(length=0, colors=MUTED)
    bar.set_label("Bot's win rate", color=INK2)
    _titles(fig, ax, "Win rate of each bot (row) against each opponent (column)",
            "Blue: the row bot wins more often than not. Red: it loses more often. Draws count as half.")
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def plot_first_move(fm, path):
    plt = _pyplot()
    from matplotlib.ticker import MaxNLocator, PercentFormatter

    labels = list(fm.index)
    y = np.arange(len(labels))
    est, low, high = fm["first_player_win_rate"], fm["low"], fm["high"]
    reach = max(0.05, float(np.nanmax(np.abs(np.r_[low, high] - 0.5))) + 0.03)

    fig, ax = plt.subplots(figsize=(6.6, 0.48 * len(labels) + 1.3))
    ax.axvline(0.5, color=AXIS, linewidth=1, zorder=1)
    if len(labels) > 1:  # the pooled row is a different kind of estimate
        ax.axhline(len(labels) - 1.5, color=GRID, linewidth=1, zorder=1)
    ax.hlines(y, low, high, color=BLUE, linewidth=2, zorder=2)
    ax.plot(est, y, "o", color=BLUE, markersize=8, markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
    for yi, (e, h) in enumerate(zip(est, high)):
        ax.text(h + reach * 0.04, yi, f"{e:.1%}", va="center", fontsize=9, color=INK2)
    ax.set_yticks(y, labels=labels)
    ax.set_ylim(len(labels) - 0.5, -0.5)
    ax.set_xlim(0.5 - reach, 0.5 + reach)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=6, steps=[1, 2, 5, 10]))  # whole-percent ticks
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.tick_params(axis="x", colors=MUTED)
    ax.grid(axis="x", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.set_xlabel("Win rate of the player who moves first")
    _clean(ax)
    _titles(fig, ax, "Does moving first help?",
            "Mirror matches pit a bot against a copy of itself, so any gap from 50% is first-move "
            "advantage.\nLines show 95% confidence intervals.")
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def plot_hot_squares(freq, decided, path):
    plt = _pyplot()
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.patches import Rectangle
    from matplotlib.ticker import PercentFormatter

    corner = np.zeros((SIZE, SIZE), dtype=bool)
    for cell in CORNERS:
        corner[divmod(cell, SIZE)] = True
    squares = np.ma.masked_where(corner, freq)
    cmap = LinearSegmentedColormap.from_list("share", BLUE_RAMP)
    vmax = float(squares.max()) or 1.0

    fig, ax = plt.subplots(figsize=(7.0, 7.0))
    mesh = ax.pcolormesh(squares, cmap=cmap, vmin=0, vmax=vmax, edgecolors=SURFACE, linewidth=2)
    for cell in range(SIZE * SIZE):
        r, c = divmod(cell, SIZE)
        if corner[r, c]:
            ax.add_patch(Rectangle((c, r), 1, 1, facecolor=NEUTRAL, edgecolor=SURFACE, linewidth=2))
            fill = NEUTRAL
        else:
            fill = cmap(freq[r, c] / vmax)
        ax.text(c + 0.5, r + 0.5, pretty(CELL_CARD[cell]), ha="center", va="center", fontsize=9,
                color=_ink_for(fill))
    ax.set_xlim(0, SIZE)
    ax.set_ylim(SIZE, 0)
    ax.set_aspect("equal")
    ax.set_xticks(np.arange(SIZE) + 0.5, labels=range(SIZE))
    ax.set_yticks(np.arange(SIZE) + 0.5, labels=range(SIZE))
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.xaxis.tick_top()
    _clean(ax)
    bar = fig.colorbar(mesh, ax=ax, fraction=0.04, pad=0.03)
    bar.outline.set_visible(False)
    bar.ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    bar.ax.tick_params(length=0, colors=MUTED)
    bar.set_label("Share of decided games", color=INK2)
    corners = float(freq[corner].mean())
    _titles(fig, ax, "Which squares end up in winning sequences?",
            f"Share of {decided:,} decided games in which the square was part of the winner's sequences.\n"
            f"Corners (★) are free for everyone and left off the scale: on average {corners:.0%}.")
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def plot_square_lift(lift, n_strategic, n_random, path):
    """Diverging board map of log2(lift): blue = wins more often than under random play."""
    plt = _pyplot()
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    from matplotlib.patches import Rectangle
    from matplotlib.ticker import FuncFormatter

    with np.errstate(divide="ignore", invalid="ignore"):
        logs = np.log2(lift)
    finite = logs[np.isfinite(logs)]
    span = max(0.5, math.ceil(float(np.abs(finite).max()) * 2) / 2) if finite.size else 1.0
    norm = TwoSlopeNorm(vcenter=0.0, vmin=-span, vmax=span)
    cmap = LinearSegmentedColormap.from_list("lift", [RED, NEUTRAL, BLUE])
    masked = np.ma.masked_invalid(logs)

    fig, ax = plt.subplots(figsize=(7.0, 7.0))
    mesh = ax.pcolormesh(masked, cmap=cmap, norm=norm, edgecolors=SURFACE, linewidth=2)
    for cell in range(SIZE * SIZE):
        r, c = divmod(cell, SIZE)
        if not np.isfinite(logs[r, c]):
            ax.add_patch(Rectangle((c, r), 1, 1, facecolor=NEUTRAL, edgecolor=SURFACE, linewidth=2))
            fill = NEUTRAL
        else:
            fill = cmap(norm(logs[r, c]))
        ax.text(c + 0.5, r + 0.5, pretty(CELL_CARD[cell]), ha="center", va="center", fontsize=9,
                color=_ink_for(fill))
    ax.set_xlim(0, SIZE)
    ax.set_ylim(SIZE, 0)
    ax.set_aspect("equal")
    ax.set_xticks(np.arange(SIZE) + 0.5, labels=range(SIZE))
    ax.set_yticks(np.arange(SIZE) + 0.5, labels=range(SIZE))
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.xaxis.tick_top()
    _clean(ax)
    bar = fig.colorbar(mesh, ax=ax, fraction=0.04, pad=0.03)
    bar.outline.set_visible(False)
    bar.ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"×{2 ** v:.2g}"))
    bar.ax.tick_params(length=0, colors=MUTED)
    bar.set_label("Wins relative to random play", color=INK2)
    _titles(fig, ax, "Where strategy, not geometry, wins games",
            f"How often each square is in a winning sequence for strategic bots ({n_strategic:,} games),\n"
            f"relative to random-vs-random games ({n_random:,}), which show geometry and luck alone. "
            "Blue: more, red: less.")
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def plot_convergence(est, a, b, path):
    """Running win rate of a against b, with its 95% band, on a log axis of deals."""
    plt = _pyplot()
    from matplotlib.ticker import FuncFormatter, PercentFormatter

    final = float(est["mean"].iloc[-1])
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.axhline(0.5, color=AXIS, linewidth=1, zorder=1)
    ax.fill_between(est["deals"], est["low"], est["high"], color=BLUE, alpha=0.12, linewidth=0, zorder=2)
    ax.plot(est["deals"], est["mean"], color=BLUE, linewidth=2, solid_capstyle="round", zorder=3)
    ax.text(est["deals"].iloc[-1] * 1.08, final, f"{final:.1%}", va="center", fontsize=9, color=INK2)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Deals played (each once from each seat)")
    ax.set_ylabel(f"{a} win rate")
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED)
    _clean(ax)
    _titles(fig, ax, f"The {a} vs {b} estimate settles as deals accumulate",
            f"Running win rate of {a} against {b}, with its 95% band. The grey line marks 50%.")
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


# ---- the report ---------------------------------------------------------------------

def _pct(x, digits=1):
    return "n/a" if pd.isna(x) else f"{100 * x:.{digits}f}%"


def _md_table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def summarize(games, out_dir, make_charts=True, run_info=None):
    """Run every analysis, write the charts, and return the report as Markdown.

    `run_info` is the dict tournament.py saves next to the CSV, if available."""
    bots = bot_order(games)
    M, half, n = win_matrix(games, bots)
    pair_games = games[games["mirror"] == 0]
    draws = int((games["winner_seat"] == -1).sum())
    out = ["# Tournament summary", ""]
    out.append(f"{len(games):,} games between {len(bots)} bots ({len(pair_games):,} between different bots, "
               f"{len(games) - len(pair_games):,} mirror matches). Draws: {draws:,}. "
               f"Median game length: {games['turns'].median():.0f} turns (plies).")
    if run_info:
        out += ["", f"Settings: line values {run_info.get('values') or 'per bot (default)'}, "
                f"{run_info.get('sequences_to_win', 2)} sequences to win, first seed {run_info.get('seed')}, "
                f"{run_info.get('deals')} deals per pairing. Command: `{run_info.get('command', '')}`"]

    if len(bots) >= 2:
        out += ["", "## Win-rate matrix", "",
                "Row bot's win rate against the column bot, with the 95% margin. "
                "Margins come from paired deals (each deal is played once from each seat).", ""]
        rows = []
        for a in bots:
            cells = []
            for b in bots:
                cells.append("–" if a == b else f"{_pct(M.loc[a, b])} ±{100 * half.loc[a, b]:.1f}")
            rows.append([f"**{a}**"] + cells + [_pct(M.loc[a, [b for b in bots if b != a]].mean())])
        out.append(_md_table(["bot \\ opponent"] + bots + ["avg vs field"], rows))
        games_per_pair = sorted({int(n.loc[a, b]) for a, b in itertools.combinations(bots, 2)})
        out += ["", f"Games per pairing: {', '.join(f'{g:,}' for g in games_per_pair)}."]

        mix, value = equilibrium(M)
        boot = bootstrap_equilibrium(M, half)
        out += ["", "## Equilibrium of the meta-game", "",
                "If each player secretly picks a bot, this mix of bots can't be exploited: no single "
                "bot wins more than 50% against it. The bootstrap redraws every win rate within its "
                "margin 500 times and re-solves, to show how stable the answer is.", ""]
        out.append(_md_table(
            ["bot", "equilibrium weight", "bootstrap 95% range", "in the mix (share of resamples)"],
            [[b, _pct(mix[b]), f"{_pct(boot.loc[b, 'low'])} – {_pct(boot.loc[b, 'high'])}",
              _pct(boot.loc[b, "in_mix"], 0)] for b in bots]))
        out.append(f"\nGame value: {value:+.4f} (a symmetric zero-sum game is worth 0).")
        check = nashpy_check(M)
        if check is not None:
            nash_mix, nash_worst = check
            same = np.allclose(nash_mix.to_numpy(), mix.to_numpy(), atol=1e-6)
            out.append(f"Cross-check with nashpy's linear program: "
                       f"{'same mix' if same else 'a different mix (the game has several equilibria)'}, "
                       f"worst-case payoff {nash_worst:+.4f}.")

        out += ["", "## Best responses", ""]
        br = best_responses(M)
        out.append(_md_table(["against", "best response", "its win rate"],
                             [[opp, row["best_response"], _pct(row["win_rate"])] for opp, row in br.iterrows()]))
        tests = pairwise_tests(M, half)
        dominant = dominant_bots(M, half)
        found = cycles(M, half)
        out += ["", f"{int((tests['p_holm'] < 0.05).sum())} of {len(tests)} pairings differ from 50% "
                "after a Holm correction for multiple comparisons.",
                "", "Beats every other bot (Holm-corrected): " + (", ".join(dominant) or "none") + ".",
                "Rock-paper-scissors cycles (all three wins Holm-corrected): "
                + ("; ".join(" > ".join(c + (c[0],)) for c in found) or "none") + "."]

        ratings, ladder_share = transitivity(M)
        out += ["", "## Skill ladder or cycles?", "",
                f"A rating per bot explains {_pct(ladder_share)} of the variation in the win-rate matrix; "
                f"the remaining {_pct(1 - ladder_share)} is cyclic (rock-paper-scissors). Rating = the "
                "bot's average edge over 50% across all bots, itself included.", ""]
        out.append(_md_table(["bot", "rating"],
                             [[b, f"{100 * ratings[b]:+.1f} points"] for b in ratings.sort_values(ascending=False).index]))

        try:
            shares = replicator(M)
        except (ImportError, AttributeError):  # needs nashpy
            shares = None
        if shares is not None:
            final = shares.iloc[-1]
            out += ["", "## Replicator dynamics", "",
                    "A population starts evenly split between the bots; each bot's share grows in "
                    "proportion to how much better than average it does. Shares at t = "
                    f"{shares.index[-1]:.0f}:", ""]
            out.append(_md_table(["bot", "start", "end"], [[b, _pct(1 / len(bots)), _pct(final[b])] for b in bots]))

        if "mixed_save" in bots and len(bots) > 2:
            vs = versus(M, half, "mixed_save")
            out += ["", "## Each strategy against mixed_save", "",
                    "mixed_save won the pilot, and each new idea is built on it, so this is what each "
                    "idea adds (or costs). Significant = differs from 50% after the Holm correction.", ""]
            out.append(_md_table(["bot", "win rate vs mixed_save", "95% margin", "significant"],
                                 [[b, _pct(r["win_rate"]), f"±{100 * r['margin']:.1f}", "yes" if r["significant"] else "no"]
                                  for b, r in vs.sort_values("win_rate", ascending=False).iterrows()]))

        timing = [b for b in ("eager", "save_wild", "save_remove", "mixed_save") if b in bots]
        if "mixed" in bots and timing:
            out += ["", "## Jack timing", "",
                    "Each variant differs from mixed only in when it plays Jacks. Win rate against mixed:", ""]
            out.append(_md_table(["variant", "win rate vs mixed", "95% margin"],
                                 [[b, _pct(M.loc[b, "mixed"]), f"±{100 * half.loc[b, 'mixed']:.1f}"] for b in timing]))

    fm = first_move(games, bots)
    out += ["", "## First-move advantage", "",
            "Win rate of the player who moves first. 50% means no advantage.", ""]
    out.append(_md_table(["games", "first player wins", "95% range", "games played"],
                         [[label, _pct(r["first_player_win_rate"]), f"{_pct(r['low'])} – {_pct(r['high'])}",
                           f"{int(r['n']):,}"] for label, r in fm.iterrows()]))

    jacks = jack_usage(games, bots)
    out += ["", "## Jack use", "", "Average per game played."]
    if "wild_finished" in jacks.columns:
        out += ["", "What the Jacks achieved: the share of two-eyed Jacks that completed a sequence or "
                "blocked an opponent's four, and of one-eyed Jacks that broke an opponent's four.", ""]

        def share(part, whole):
            return _pct(part / whole) if whole > 0 else "n/a"

        out.append(_md_table(
            ["bot", "two-eyed Jacks", "finished a sequence", "blocked a four", "one-eyed Jacks",
             "broke a four", "dead cards traded"],
            [[b, f"{r['two_eyed_jacks']:.2f}", share(r["wild_finished"], r["two_eyed_jacks"]),
              share(r["wild_blocked"], r["two_eyed_jacks"]), f"{r['one_eyed_jacks']:.2f}",
              share(r["removal_broke_four"], r["one_eyed_jacks"]), f"{r['dead_cards_traded']:.2f}"]
             for b, r in jacks.iterrows()]))
    else:
        out += ["", _md_table(["bot", "two-eyed Jacks", "one-eyed Jacks", "dead cards traded"],
                              [[b, f"{r['two_eyed_jacks']:.2f}", f"{r['one_eyed_jacks']:.2f}",
                                f"{r['dead_cards_traded']:.2f}"] for b, r in jacks.iterrows()])]

    freq, decided = square_frequency(games)
    corner = set(CORNERS)
    ranked = sorted((c for c in range(SIZE * SIZE) if c not in corner), key=lambda c: -freq.flat[c])
    out += ["", "## Squares that win games", "",
            f"Share of {decided:,} decided games in which the square was part of the winner's sequences. "
            f"The four corners (free spaces) average {_pct(np.mean([freq.flat[c] for c in CORNERS]))}. "
            "Central squares lie on more of the 192 lines (up to 20, against 3 for a corner), so part "
            "of this is geometry; the next section separates the two.", ""]
    out.append(_md_table(["rank", "square", "row, col", "lines through it", "share"],
                         [[i + 1, pretty(CELL_CARD[c]), f"{c // SIZE}, {c % SIZE}",
                           int(LINES_PER_SQUARE.flat[c]), _pct(freq.flat[c])]
                          for i, c in enumerate(ranked[:10])]))

    lifted = square_lift(games)
    if lifted is None:
        out += ["", "## Squares beyond geometry", "",
                "Needs random-vs-random games (include `random` in the tournament) to separate "
                "strategy from geometry."]
    else:
        lift, n_strategic, n_random = lifted
        cells = [c for c in range(SIZE * SIZE) if np.isfinite(lift.flat[c])]
        by_lift = sorted(cells, key=lambda c: -lift.flat[c])
        out += ["", "## Squares beyond geometry", "",
                f"Random-vs-random games ({n_random:,}) show what geometry and luck alone produce. "
                f"Lift = a square's share among strategic bots' wins ({n_strategic:,} games) divided by "
                "its share under random play; above 1, strategy uses the square more than geometry predicts.", ""]
        out.append(_md_table(["", "square", "row, col", "lift"],
                             [["most", pretty(CELL_CARD[c]), f"{c // SIZE}, {c % SIZE}", f"×{lift.flat[c]:.2f}"]
                              for c in by_lift[:5]]
                             + [["least", pretty(CELL_CARD[c]), f"{c // SIZE}, {c % SIZE}", f"×{lift.flat[c]:.2f}"]
                                for c in by_lift[-5:]]))

    if make_charts:
        charts = []
        if len(bots) >= 2:
            plot_win_matrix(M, os.path.join(out_dir, "win_matrix.png"))
            charts.append("win_matrix.png")
            averages = {b: M.loc[b, [o for o in bots if o != b]].mean() for b in bots}
            top = sorted(bots, key=lambda b: -averages[b])[:2]
            est = running_estimate(games, top[0], top[1])
            if len(est) >= 10:
                plot_convergence(est, top[0], top[1], os.path.join(out_dir, "convergence.png"))
                charts.append("convergence.png")
        plot_first_move(fm, os.path.join(out_dir, "first_move.png"))
        plot_hot_squares(freq, decided, os.path.join(out_dir, "hot_squares.png"))
        charts += ["first_move.png", "hot_squares.png"]
        if lifted is not None:
            plot_square_lift(*lifted, os.path.join(out_dir, "square_lift.png"))
            charts.append("square_lift.png")
        out += ["", "## Charts", ""] + [f"![{name}]({name})" for name in charts]
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analyse a Sequence tournament CSV.")
    parser.add_argument("csv", nargs="?", default=os.path.join("results", "games.csv"))
    parser.add_argument("--out", help="folder for summary.md and charts (default: next to the CSV)")
    parser.add_argument("--no-charts", action="store_true")
    args = parser.parse_args(argv)
    out_dir = args.out or os.path.dirname(args.csv) or "."
    os.makedirs(out_dir, exist_ok=True)
    run_info = None
    info_path = os.path.splitext(args.csv)[0] + "_run.json"
    if os.path.exists(info_path):
        import json
        with open(info_path, encoding="utf-8") as f:
            run_info = json.load(f)
    report = summarize(load_games(args.csv), out_dir, make_charts=not args.no_charts, run_info=run_info)
    path = os.path.join(out_dir, "summary.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"Saved {path}" + ("" if args.no_charts else " and the charts in " + out_dir))


if __name__ == "__main__":
    main()
