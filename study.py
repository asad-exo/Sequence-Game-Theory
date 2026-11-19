"""Rebuild the whole study from the game logs in results/, with one command.

    python study.py               # each run's report, the comparisons and the cross-run figures
    python study.py --skip-runs   # only the comparisons and the cross-run figures (faster)

It writes:
- results/<run>/summary.md and charts, for every run folder with a game log (analysis.py)
- results/<run>/comparison.md for the replication, line-value and rule-variant runs,
  each compared with the pilot (compare_runs.py)
- figures/*.png, the cross-run figures shown in FINDINGS.md
- results/README.md, an index of the runs plus every table behind the figures

Missing runs are skipped, so it also works on a partial set of results. The commands
that produced each run are in the run's games_run.json and in the README.
"""

import argparse
import itertools
import json
import math
import os

import numpy as np
import pandas as pd

import analysis
import compare_runs
from analysis import (AXIS, BLUE, GRID, INK2, MUTED, RED, SURFACE, Z, _clean, _md_table, _pct,
                      _pyplot, _titles)
from bots import heuristic_settings
from tournament import run_info_path

ORANGE, AQUA, YELLOW = "#eb6834", "#1baf7a", "#eda100"  # categorical slots 2-4 (slot 1 is BLUE)
OTHER = "#c3c2b7"                                       # the remainder in a segmented bar

RUNS = {  # folder -> what the run tests, in reading order
    "pilot": "The five pilot strategies, 5,000 deals",
    "full": "All 18 fast strategies",
    "replication": "The pilot again, on 5,000 fresh deals",
    "replication2": "The pilot a third time, on another 5,000 fresh deals",
    "values_linear": "The pilot with linear line values (1, 2, 3, 4)",
    "values_flat": "The pilot with flat line values (1, 2, 4, 8)",
    "values_steep": "The pilot with steep line values (1, 10, 100, 1000)",
    "one_sequence": "The pilot under the rule variant: first to one sequence wins",
    "jacks": "The five Jack-timing policies",
    "sweep_defend": "mixed_save with defence weights from 0 to 4",
    "sweep_lambda": "Logit (noisy) choice with lambda from 0.03 to 10, and mixed_save",
    "counting": "Head to head at 15,000 deals: is card counting's edge real?",
    "defence_counting": "Card counting x doubled defence, head to head at 10,000 deals",
    "ablation": "expert with one component removed at a time",
    "sampler": "Monte Carlo lookahead against the strongest heuristic bots",
    "hunt": "Counter-strategy hunt (double oracle) from the full tournament's equilibrium",
    "hunt_wide": "Counter-strategy hunt from a wider starting pool",
}
VERSUS_PILOT = ["replication", "replication2", "values_linear", "values_flat", "values_steep", "one_sequence"]
SCALES = ["linear", "flat", "default", "steep"]


# ---- the runs ------------------------------------------------------------------------

class Run:
    """One results folder: its game log, settings, and (cached) win-rate matrix."""

    def __init__(self, name, path, info):
        self.name, self.path, self.info = name, path, info
        self.folder = os.path.dirname(path)
        self.is_hunt = os.path.exists(os.path.join(self.folder, "hunt_log.json"))
        self._games = self._matrix = None

    @property
    def games(self):
        if self._games is None:
            self._games = analysis.load_games(self.path)
        return self._games

    @property
    def bots(self):
        return analysis.bot_order(self.games)

    def matrix(self):
        """(M, half_width, n_games), as analysis.win_matrix returns them."""
        if self._matrix is None:
            self._matrix = analysis.win_matrix(self.games, self.bots)
        return self._matrix


def find_runs(results):
    runs = {}
    for name in sorted(os.listdir(results)) if os.path.isdir(results) else []:
        for file in ("games.csv.gz", "games.csv"):
            path = os.path.join(results, name, file)
            if os.path.exists(path):
                info = {}
                if os.path.exists(run_info_path(path)):
                    with open(run_info_path(path), encoding="utf-8") as f:
                        info = json.load(f)
                runs[name] = Run(name, path, info)
                break
    order = [n for n in RUNS if n in runs] + [n for n in runs if n not in RUNS]
    return {n: runs[n] for n in order}


def field_average(M, half):
    """Each bot's mean win rate against all other bots, and its standard error
    (the pairings are independent games, so their variances add)."""
    rows = {}
    for b in M.index:
        others = [o for o in M.index if o != b]
        se = math.sqrt(sum((float(half.loc[b, o]) / Z) ** 2 for o in others)) / len(others)
        rows[b] = {"avg": float(M.loc[b, others].mean()), "se": se}
    return pd.DataFrame(rows).T


def setting(spec, key, default):
    """A heuristic spec's value for one setting, e.g. setting('mixed_save:defend=2', 'defend', 1.0)."""
    return heuristic_settings(spec).get(key, default)


def rate(M, half, a, b):
    return f"{_pct(M.loc[a, b])} ±{100 * half.loc[a, b]:.1f}"


def ranking_text(avg):
    return " > ".join(avg.sort_values("avg", ascending=False).index)


def mix_text(mix):
    return ", ".join(f"{b} {100 * w:.0f}%" for b, w in mix.sort_values(ascending=False).items() if w > 0.005)


# ---- figures -------------------------------------------------------------------------

def _save(plt, fig, ax, title, subtitle, path):
    _clean(ax)
    _titles(fig, ax, title, subtitle)
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def _percent_axis(axis):
    """Nice percent ticks, with a decimal only where a tick needs one."""
    from matplotlib.ticker import FuncFormatter, MaxNLocator
    axis.set_major_locator(MaxNLocator(nbins=6, steps=[1, 2, 2.5, 5, 10]))
    axis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{100 * v:.0f}%" if abs(100 * v - round(100 * v)) < 1e-6 else f"{100 * v:.1f}%"))


def _spread(values, gap):
    """Nudge label positions apart so that neighbours are at least `gap` apart."""
    order = np.argsort(values)
    placed = np.array(values, dtype=float)
    for i in range(1, len(order)):
        prev, cur = order[i - 1], order[i]
        placed[cur] = max(placed[cur], placed[prev] + gap)
    shift = (placed - np.array(values, dtype=float)).mean()  # re-centre the block
    return placed - shift


def dot_plot(rows, path, title, subtitle, xlabel, reference=0.5):
    """Horizontal dots with 95% intervals, top to bottom.
    rows = [(label, estimate, low, high, colour)]."""
    plt = _pyplot()
    n = len(rows)
    low = np.array([r[2] for r in rows])
    high = np.array([r[3] for r in rows])
    left, right = min(float(low.min()), reference), max(float(high.max()), reference)
    pad = max(0.005, 0.05 * (right - left))
    fig, ax = plt.subplots(figsize=(7.0, 0.36 * n + 1.5))
    ax.axvline(reference, color=AXIS, linewidth=1, zorder=1)
    for i, (_, estimate, lo, hi, colour) in enumerate(rows):
        ax.hlines(i, lo, hi, color=colour, linewidth=2, zorder=2)
        ax.plot(estimate, i, "o", color=colour, markersize=8, markeredgecolor=SURFACE,
                markeredgewidth=2, zorder=3)
        ax.text(hi + pad * 0.5, i, f"{estimate:.1%}", va="center", fontsize=9, color=INK2)
    ax.set_yticks(range(n), labels=[r[0] for r in rows])
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_xlim(left - pad, right + pad * 3.5)
    _percent_axis(ax.xaxis)
    ax.tick_params(axis="x", colors=MUTED)
    ax.grid(axis="x", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.set_xlabel(xlabel)
    _save(plt, fig, ax, title, subtitle, path)


def sweep_plot(x, labels, est, low, high, path, title, subtitle, xlabel, ylabel, log=False,
               reference=0.5):
    """One series over a swept setting, with 95% intervals; the best point is labelled."""
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    ax.axhline(reference, color=AXIS, linewidth=1, zorder=1)
    ax.plot(x, est, color=BLUE, linewidth=2, zorder=2, solid_capstyle="round")
    ax.vlines(x, low, high, color=BLUE, linewidth=2, alpha=0.45, zorder=2)
    ax.plot(x, est, "o", color=BLUE, markersize=8, markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
    best = int(np.argmax(est))
    ax.annotate(f"{est[best]:.1%}", (x[best], high[best]), xytext=(0, 6), textcoords="offset points",
                ha="center", va="bottom", fontsize=9, color=INK2)
    if log:
        ax.set_xscale("log")
        ax.minorticks_off()
    ax.set_xticks(x, labels=labels)
    bottom, top = min(float(np.min(low)), reference), max(float(np.max(high)), reference)
    pad = max(0.005, 0.08 * (top - bottom))
    ax.set_ylim(bottom - pad, top + 2 * pad)
    _percent_axis(ax.yaxis)
    ax.tick_params(colors=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    _save(plt, fig, ax, title, subtitle, path)


def scales_plot(avg, path):
    """Each heuristic bot's average win rate under the four line-value scales (x)."""
    plt = _pyplot()
    colours = [BLUE, ORANGE, AQUA, YELLOW]
    x = np.arange(len(SCALES))
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    order = avg["default"].sort_values(ascending=False).index
    for colour, bot in zip(colours, order):
        values = avg.loc[bot, SCALES].to_numpy(dtype=float)
        ax.plot(x, values, color=colour, linewidth=2, zorder=2, label=bot)
        ax.plot(x, values, "o", color=colour, markersize=8, markeredgecolor=SURFACE,
                markeredgewidth=2, zorder=3)
    ends = avg.loc[order, SCALES[-1]].to_numpy(dtype=float)
    span = float(avg[SCALES].to_numpy().max() - avg[SCALES].to_numpy().min())
    for bot, y in zip(order, _spread(ends, 0.06 * span)):
        ax.text(x[-1] + 0.12, y, bot, va="center", fontsize=9, color=INK2)
    ax.set_xticks(x, labels=["linear\n1, 2, 3, 4", "flat\n1, 2, 4, 8", "default\n1, 4, 16, 128",
                             "steep\n1, 10, 100, 1000"])
    ax.set_xlim(-0.3, len(SCALES) - 0.3)
    _percent_axis(ax.yaxis)
    ax.tick_params(colors=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.set_xlabel("Line-value scale: value of an open line with 1, 2, 3, 4 chips")
    ax.set_ylabel("Average win rate vs the other pilot bots")
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0.0, -0.22), ncol=4, fontsize=9)
    _save(plt, fig, ax, "Does the ranking survive other line values?",
          "Each heuristic pilot bot's average win rate against the other four pilot bots (random "
          "included) under each\nscale. Lines that never cross mean the ranking is unchanged.", path)


def jack_plot(usage, path):
    """What each Jack policy's Jacks achieved, per game: two-eyed (left), one-eyed (right)."""
    plt = _pyplot()
    n = len(usage)
    y = np.arange(n)
    fig, (left, right) = plt.subplots(1, 2, figsize=(9.6, 0.55 * n + 2.0), sharey=True,
                                      gridspec_kw={"width_ratios": [1.3, 1.0], "wspace": 0.08})
    finished = usage["wild_finished"].to_numpy(dtype=float)
    blocked = usage["wild_blocked"].to_numpy(dtype=float)
    rest = usage["two_eyed_jacks"].to_numpy(dtype=float) - finished - blocked
    style = dict(height=0.62, edgecolor=SURFACE, linewidth=2)
    left.barh(y, finished, color=BLUE, label="completed a sequence", **style)
    left.barh(y, blocked, left=finished, color=ORANGE, label="blocked an opponent four", **style)
    left.barh(y, rest, left=finished + blocked, color=OTHER, label="anything else", **style)
    broke = usage["removal_broke_four"].to_numpy(dtype=float)
    rest1 = usage["one_eyed_jacks"].to_numpy(dtype=float) - broke
    right.barh(y, broke, color=AQUA, label="broke an opponent four", **style)
    right.barh(y, rest1, left=broke, color=OTHER, label="anything else", **style)
    for ax, total, heading in ((left, usage["two_eyed_jacks"], "Two-eyed (wild) Jacks per game"),
                               (right, usage["one_eyed_jacks"], "One-eyed (removal) Jacks per game")):
        for yi, t in enumerate(total):
            ax.text(t + 0.02, yi, f"{t:.2f}", va="center", fontsize=9, color=INK2)
        ax.set_xlim(0, float(max(usage["two_eyed_jacks"].max(), usage["one_eyed_jacks"].max())) * 1.18)
        ax.set_title(heading, loc="left", fontsize=10, color=INK2)
        ax.tick_params(axis="x", colors=MUTED)
        ax.tick_params(length=0)
        ax.grid(axis="x", color=GRID, linewidth=1)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0.0, -0.08), fontsize=8.5, ncol=1)
    left.set_yticks(y, labels=list(usage.index))
    left.set_ylim(n - 0.5, -0.5)
    _titles(fig, left, "What each Jack policy's Jacks achieved",
            "Average Jacks played per game, split by what each one did. Same five bots, 5,000 deals, "
            "both seatings.")
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def hunt_plot(record, path):
    """The best confirmed candidate against the current equilibrium, per iteration."""
    plt = _pyplot()
    its = record["iterations"]
    x = np.array([it["iteration"] for it in its])
    value = np.array([it["value"] for it in its])
    se = np.array([it["se"] for it in its])
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.axhline(0.5, color=AXIS, linewidth=1, zorder=1)
    for xi, v, s, added in zip(x, value, se, [it["added"] for it in its]):
        colour = BLUE if added else MUTED
        ax.vlines(xi, v - Z * s, v + Z * s, color=colour, linewidth=2, zorder=2)
        ax.plot(xi, v, "o", color=colour, markersize=8, markeredgecolor=SURFACE, markeredgewidth=2,
                zorder=3)
        ax.annotate(f"{v:.1%}", (xi, v + Z * s), xytext=(0, 5), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9, color=INK2)
    ax.set_xticks(x)
    ax.set_xlim(x.min() - 0.6, x.max() + 0.6)
    _percent_axis(ax.yaxis)
    ax.tick_params(colors=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Best candidate vs the equilibrium")
    _save(plt, fig, ax, "Can any strategy beat the equilibrium?",
          "Each iteration's best candidate, confirmed on fresh deals, against the current equilibrium "
          "mix, with its\n95% interval. Blue: it beat the mix and joined the pool. Grey: within the "
          "noise, so the hunt stopped.", path)


def curse_plot(record, path):
    """The winner's curse: every candidate's screening estimate (top row) and, for the
    finalists, the confirmed estimate on fresh deals (bottom row)."""
    plt = _pyplot()
    it = next(it for it in record["iterations"] if "screening" in it)
    settings = record["settings"]
    screened = {c: v["estimate"] for c, v in it["screening"].items()}
    finalists = it["finalists"]
    rng = np.random.default_rng(0)  # vertical jitter only, so overlapping dots stay visible
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    ax.axvline(0.5, color=AXIS, linewidth=1, zorder=1)
    names = [c for c in screened if c not in {f["spec"] for f in finalists}]
    floor = 0.45  # zoom on the contest at the top; weaker candidates are counted, not drawn
    xs = np.array([screened[c] for c in names if screened[c] >= floor])
    below = sum(1 for c in names if screened[c] < floor)
    ax.plot(xs, 1 + rng.uniform(-0.08, 0.08, len(xs)), "o", color=MUTED, alpha=0.55, markersize=6,
            markeredgecolor=SURFACE, markeredgewidth=1, zorder=2)
    if below:
        ax.annotate(f"+ {below} more candidates below {floor:.0%}, not shown", (floor, 0.8), xytext=(4, 0),
                    textcoords="offset points", ha="left", va="center", fontsize=8.5, color=MUTED)
    ax.set_xlim(floor, max(0.5, max(screened.values())) + 0.012)
    for f in finalists:
        ax.plot([f["screening"], f["confirmed"]], [1, 0], color=BLUE, linewidth=1.2, alpha=0.6, zorder=2)
        ax.hlines(0, f["confirmed"] - Z * f["se"], f["confirmed"] + Z * f["se"], color=BLUE, linewidth=2, zorder=3)
        for x, y in ((f["screening"], 1), (f["confirmed"], 0)):
            ax.plot(x, y, "o", color=BLUE, markersize=8, markeredgecolor=SURFACE, markeredgewidth=2, zorder=4)
    best = max(finalists, key=lambda f: f["screening"])
    ax.annotate(f"best screening estimate {best['screening']:.1%}", (best["screening"], 1), xytext=(0, 12),
                textcoords="offset points", ha="center", fontsize=9, color=INK2)
    ax.annotate(f"confirmed {best['confirmed']:.1%}", (best["confirmed"], 0), xytext=(0, -18),
                textcoords="offset points", ha="center", fontsize=9, color=INK2)
    ax.set_yticks([1, 0], labels=[f"screening\n{settings['screen_deals']:,} deals",
                                  f"confirmation\n{settings['confirm_deals']:,} fresh deals"])
    ax.set_ylim(-0.45, 1.45)
    _percent_axis(ax.xaxis)
    ax.tick_params(axis="x", colors=MUTED)
    ax.grid(axis="x", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.set_xlabel("Win rate against the equilibrium (" + ", ".join(it["mix"]) + ")")
    _save(plt, fig, ax, "The winner's curse in the counter-strategy hunt",
          f"Each of the {len(screened)} candidates was screened against the equilibrium (top row). The "
          f"{len(finalists)} best (blue) were\nreplayed on fresh deals (bottom row, with 95% intervals): "
          "the best-looking candidates fall back to the equilibrium.", path)


# ---- the sections of results/README.md --------------------------------------------------

def index_section(runs):
    rows = []
    for name, run in runs.items():
        info = run.info
        links = [] if run.is_hunt else [f"[summary]({name}/summary.md)"]
        if os.path.exists(os.path.join(run.folder, "comparison.md")) or name in VERSUS_PILOT:
            links.append(f"[vs pilot]({name}/comparison.md)")
        if run.is_hunt:
            links.append(f"[log]({name}/hunt_log.md)")
        rows.append([f"`{name}`", RUNS.get(name, ""), f"{len(run.games):,}",
                     info.get("deals", "–"), info.get("seed", "–"),
                     "–" if run.is_hunt else info.get("values") or "default",
                     "–" if run.is_hunt else info.get("sequences_to_win", 2), ", ".join(links)])
    return ["# Results", "",
            "Every folder holds one experiment: its game log (`games.csv.gz`, one row per game), its "
            "settings (`games_run.json`), the report `analysis.py` writes (`summary.md`) and its charts. "
            "This page and the figures in `figures/` are generated by `python study.py`; the "
            "interpretation is in [FINDINGS.md](../FINDINGS.md).", "",
            _md_table(["run", "what it tests", "games", "deals", "first seed", "line values",
                       "sequences to win", "reports"], rows)]


def full_section(runs, figures):
    run = runs.get("full")
    if run is None:
        return []
    M, half, _ = run.matrix()
    bots = list(M.index)
    mix, _ = analysis.equilibrium(M)
    avg = field_average(M, half)
    ratings, ladder = analysis.transitivity(M)
    nash = analysis.nash_average(M, mix)
    tests = analysis.pairwise_tests(M, half)
    vs = analysis.versus(M, half, "mixed_save")
    order = list(avg.sort_values("avg", ascending=False).index)
    rows = []
    for b in order:
        if b == "mixed_save":
            versus = "–"
        else:
            versus = rate(M, half, b, "mixed_save") + (" (significant)" if vs.loc[b, "significant"] else "")
        rows.append([b, f"{_pct(avg.loc[b, 'avg'])} ±{100 * Z * avg.loc[b, 'se']:.1f}", versus,
                     f"{100 * ratings[b]:+.1f}", _pct(mix[b]), _pct(nash[b])])
    support = [b for b in bots if mix[b] > 0.005]
    lines = ["", "## Full tournament: all 18 strategies", "",
             f"Ranking by average win rate against the other 17 bots. The equilibrium of the meta-game "
             f"is {mix_text(mix)}. A rating per bot explains {_pct(ladder)} of the matrix. "
             f"{int((tests['p_holm'] < 0.05).sum())} of {len(tests)} pairings differ from 50% after the "
             "Holm correction.", "",
             _md_table(["bot", "avg vs field (95%)", "vs mixed_save", "rating (points)",
                        "equilibrium weight", "vs the equilibrium mix"], rows)]

    dots = [(b, avg.loc[b, "avg"], avg.loc[b, "avg"] - Z * avg.loc[b, "se"],
             avg.loc[b, "avg"] + Z * avg.loc[b, "se"], BLUE if b in support else MUTED)
            for b in order if b != "random"]
    dot_plot(dots, os.path.join(figures, "full_ranking.png"),
             "The 18 strategies, ranked",
             "Average win rate against the other 17 strategies, with 95% intervals. Blue: in the "
             "equilibrium mix.\n"
             f"random ({_pct(avg.loc['random', 'avg'])}) is not shown.",
             "Average win rate against the field")

    others = vs.drop(index=[b for b in ("random",) if b in vs.index]).sort_values("win_rate", ascending=False)
    dots = []
    for b, r in others.iterrows():
        colour = MUTED
        if r["significant"]:
            colour = BLUE if r["win_rate"] > 0.5 else RED
        dots.append((b, r["win_rate"], r["win_rate"] - r["margin"], r["win_rate"] + r["margin"], colour))
    dot_plot(dots, os.path.join(figures, "versus_mixed_save.png"),
             "Each strategy against mixed_save, the pilot champion",
             "Win rate against mixed_save in the full tournament, with 95% intervals. Blue: beats it, "
             "red: loses to it\n(Holm-corrected over all 153 pairings); grey: no clear difference. "
             f"random ({_pct(M.loc['random', 'mixed_save'])}) is not shown.",
             "Win rate against mixed_save")
    return lines


def sensitivity_section(runs, figures):
    have = {"default": runs.get("pilot"), **{s: runs.get(f"values_{s}") for s in ("linear", "flat", "steep")}}
    if have["default"] is None or not any(have[s] for s in ("linear", "flat", "steep")):
        return []
    scales = [s for s in SCALES if have[s] is not None]
    bots = have["default"].bots
    avg, ranking, equilibria, pairs = {}, {}, {}, {}
    for s in scales:
        M, half, _ = have[s].matrix()
        a = field_average(M.loc[bots, bots], half.loc[bots, bots])
        avg[s] = a["avg"]
        ranking[s] = ranking_text(a)
        equilibria[s] = mix_text(analysis.equilibrium(M.loc[bots, bots])[0])
        pairs[s] = {key: rate(M, half, *key) for key in
                    [("mixed_save", "mixed"), ("blocker", "builder"), ("mixed", "builder")]}
    table = pd.DataFrame(avg)
    lines = ["", "## Line values: does the ranking survive?", "",
             "Average win rate against the other pilot bots under each line-value scale (the pilot is "
             "the default scale). All four runs use the same 5,000 deals.", "",
             _md_table(["bot"] + scales, [[b] + [_pct(table.loc[b, s]) for s in scales] for b in bots]),
             "", _md_table(["scale", "ranking", "equilibrium", "mixed_save vs mixed", "blocker vs builder",
                            "mixed vs builder"],
                           [[s, ranking[s], equilibria[s]] + list(pairs[s].values()) for s in scales])]
    if len(scales) == 4:
        scales_plot(table.drop(index="random"), os.path.join(figures, "value_scales.png"))
    return lines


def comparison_section(runs, name, heading, intro):
    """Pilot vs another run of the same five bots: pairing by pairing."""
    if "pilot" not in runs or name not in runs:
        return []
    bots = runs["pilot"].bots
    Ma, Ha, _ = runs["pilot"].matrix()
    Mb, Hb, _ = runs[name].matrix()
    diffs = compare_runs.pairing_differences(Ma, Ha, Mb, Hb, bots)
    rows = [[f"{r.a} vs {r.b}", f"{_pct(r.rate_a)} ±{100 * r.margin_a:.1f}",
             f"{_pct(r.rate_b)} ±{100 * r.margin_b:.1f}", f"{100 * r.diff:+.1f}",
             f"{r.z:+.2f}" if np.isfinite(r.z) else "n/a"] for r in diffs.itertuples()]
    avg_a, avg_b = field_average(Ma, Ha), field_average(Mb, Hb)
    return ["", heading, "", intro, "",
            _md_table(["pairing", "pilot", name, "difference (points)", "z"], rows), "",
            f"{int(diffs['beyond'].sum())} of {len(diffs)} differences are beyond chance (|z| ≥ 1.96); "
            f"about {0.05 * len(diffs):.1f} would be expected by luck alone if nothing had changed. "
            f"Largest difference: {100 * diffs['diff'].abs().max():.1f} points.", "",
            f"Ranking, pilot: {ranking_text(avg_a)}.", "",
            f"Ranking, {name}: {ranking_text(avg_b)}."]


def replication_summary(runs):
    """Every independent estimate of each pilot pairing: the pilot, the replications,
    and the same pairing inside the full tournament."""
    if "pilot" not in runs:
        return []
    bots = runs["pilot"].bots
    names = [n for n in ("pilot", "replication", "replication2", "full")
             if n in runs and set(bots) <= set(runs[n].bots)]
    if len(names) < 3:
        return []
    mats = {n: runs[n].matrix() for n in names}
    rows = []
    for a, b in itertools.combinations(bots, 2):
        est = np.array([mats[n][0].loc[a, b] for n in names])
        se = np.array([mats[n][1].loc[a, b] / Z for n in names])
        w = 1 / se ** 2
        pooled = float((w * est).sum() / w.sum())
        chi2 = float((w * (est - pooled) ** 2).sum())
        rows.append([f"{a} vs {b}"] + [f"{_pct(e)} ±{100 * Z * s:.1f}" for e, s in zip(est, se)]
                    + [_pct(pooled), f"{chi2:.1f}"])
    return ["", "## Every estimate of the pilot pairings", "",
            "Each pilot pairing measured on independent deals: the pilot (seeds from 2026), the two "
            "replications, and the same pairing inside the full tournament (seeds from 200000). Pooled = "
            f"inverse-variance weighted mean. χ² measures disagreement between the estimates; with "
            f"{len(names)} estimates it has {len(names) - 1} degrees of freedom (95% of the time below "
            f"{ {2: 5.99, 3: 7.81, 4: 9.49}[len(names) - 1] }) if they differ only by chance.", "",
            _md_table(["pairing"] + names + ["pooled", "χ²"], rows)]


def rule_section(runs):
    if "pilot" not in runs or "one_sequence" not in runs:
        return []
    lines = comparison_section(runs, "one_sequence", "## Rule variant: first to one sequence",
                               "The same five bots and the same 5,000 deals, but the first sequence wins.")
    rows = []
    fm_a, fm_b = analysis.first_move(runs["pilot"].games), analysis.first_move(runs["one_sequence"].games)
    len_a, len_b = analysis.game_lengths(runs["pilot"].games), analysis.game_lengths(runs["one_sequence"].games)
    for b in runs["pilot"].bots:
        label = f"{b} vs itself"
        rows.append([b, _pct(fm_a.loc[label, "first_player_win_rate"]),
                     _pct(fm_b.loc[label, "first_player_win_rate"]),
                     f"{len_a.loc[b, 'mirror']:.0f}", f"{len_b.loc[b, 'mirror']:.0f}"])
    return lines + ["", "First-move advantage and length of mirror matches under each rule:", "",
                    _md_table(["bot", "first player wins, 2 sequences", "first player wins, 1 sequence",
                               "median plies, 2 sequences", "median plies, 1 sequence"], rows)]


def jacks_section(runs, figures):
    run = runs.get("jacks")
    if run is None:
        return []
    M, half, _ = run.matrix()
    avg = field_average(M, half)
    usage = analysis.jack_usage(run.games, run.bots)
    order = list(avg.sort_values("avg", ascending=False).index)

    def share(part, whole):
        return _pct(part / whole) if whole > 0 else "n/a"

    rows = []
    for b in order:
        u = usage.loc[b]
        rows.append([b, "–" if b == "mixed" else rate(M, half, b, "mixed"),
                     f"{_pct(avg.loc[b, 'avg'])} ±{100 * Z * avg.loc[b, 'se']:.1f}",
                     f"{u['two_eyed_jacks']:.2f}", share(u["wild_finished"], u["two_eyed_jacks"]),
                     share(u["wild_blocked"], u["two_eyed_jacks"]), f"{u['one_eyed_jacks']:.2f}",
                     share(u["removal_broke_four"], u["one_eyed_jacks"])])
    jack_plot(usage.loc[order], os.path.join(figures, "jack_policies.png"))
    mix, _ = analysis.equilibrium(M)
    return ["", "## Jack timing", "",
            f"The five Jack policies, all otherwise identical to mixed. Equilibrium: {mix_text(mix)}.", "",
            _md_table(["policy", "vs mixed", "avg vs field (95%)", "two-eyed per game", "finished a sequence",
                       "blocked a four", "one-eyed per game", "broke a four"], rows)]


def defend_section(runs, figures):
    run = runs.get("sweep_defend")
    if run is None:
        return []
    M, half, _ = run.matrix()
    avg = field_average(M, half)
    bots = sorted(M.index, key=lambda b: setting(b, "defend", 1.0))
    weights = [setting(b, "defend", 1.0) for b in bots]
    reference = next(b for b, w in zip(bots, weights) if w == 1.0)
    rows = [[f"{w:g}", b, f"{_pct(avg.loc[b, 'avg'])} ±{100 * Z * avg.loc[b, 'se']:.1f}",
             "–" if b == reference else rate(M, half, b, reference)] for b, w in zip(bots, weights)]
    est = avg.loc[bots, "avg"].to_numpy()
    se = avg.loc[bots, "se"].to_numpy()
    sweep_plot(np.arange(len(bots)), [f"{w:g}" for w in weights], est, est - Z * se, est + Z * se,
               os.path.join(figures, "defend_sweep.png"), "How much should a bot defend?",
               "mixed_save with its defence weight varied (attack stays 1). Each point is that version's "
               "average win rate\nagainst the other eight, with its 95% interval.",
               "Defence weight (attack = 1)", "Average win rate vs the other weights")
    mix, _ = analysis.equilibrium(M)
    return ["", "## Defence weight sweep", "",
            f"mixed_save with the defence weight varied; attack stays 1. Equilibrium: {mix_text(mix)}.", "",
            _md_table(["defence weight", "bot", "avg vs the other weights (95%)", "vs defence 1"], rows)]


def lambda_section(runs, figures):
    run = runs.get("sweep_lambda")
    if run is None:
        return []
    M, half, _ = run.matrix()
    avg = field_average(M, half)
    noisy = sorted([b for b in M.index if setting(b, "lam", 0.0) > 0], key=lambda b: setting(b, "lam", 0.0))
    lams = [setting(b, "lam", 0.0) for b in noisy]
    greedy = next(b for b in M.index if setting(b, "lam", 0.0) == 0)
    rows = [[f"{lam:g}", b, rate(M, half, b, greedy), f"{_pct(avg.loc[b, 'avg'])}"] for b, lam in zip(noisy, lams)]
    rows.append(["greedy", greedy, "–", _pct(avg.loc[greedy, "avg"])])
    est = np.array([M.loc[b, greedy] for b in noisy])
    margin = np.array([half.loc[b, greedy] for b in noisy])
    sweep_plot(np.array(lams), [f"{lam:g}" for lam in lams], est, est - margin, est + margin,
               os.path.join(figures, "lambda_sweep.png"), "How much does noisy choice cost?",
               "Logit choice picks each move with probability proportional to exp(λ × score). Win rate "
               "against\nmixed_save, which always plays the top-scoring move, with 95% intervals.",
               "λ (log scale): small = nearly random, large = nearly greedy", f"Win rate vs {greedy}", log=True)
    return ["", "## Bounded rationality: the λ sweep", "",
            "Logit choice with probability proportional to exp(λ × score), against greedy mixed_save.", "",
            _md_table(["λ", "bot", f"vs {greedy}", "avg vs field"], rows)]


def matrix_section(runs, name, heading, intro):
    """A small run's full win-rate matrix, with margins and games per pairing."""
    run = runs.get(name)
    if run is None:
        return []
    M, half, n = run.matrix()
    bots = list(M.index)
    rows = [[f"**{a}**"] + ["–" if a == b else rate(M, half, a, b) for b in bots] for a in bots]
    games = sorted({int(n.loc[a, b]) for a in bots for b in bots if a != b})
    return ["", heading, "",
            f"{intro} Row bot's win rate against the column bot, with the 95% margin; "
            f"{', '.join(f'{g:,}' for g in games)} games per pairing.",
            "", _md_table(["bot \\ opponent"] + bots, rows)]


def decision_agreement(specs, reference="mixed_save", deals=100, seed=950_000):
    """How often each strategy picks a move the reference would not.

    Each strategy plays the reference on `deals` deals, from both seats. On every one
    of its decisions with two or more legal moves, the reference scores the same
    position; the decision "differs" if the chosen move is not among the reference's
    top-scoring moves. Returns {spec: (share that differ, decisions)}."""
    from bots import make_bot
    from game import Game, seat_rngs

    ref = make_bot(reference)
    shares = {}
    for spec in specs:
        bot = make_bot(spec)
        differ = total = 0
        for d in range(deals):
            for seat in (0, 1):
                game = Game(seed + d)
                rngs = seat_rngs(seed + d)
                players = (bot, ref) if seat == 0 else (ref, bot)
                while game.winner is None and game.turn < 500:
                    p = game.to_move
                    if p != seat:
                        game.play_turn(players[p], rngs[p])
                        continue
                    traded = game._trade_dead_card(p)
                    moves = game.legal_moves(p)
                    move = bot.choose(game.views[p], p, moves, rngs[p]) if moves else None
                    if len(moves) > 1:
                        scored = ref.score_moves(game.views[p], p, moves)
                        top = max(s for s, _, _ in scored)
                        best = {m for s, _, m in scored if s >= top - 1e-9 * max(1.0, abs(top))}
                        differ += move not in best
                        total += 1
                    game.play_move(p, move, traded)
        shares[spec] = (differ / total if total else float("nan"), total)
    return shares


JACK_TIMING = {"mixed", "eager", "save_wild", "save_remove"}  # differ from mixed_save only in Jack policy
BASELINES = {"builder", "blocker"}                          # differ in their attack/defend weights


def agreement_plot(bots, shares, M, half, path, note):
    """Left: how often each strategy's move differs from mixed_save's. Right: its win rate
    against mixed_save. Rows coloured by the kind of change."""
    plt = _pyplot()
    from matplotlib.lines import Line2D
    n = len(bots)
    y = np.arange(n)
    colour = {b: ORANGE if b in JACK_TIMING else AQUA if b in BASELINES else BLUE for b in bots}
    fig, (left, right) = plt.subplots(1, 2, figsize=(10.2, 0.4 * n + 2.2), sharey=True,
                                      gridspec_kw={"width_ratios": [1.0, 1.15], "wspace": 0.06})
    values = np.array([shares[b][0] for b in bots])
    left.barh(y, values, height=0.62, color=[colour[b] for b in bots], edgecolor=SURFACE, linewidth=2)
    for yi, v in zip(y, values):
        left.text(v + values.max() * 0.02, yi, f"{v:.1%}", va="center", fontsize=8.5, color=INK2)
    left.set_xlim(0, values.max() * 1.22)
    left.set_title("Decisions where its move differs from mixed_save's", loc="left", fontsize=10, color=INK2)
    rates = np.array([M.loc[b, "mixed_save"] for b in bots])
    margins = np.array([half.loc[b, "mixed_save"] for b in bots])
    right.axvline(0.5, color=AXIS, linewidth=1, zorder=1)
    for yi, b, r, m in zip(y, bots, rates, margins):
        right.hlines(yi, r - m, r + m, color=colour[b], linewidth=2, zorder=2)
        right.plot(r, yi, "o", color=colour[b], markersize=7, markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
        right.text(r + m + 0.004, yi, f"{r:.1%}", va="center", fontsize=8.5, color=INK2)
    right.set_xlim(min(0.5, float((rates - margins).min())) - 0.01, max(0.5, float((rates + margins).max())) + 0.03)
    right.set_title("Its win rate against mixed_save (95% interval)", loc="left", fontsize=10, color=INK2)
    for ax in (left, right):
        _percent_axis(ax.xaxis)
        ax.tick_params(axis="x", colors=MUTED)
        ax.tick_params(length=0)
        ax.grid(axis="x", color=GRID, linewidth=1)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_visible(False)
    left.set_yticks(y, labels=bots)
    left.set_ylim(n - 0.5, -0.5)
    handles = [Line2D([], [], color=c, marker="s", linestyle="", markersize=9, label=label)
               for c, label in ((BLUE, "adds an idea to mixed_save"), (ORANGE, "a different Jack policy"),
                                (AQUA, "other attack/defend weights"))]
    left.legend(handles=handles, frameon=False, loc="upper left", bbox_to_anchor=(0.0, -0.06 - 0.25 / n),
                ncol=3, fontsize=9)
    _titles(fig, left, "It's not how often an idea changes the move, but where",
            "Each strategy played mixed_save on 100 deals from both seats; on each of its decisions with a real "
            "choice,\nmixed_save scored the same position. Win rates are from the full tournament. " + note)
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def agreement_section(runs, figures):
    run = runs.get("full")
    if run is None:
        return []
    M, half, _ = run.matrix()
    specs = [b for b in M.index if b != "mixed_save"]
    shares = decision_agreement(specs)
    order = sorted(specs, key=lambda b: shares[b][0])
    rows = [[b, f"{100 * shares[b][0]:.1f}%", f"{shares[b][1]:,}", rate(M, half, b, "mixed_save")] for b in order]
    shown = [b for b in order if b != "random"]
    agreement_plot(shown, shares, M, half, os.path.join(figures, "decision_agreement.png"),
                   f"random ({shares['random'][0]:.0%} of decisions, {_pct(M.loc['random', 'mixed_save'])}) is not shown.")
    return ["", "## How often does each idea change the move?", "",
            "Each strategy played mixed_save on 100 deals from both seats. On each of its decisions with "
            "two or more legal moves, mixed_save scored the same position; the decision differs if the "
            "chosen move is not among mixed_save's top-scoring moves.", "",
            _md_table(["bot", "decisions that differ", "decisions", "win rate vs mixed_save (full tournament)"], rows)]


def ablation_section(runs, figures):
    run = runs.get("ablation")
    if run is None:
        return []
    M, half, _ = run.matrix()
    avg = field_average(M, half)
    tests = analysis.pairwise_tests(M, half)

    def holm(a, b):
        row = tests[((tests["a"] == a) & (tests["b"] == b)) | ((tests["a"] == b) & (tests["b"] == a))]
        return bool(len(row)) and bool(row["p_holm"].iloc[0] < 0.05)

    others = [b for b in avg.sort_values("avg", ascending=False).index if b != "expert"]
    rows = [[b, rate(M, half, b, "expert") + (" (significant)" if holm(b, "expert") else ""),
             f"{_pct(avg.loc[b, 'avg'])} ±{100 * Z * avg.loc[b, 'se']:.1f}"] for b in others]
    rows.append(["expert", "–", f"{_pct(avg.loc['expert', 'avg'])} ±{100 * Z * avg.loc['expert', 'se']:.1f}"])
    order = list(avg.sort_values("avg", ascending=False).index)
    dots = [(b, avg.loc[b, "avg"], avg.loc[b, "avg"] - Z * avg.loc[b, "se"], avg.loc[b, "avg"] + Z * avg.loc[b, "se"],
             MUTED if b == "expert" else BLUE) for b in order]
    dot_plot(dots, os.path.join(figures, "expert_ablation.png"),
             "Taking expert apart: counting helps, adaptation hurts",
             "expert is mixed_save + forks + hand management + card counting + inference + adaptation. Each "
             "variant drops one\ncomponent. Average win rate against the other seven bots in this run, with "
             "95% intervals;\nthe vertical line marks the full expert (grey).",
             "Average win rate against the other bots in the ablation run", reference=avg.loc["expert", "avg"])
    return ["", "## Taking expert apart", "",
            "expert with one component removed at a time, against the full expert and the rest of this field.", "",
            _md_table(["bot", "vs expert", "avg vs this field (95%)"], rows)]


def hunt_section(runs, figures):
    lines = []
    for name, run in runs.items():
        if not run.is_hunt:
            continue
        with open(os.path.join(run.folder, "hunt_log.json"), encoding="utf-8") as f:
            record = json.load(f)
        from statistics import NormalDist
        rows = []
        for it in record["iterations"]:
            # The best of k confirmed finalists is itself a selected estimate: a Bonferroni-corrected
            # lower bound shows how much of its margin survives that selection.
            z_k = NormalDist().inv_cdf(1 - 0.05 / (2 * len(it["finalists"])))
            rows.append([it["iteration"], len(it["pool"]), mix_text(pd.Series(it["mix"])), it["screened"],
                         f"`{it['best']}`", f"{_pct(it['value'])} ({_pct(it['value'] - Z * it['se'])} – "
                         f"{_pct(it['value'] + Z * it['se'])})", f"{100 * (it['value'] - z_k * it['se']):.2f}%",
                         "added" if it["added"] else "stop"])
        final = record.get("final") or {}
        settings = record["settings"]
        lines += ["", f"## Counter-strategy hunt: `{name}`", "",
                  f"Start pool: {', '.join(record['start_pool'])}. Screening on {settings['screen_deals']} "
                  f"deals, confirming on {settings['confirm_deals']} fresh deals, {settings['random']} random "
                  f"candidates per iteration. Games played: {final.get('games', 0):,}.", "",
                  _md_table(["iteration", "pool size", "equilibrium", "candidates screened", "best candidate",
                             "its win rate vs the mix (95%)", "lower bound, Bonferroni over the finalists",
                             "result"], rows)]
        if final:
            lines += ["", f"Final pool: {', '.join(final['pool'])}. Final equilibrium: "
                          f"{mix_text(pd.Series(final['mix']))}."]
        if name == "hunt" and len(record["iterations"]) > 1:
            hunt_plot(record, os.path.join(figures, "hunt.png"))
        if name == "hunt" and any("screening" in it for it in record["iterations"]):
            curse_plot(record, os.path.join(figures, "hunt_winners_curse.png"))
    return lines


# ---- main ----------------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description="Rebuild the study's reports and figures.")
    parser.add_argument("--results", default="results", help="folder of run folders (default: %(default)s)")
    parser.add_argument("--figures", default="figures", help="where the cross-run figures go")
    parser.add_argument("--skip-runs", action="store_true", help="don't rewrite each run's summary.md and charts")
    args = parser.parse_args(argv)

    runs = find_runs(args.results)
    if not runs:
        raise SystemExit(f"No game logs found under {args.results}/")
    if not args.skip_runs:
        for name, run in runs.items():
            if run.is_hunt:
                continue
            print(f"Analysing {name} ({len(run.games):,} games)...", flush=True)
            report = analysis.summarize(run.games, run.folder, run_info=run.info or None)
            with open(os.path.join(run.folder, "summary.md"), "w", encoding="utf-8") as f:
                f.write(report)
    if "pilot" in runs:
        for name in VERSUS_PILOT:
            if name in runs:
                print(f"Comparing {name} with the pilot...", flush=True)
                report = compare_runs.compare(runs["pilot"].path, runs[name].path)
                with open(os.path.join(runs[name].folder, "comparison.md"), "w", encoding="utf-8") as f:
                    f.write(report)

    os.makedirs(args.figures, exist_ok=True)
    print("Cross-run tables and figures...", flush=True)
    lines = index_section(runs)
    lines += full_section(runs, args.figures)
    lines += agreement_section(runs, args.figures)
    lines += comparison_section(runs, "replication", "## Replication",
                                "The pilot's five bots on 5,000 fresh deals. Every difference should look like chance.")
    lines += comparison_section(runs, "replication2", "## Second replication",
                                "The pilot's five bots on another 5,000 fresh deals.")
    lines += replication_summary(runs)
    lines += sensitivity_section(runs, args.figures)
    lines += rule_section(runs)
    lines += jacks_section(runs, args.figures)
    lines += defend_section(runs, args.figures)
    lines += lambda_section(runs, args.figures)
    lines += matrix_section(runs, "counting", "## Is card counting's edge real?",
                            "The top three strategies of the full tournament, head to head on 15,000 deals.")
    lines += matrix_section(runs, "defence_counting", "## Card counting and defence",
                            "A 2 x 2 design: card counting (no / yes) x defence weight (1 / 2), head to head "
                            "on 10,000 deals. `mixed:attack=0.5,jacks=save,count=1` is card counting with "
                            "the defence weight doubled relative to attack (the counter-strategy hunt's find).")
    lines += ablation_section(runs, args.figures)
    lines += matrix_section(runs, "sampler", "## Lookahead",
                            "Monte Carlo lookahead (`sampler`, k = 4 candidates, n = 8 deals each) against "
                            "the strongest heuristic bots.")
    lines += hunt_section(runs, args.figures)
    figures = sorted(f for f in os.listdir(args.figures) if f.endswith(".png"))
    rel = os.path.relpath(args.figures, args.results)
    lines += ["", "## Figures", ""] + [f"![{f}]({rel}/{f})" for f in figures]
    with open(os.path.join(args.results, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Saved {os.path.join(args.results, 'README.md')} and {len(figures)} figures in {args.figures}/")


if __name__ == "__main__":
    main()
